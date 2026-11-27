"""Transforme un instantané Bronze vérifié en tables Silver traçables."""

import csv
import hmac
import json
import re
import subprocess
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import quantiles
from tempfile import TemporaryFile

from bronze import (
    TYPES_INCIDENTS,
    TYPES_TELEMETRIE,
    charger_psql,
    commande_psql,
    encoder_champs,
    encoder_copy,
    lire_csv_bronze,
    sha256_source,
)

VERSION_CONTRAT = "silver-1.0"
HEURE = timedelta(hours=1)
MESURES = ("temperature_c", "pressure_bar", "voltage_mean_v", "rotation_mean_rpm")
SOURCES = {
    "telemetry": {
        "machine_id": "TEXT", "timestamp": "TIMESTAMPTZ",
        **dict.fromkeys(MESURES, "NUMERIC"), "pieces_produced": "BIGINT",
    },
    "releves_incidents": {
        "incident_id": "TEXT", "date": "DATE", "time": "TIME", "machine_id": "TEXT",
        "severity": "SMALLINT", "shift": "TEXT",
        **{nom: "BOOLEAN" for nom in TYPES_INCIDENTS if nom.startswith("type_")},
    },
    "machine": {
        "machine_code": "TEXT", "commissioning_date": "DATE",
        "max_daily_capacity": "INTEGER", "max_hourly_capacity_pieces": "INTEGER",
        "model": "TEXT", "production_line": "TEXT", "location": "TEXT", "criticality": "TEXT",
        "is_active": "BOOLEAN", "created_at": "TIMESTAMPTZ", "updated_at": "TIMESTAMPTZ",
    },
    "maintenance": {
        "maintenance_id": "TEXT", "machine_code": "TEXT", "maintenance_at": "TIMESTAMPTZ",
        "maintenance_type": "TEXT", "action_type": "TEXT", "component": "TEXT",
        "description": "TEXT", "related_incident_id": "TEXT", "duration_hours": "NUMERIC",
        "created_at": "TIMESTAMPTZ", "updated_at": "TIMESTAMPTZ",
    },
}
TECHNIQUE = {"bronze_run_id": "UUID NOT NULL", "bronze_hash": "TEXT NOT NULL"}
SCHEMAS = {
    table: {**types, **TECHNIQUE, "signaux": "JSONB NOT NULL"} for table, types in SOURCES.items()
}
SCHEMAS["telemetry"].update({
    "numero_ligne_csv": "BIGINT NOT NULL", "debut_heure_utc": "TIMESTAMPTZ",
    "surcroit_activite": "BOOLEAN", "mesures_manquantes": "JSONB NOT NULL",
    "mesures_atypiques_a_revoir": "JSONB NOT NULL",
})
SCHEMAS["releves_incidents"]["incident_recorded_at_utc"] = "TIMESTAMPTZ"
SCHEMAS.update({
    "reemissions": {
        "bronze_run_id": "UUID NOT NULL", "machine_id": "TEXT", "timestamp": "TIMESTAMPTZ",
        "ligne_conservee": "BIGINT NOT NULL", "hash_conserve": "TEXT NOT NULL",
        "ligne_ecartee": "BIGINT NOT NULL", "hash_ecarte": "TEXT NOT NULL", "motif": "TEXT NOT NULL",
    },
    "periodes_manquantes": {
        "bronze_run_id": "UUID NOT NULL", "machine_id": "TEXT", "mesure": "TEXT",
        "debut_utc": "TIMESTAMPTZ", "fin_utc": "TIMESTAMPTZ", "nombre_releves": "INTEGER NOT NULL",
    },
    "heures_sans_releve": {
        "bronze_run_id": "UUID NOT NULL", "machine_id": "TEXT",
        "timestamp_attendu_utc": "TIMESTAMPTZ", "etat_machine": "TEXT NOT NULL",
    },
    "manifeste": {
        "source_table": "TEXT NOT NULL", "bronze_run_id": "UUID NOT NULL", "source_file": "TEXT NOT NULL",
        "source_sha256": "TEXT NOT NULL", "version_contrat": "TEXT NOT NULL",
        "bronze_lignes": "BIGINT NOT NULL", "silver_lignes": "BIGINT NOT NULL",
        "reemissions_ecartees": "BIGINT NOT NULL",
    },
})


