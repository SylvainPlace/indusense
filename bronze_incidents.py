"""Charge un instantané des relevés d'incidents dans PostgreSQL."""

import argparse
import csv
import hashlib
import hmac
import json
import os
import subprocess
from collections.abc import Iterator, Sequence
from pathlib import Path

TYPES_INCIDENTS = {
    "incident_id": "IDENTITY",
    "date": "DATE",
    "time": "TIME",
    "operator_name": "TEXT",
    "machine_id": "IDENTITY",
    "severity": "NUMERIC",
    "operator_badge": "IDENTITY",
    "comment": "TEXT",
    "shift": "TEXT",
    "type_surchauffe": "BOOLEAN",
    "type_baisse_pression": "BOOLEAN",
    "type_vibration": "BOOLEAN",
    "type_bruit_mecanique": "BOOLEAN",
    "type_surconsommation": "BOOLEAN",
    "type_blocage_mecanique": "BOOLEAN",
    "type_alarme_capteur": "BOOLEAN",
    "type_arret_urgence": "BOOLEAN",
    "type_defaut_qualite": "BOOLEAN",
}

CHAMPS_OPERATEUR = {"operator_name", "operator_badge"}
TABLE_BRONZE = '"bronze"."releves_incidents"'


def lire_incidents(source: Path) -> Iterator[list[str]]:
    """Conserve les champs CSV sous forme de texte dans leur ordre d'origine."""
    with source.open(encoding="utf-8-sig", newline="") as fichier:
        lecteur = csv.reader(fichier, strict=True)
        if next(lecteur, None) != list(TYPES_INCIDENTS):
            raise ValueError(f"{source.name} : en-tête différent du contrat des incidents.")
        for ligne in lecteur:
            if len(ligne) != len(TYPES_INCIDENTS) or any("\x00" in valeur for valeur in ligne):
                raise ValueError(f"{source.name} : ligne CSV invalide à la ligne {lecteur.line_num}.")
            yield ligne


def encoder_champs(champs: Sequence[str]) -> bytes:
    """Encode une séquence ordonnée sans ambiguïté liée aux séparateurs."""
    return json.dumps(champs, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def transformer_incident(ligne: list[str], sel: bytes, cle_hash: bytes) -> list[str]:
    """Ajoute les types et l'empreinte de la ligne source, puis masque l'opérateur."""
    empreinte = hmac.digest(cle_hash, encoder_champs(ligne), "sha256").hex()
    resultat = []
    for (colonne, type_colonne), valeur in zip(TYPES_INCIDENTS.items(), ligne, strict=True):
        if colonne in CHAMPS_OPERATEUR and valeur:
            # Sépare les domaines nom et badge, même si une valeur se répète.
            valeur = hashlib.sha256(sel + b"\0" + encoder_champs([colonne, valeur])).hexdigest()
        resultat.extend((valeur, type_colonne))
    return [*resultat, empreinte]


def encoder_copy(valeur: str) -> str:
    """Protège les caractères réservés du format texte de COPY."""
    return valeur.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def preparer_chargement(source: Path, sel: bytes, cle_hash: bytes) -> tuple[bytes, int]:
    colonnes = [f'"{nom}"' for colonne in TYPES_INCIDENTS for nom in (colonne, f"{colonne}_type")]
    colonnes.append('"hash"')
    definitions = ", ".join(f"{nom} TEXT NOT NULL" for nom in colonnes)
    lignes = [
        "\t".join(encoder_copy(valeur) for valeur in transformer_incident(ligne, sel, cle_hash))
        for ligne in lire_incidents(source)
    ]
    if not lignes:
        raise ValueError(f"{source.name} : aucune ligne à charger.")
    # Le remplacement et COPY partagent la même transaction.
    commandes = [
        "BEGIN;",
        'CREATE SCHEMA IF NOT EXISTS "bronze";',
        f"CREATE TABLE IF NOT EXISTS {TABLE_BRONZE} ({definitions});",
        f"TRUNCATE TABLE {TABLE_BRONZE};",
        f"COPY {TABLE_BRONZE} ({', '.join(colonnes)}) FROM STDIN;",
        *lignes,
        r"\.",
        "COMMIT;",
        "",
    ]
    return "\n".join(commandes).encode("utf-8"), len(lignes)


def charger_psql(compose: Path, commandes: bytes) -> None:
    subprocess.run(
        [
            "docker", "compose", "-f", str(compose), "exec", "-T",
            "-e", "PGCLIENTENCODING=UTF8", "db", "sh", "-c",
            'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
        ],
        input=commandes,
        check=True,
    )


def lire_secrets() -> tuple[bytes, bytes]:
    sel = os.environ.get("BRONZE_OPERATOR_SALT", "").strip()
    cle = os.environ.get("BRONZE_ROW_HASH_KEY", "").strip()
    if not sel or not cle or sel == cle:
        raise ValueError("BRONZE_OPERATOR_SALT et BRONZE_ROW_HASH_KEY doivent être non vides et distincts.")
    return sel.encode("utf-8"), cle.encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose-file", type=Path, default=Path("../docker-compose.yml"))
    parser.add_argument("--source", type=Path, default=Path("datas/releves_incidents.csv"))
    options = parser.parse_args()
    try:
        sel, cle_hash = lire_secrets()
        commandes, nombre_lignes = preparer_chargement(options.source, sel, cle_hash)
        charger_psql(options.compose_file, commandes)
    except (ValueError, OSError, csv.Error, subprocess.CalledProcessError) as erreur:
        parser.exit(1, f"Échec du chargement Bronze : {erreur}\n")
    print(f"{nombre_lignes} lignes chargées dans bronze.releves_incidents.")


if __name__ == "__main__":
    main()