@dataclass
class Instantane:
    lignes: dict[str, list[dict]]
    lots: dict[str, dict]


def lire_bronze_silver(compose: Path) -> Instantane:
    """Lit les quatre tables et leurs métadonnées dans un même instantané."""
    requetes = [
        "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;",
        "SELECT json_build_array('controle', current_setting('transaction_read_only'));",
    ]
    for table, types in SOURCES.items():
        champs = ", ".join(f't."{nom}"' for nom in types)
        requetes.append(
            f"SELECT json_build_array('ligne', '{table}', t.run_id, t.hash, {champs}) "
            f"FROM bronze.{table} t;"
        )
        requetes.append(f"""
            SELECT json_build_array('lot', '{table}', a.run_id, h.source_file, h.source_sha256, h.row_count)
            FROM (SELECT DISTINCT run_id FROM bronze.{table}) a
            LEFT JOIN bronze.ingestion_runs h ON h.run_id = a.run_id AND h.target_table = '{table}';
        """)
    requetes.append("COMMIT;")
    resultat = subprocess.run(
        commande_psql(compose, "-qAt"), input="\n".join(requetes).encode(),
        capture_output=True, check=True,
    )
    lignes = {table: [] for table in SOURCES}
    lots = {}
    lecture_seule = False
    for sortie in resultat.stdout.decode("utf-8").split("\n"):
        if not sortie.strip():
            continue
        genre, *valeurs = json.loads(sortie)
        if genre == "controle":
            lecture_seule = valeurs == ["on"]
        elif genre == "ligne":
            table, *contenu = valeurs
            champs = ["bronze_run_id", "bronze_hash", *SOURCES[table]]
            lignes[table].append(dict(zip(champs, contenu, strict=True)))
        elif genre == "lot":
            table, lot, source, sha, volume = valeurs
            if table in lots or not sha:
                raise ValueError(f"{table} : un lot Bronze unique et enregistré est requis.")
            lots[table] = dict(bronze_run_id=lot, source_file=source, source_sha256=sha, bronze_lignes=volume)
    if not lecture_seule or lots.keys() != SOURCES.keys():
        raise ValueError("Instantané Bronze incomplet ou mode lecture seule non confirmé.")
    for nom, table in lignes.items():
        if len(table) != lots[nom]["bronze_lignes"]:
            raise ValueError(f"{nom} : le volume Bronze diffère du manifeste.")
    return Instantane(lignes, lots)


def choisir_telemetrie(
    lignes: list[dict], csv_source: Path, sha_attendu: str, cle: bytes,
) -> tuple[list[tuple[int, dict]], list[dict]]:
    """Retrouve les positions du CSV vérifié sans substituer ses valeurs à Bronze."""
    if sha256_source(csv_source) != sha_attendu:
        raise ValueError("Le SHA-256 du CSV télémétrie ne correspond pas au lot Bronze.")
    par_hash = defaultdict(deque)
    for ligne in lignes:
        par_hash[ligne["bronze_hash"]].append(ligne)
    premieres = {}
    retenues, reemissions = [], []
    for position, valeurs in enumerate(lire_csv_bronze(csv_source, TYPES_TELEMETRIE), 1):
        empreinte = hmac.digest(cle, encoder_champs(valeurs), "sha256").hex()
        candidatures = par_hash.get(empreinte)
        if not candidatures:
            raise ValueError(f"CSV télémétrie, enregistrement {position} : hash absent du Bronze.")
        ligne = candidatures.popleft()
        if [ligne[champ] for champ in TYPES_TELEMETRIE] != valeurs:
            raise ValueError(f"CSV télémétrie, enregistrement {position} : valeurs différentes du Bronze.")
        machine, instant = ligne["machine_id"], ligne["timestamp"]
        groupe = (machine, instant)
        if not machine or not instant or groupe not in premieres:
            retenues.append((position, ligne))
            if machine and instant:
                premieres[groupe] = position, empreinte
        else:
            premiere, hash_premiere = premieres[groupe]
            reemissions.append(dict(
                bronze_run_id=ligne["bronze_run_id"], machine_id=machine,
                timestamp=convertir(instant, "TIMESTAMPTZ", "telemetry.timestamp", utc_csv=True),
                ligne_conservee=premiere, hash_conserve=hash_premiere,
                ligne_ecartee=position, hash_ecarte=empreinte, motif="REEMISSION_PREMIERE_OCCURRENCE",
            ))
    if any(par_hash.values()) or sha256_source(csv_source) != sha_attendu:
        raise ValueError("Le CSV ordonné ne couvre pas exactement les lignes du lot Bronze.")
    return retenues, reemissions


def convertir(valeur: str | None, type_sql: str, champ: str, *, utc_csv=False):
    """Convertit les formats validés sans correction silencieuse des invalides."""
    if type_sql == "TEXT":
        return valeur
    if valeur is None or valeur == "":
        return None
    try:
        match type_sql:
            case "NUMERIC":
                if re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", valeur):
                    nombre = Decimal(valeur)
                    if nombre.is_finite():
                        return nombre
            case "SMALLINT" | "INTEGER" | "BIGINT":
                if re.fullmatch(r"[+-]?[0-9]+", valeur):
                    return int(valeur)
            case "DATE":
                if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", valeur):
                    return date.fromisoformat(valeur)
            case "TIME":
                if re.fullmatch(r"[0-9]{2}:[0-9]{2}", valeur):
                    return time.fromisoformat(valeur)
            case "TIMESTAMPTZ":
                motif = r"[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?"
                if not utc_csv:
                    motif += r"(?:Z|[+-][0-9]{2}(?::?[0-9]{2})?)"
                if not re.fullmatch(motif, valeur):
                    raise ValueError("Format d’horodatage inattendu.")
                instant = datetime.fromisoformat(valeur)
                if utc_csv and instant.tzinfo is None:
                    return instant.replace(tzinfo=UTC)
                if not utc_csv and instant.tzinfo is not None:
                    return instant.astimezone(UTC)
            case "BOOLEAN":
                booleens = {"0": False, "1": True} if champ.startswith("releves_incidents.") else {
                    "false": False, "true": True,
                }
                return booleens[valeur]
    except (ValueError, InvalidOperation, KeyError, OverflowError) as erreur:
        raise ValueError(f"{champ} : conversion impossible pour {valeur!r}. Revue requise.") from erreur
    raise ValueError(f"{champ} : valeur non conforme {valeur!r}. Revue requise.")


def typer_ligne(table: str, brute: dict) -> dict:
    resultat = {
        champ: convertir(brute[champ], type_sql, f"{table}.{champ}", utc_csv=table == "telemetry")
        for champ, type_sql in SOURCES[table].items()
    }
    resultat.update({champ: brute[champ] for champ in TECHNIQUE}, signaux=[])
    return resultat


def construire_silver(
    bronze: Instantane, telemetry: list[tuple[int, dict]], reemissions: list[dict],
) -> dict[str, list[dict]]:
    resultat = {
        nom: [typer_ligne(nom, ligne) for ligne in bronze.lignes[nom]]
        for nom in SOURCES if nom != "telemetry"
    }
    machines = defaultdict(set)
    for ligne in resultat["machine"]:
        machines[ligne["machine_code"]].add(ligne["max_hourly_capacity_pieces"])
        if not ligne["machine_code"]:
            ligne["signaux"].append("CLE_A_REVOIR")
    incidents = {ligne["incident_id"] for ligne in resultat["releves_incidents"] if ligne["incident_id"]}
    for ligne in resultat["releves_incidents"]:
        jour, heure = ligne["date"], ligne["time"]
        ligne["incident_recorded_at_utc"] = datetime.combine(jour, heure, UTC) if jour and heure else None
        if not ligne["incident_id"] or not ligne["machine_id"] or not jour or not heure:
            ligne["signaux"].append("CLE_OU_DATE_A_REVOIR")
        if ligne["machine_id"] and ligne["machine_id"] not in machines:
            ligne["signaux"].append("MACHINE_INCONNUE")
    for ligne in resultat["maintenance"]:
        lien = ligne["related_incident_id"]
        if lien == "":
            ligne["related_incident_id"] = None
        elif lien and lien not in incidents:
            ligne["signaux"].append("INCIDENT_INCONNU")
        if not ligne["maintenance_id"] or not ligne["machine_code"]:
            ligne["signaux"].append("CLE_A_REVOIR")
        if ligne["machine_code"] and ligne["machine_code"] not in machines:
            ligne["signaux"].append("MACHINE_INCONNUE")

    donnees = []
    for position, brute in telemetry:
        ligne = typer_ligne("telemetry", brute)
        instant, machine = ligne["timestamp"], ligne["machine_id"]
        seuils = machines.get(machine, set())
        seuil = next(iter(seuils)) if len(seuils) == 1 else None
        pieces = ligne["pieces_produced"]
        ligne.update(
            numero_ligne_csv=position, debut_heure_utc=instant - HEURE if instant else None,
            surcroit_activite=pieces > seuil if pieces is not None and seuil is not None else None,
            mesures_manquantes=[champ for champ in (*MESURES, "pieces_produced") if ligne[champ] is None],
            mesures_atypiques_a_revoir=[],
        )
        if not machine or not instant:
            ligne["signaux"].append("CLE_A_REVOIR")
        elif machine not in machines:
            ligne["signaux"].append("MACHINE_INCONNUE")
        if instant and (instant.minute or instant.second or instant.microsecond):
            ligne["signaux"].append("HORS_GRILLE_HORAIRE")
        donnees.append(ligne)
    signaler_atypiques(donnees)
    resultat["telemetry"] = donnees
    resultat["reemissions"] = reemissions
    resultat["periodes_manquantes"], resultat["heures_sans_releve"] = decrire_absences(donnees)
    resultat["manifeste"] = [
        dict(source_table=nom, **meta, version_contrat=VERSION_CONTRAT,
             silver_lignes=len(resultat[nom]), reemissions_ecartees=len(reemissions) if nom == "telemetry" else 0)
        for nom, meta in bronze.lots.items()
    ]
    for ligne in resultat["manifeste"]:
        if ligne["bronze_lignes"] != ligne["silver_lignes"] + ligne["reemissions_ecartees"]:
            raise ValueError(f"{ligne['source_table']} : le bilan des lignes ne concorde pas.")
    return resultat


def signaler_atypiques(telemetry: list[dict]) -> None:
    """Repérage exploratoire par machine, sans seuil physique ni exclusion."""
    series = defaultdict(list)
    for ligne in telemetry:
        for mesure in MESURES:
            if ligne["machine_id"] and ligne[mesure] is not None:
                series[ligne["machine_id"], mesure].append(ligne[mesure])
    seuils = {}
    for cle, valeurs in series.items():
        if len(valeurs) >= 4:
            q1, _, q3 = quantiles(valeurs, n=4, method="inclusive")
            ecart = 3 * (q3 - q1)
            if ecart:
                seuils[cle] = (q1 - ecart, q3 + ecart)
    for ligne in telemetry:
        for mesure in MESURES:
            bornes = seuils.get((ligne["machine_id"], mesure))
            if bornes and ligne[mesure] is not None and not bornes[0] <= ligne[mesure] <= bornes[1]:
                ligne["mesures_atypiques_a_revoir"].append(mesure)


def decrire_absences(telemetry: list[dict]) -> tuple[list[dict], list[dict]]:
    heures = defaultdict(set)
    manquants = defaultdict(set)
    for ligne in telemetry:
        lot, machine, instant = (ligne[c] for c in ("bronze_run_id", "machine_id", "timestamp"))
        if not machine or not instant or "HORS_GRILLE_HORAIRE" in ligne["signaux"]:
            continue
        heures[lot, machine].add(instant)
        for mesure in ligne["mesures_manquantes"]:
            manquants[lot, machine, mesure].add(instant)

    periodes = []
    for (lot, machine, mesure), instants in sorted(manquants.items()):
        precedents = sorted(instants)
        debut = dernier = precedents[0]
        for instant in [*precedents[1:], None]:
            if instant is not None and instant - dernier == HEURE:
                dernier = instant
                continue
            periodes.append(dict(
                bronze_run_id=lot, machine_id=machine, mesure=mesure,
                debut_utc=debut - HEURE, fin_utc=dernier,
                nombre_releves=int((dernier - debut) / HEURE) + 1,
            ))
            debut = dernier = instant

    trous = []
    for (lot, machine), instants in sorted(heures.items()):
        heures_triees = sorted(instants)
        for debut, fin in zip(heures_triees, heures_triees[1:]):
            instant = debut + HEURE
            while instant < fin:
                trous.append(dict(
                    bronze_run_id=lot, machine_id=machine, timestamp_attendu_utc=instant,
                    etat_machine="INCONNU",
                ))
                instant += HEURE
    return periodes, trous


def valeur_copy(valeur) -> str | None:
    if valeur is None:
        return None
    if isinstance(valeur, list):
        return json.dumps(valeur, ensure_ascii=False)
    if isinstance(valeur, bool):
        return str(valeur).lower()
    if isinstance(valeur, (datetime, date, time)):
        return valeur.isoformat()
    return str(valeur)


def publier_silver(compose: Path, donnees: dict[str, list[dict]]) -> None:
    """La transaction d’écriture ne cible que les tables fixes du schéma Silver."""
    if donnees.keys() != SCHEMAS.keys():
        raise ValueError("Jeu Silver incomplet.")
    with TemporaryFile() as flux:
        flux.write(b"BEGIN;\nCREATE SCHEMA IF NOT EXISTS silver;\n")
        for nom, schema in SCHEMAS.items():
            ddl = ", ".join(f'"{champ}" {type_sql}' for champ, type_sql in schema.items())
            champs = ", ".join(f'"{champ}"' for champ in schema)
            entete = (
                f"CREATE TABLE IF NOT EXISTS silver.{nom} ({ddl});\n"
                f"TRUNCATE TABLE silver.{nom};\n"
                f"COPY silver.{nom} ({champs}) FROM STDIN;\n"
            )
            flux.write(entete.encode())
            for ligne in donnees[nom]:
                valeurs = (encoder_copy(valeur_copy(ligne[champ])) for champ in schema)
                flux.write(("\t".join(valeurs) + "\n").encode())
            flux.write(b"\\.\n")
        flux.write(b"COMMIT;\n")
        flux.seek(0)
        charger_psql(compose, flux)


def ecrire_artefacts(dossier: Path, donnees: dict[str, list[dict]]) -> None:
    dossier.mkdir(parents=True, exist_ok=True)
    for nom in ("manifeste", "reemissions", "periodes_manquantes", "heures_sans_releve"):
        with (dossier / f"{nom}.csv").open("w", encoding="utf-8", newline="") as fichier:
            champs = list(SCHEMAS[nom])
            ecrire = csv.writer(fichier, lineterminator="\n")
            ecrire.writerow(champs)
            ecrire.writerows([valeur_copy(ligne[c]) for c in champs] for ligne in donnees[nom])

    echantillon = {
        nom: [
            {c: v for c, v in ligne.items() if c != "description"}
            for ligne in sorted(donnees[nom], key=lambda ligne: ligne["bronze_hash"])[:5]
        ]
        for nom in SOURCES
    }
    (dossier / "echantillon.json").write_text(
        json.dumps(echantillon, ensure_ascii=False, indent=2, default=valeur_copy) + "\n", encoding="utf-8"
    )
    telemetry = donnees["telemetry"]
    lignes = [
        "# Rapport qualité Silver", "", f"Contrat : {VERSION_CONTRAT}", "",
        "| Table | Bronze | Silver | Réémissions écartées |", "| --- | ---: | ---: | ---: |",
    ]
    for ligne in donnees["manifeste"]:
        lignes.append(f"| {ligne['source_table']} | {ligne['bronze_lignes']} | "
                      f"{ligne['silver_lignes']} | {ligne['reemissions_ecartees']} |")
    lignes.extend([
        "", f"- Relevés avec une mesure manquante : {sum(bool(l['mesures_manquantes']) for l in telemetry)}.",
        f"- Mesures manquantes : {sum(len(l['mesures_manquantes']) for l in telemetry)}. Aucune imputation.",
        f"- Périodes par mesure manquante : {len(donnees['periodes_manquantes'])}.",
        f"- Heures de relevé absentes dans les plages observées : {len(donnees['heures_sans_releve'])}.",
        f"- Relevés avec surcroît d’activité : {sum(l['surcroit_activite'] is True for l in telemetry)}. Ils restent en Silver.",
        f"- Relevés atypiques à revoir : {sum(bool(l['mesures_atypiques_a_revoir']) for l in telemetry)}. Aucun retrait.",
        "", "Chaque réémission trace sa position dans le CSV (hors en-tête), son hash et l’occurrence conservée.",
        "Les périodes se rapportent à l’heure précédente du relevé. Les limites physiques restent non évaluées.",
        "Le repérage exploratoire utilise un écart de trois écarts interquartiles au-delà de Q1 ou Q3, par machine et mesure.",
        "Le registre des décisions documente les règles et les interprétations métier.",
    ])
    (dossier / "rapport.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
