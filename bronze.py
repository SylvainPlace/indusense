"""Charge un instantané CSV dans le schéma Bronze de PostgreSQL."""

import argparse
import csv
import hashlib
import hmac
import json
import os
import subprocess
from collections.abc import Iterator, Sequence
from tempfile import TemporaryFile
from typing import BinaryIO
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

TYPES_TELEMETRIE = {
    "machine_id": "IDENTITY",
    "timestamp": "DATETIME",
    "temperature_c": "NUMERIC",
    "pressure_bar": "NUMERIC",
    "voltage_mean_v": "NUMERIC",
    "rotation_mean_rpm": "NUMERIC",
    "pieces_produced": "NUMERIC",
}
TYPES_SOURCES = {
    "releves_incidents": TYPES_INCIDENTS,
    "telemetry": TYPES_TELEMETRIE,
}
CHAMPS_OPERATEUR = frozenset({"operator_name", "operator_badge"})


def lire_csv_bronze(source: Path, types: dict[str, str]) -> Iterator[list[str]]:
    """Conserve les champs CSV sous forme de texte dans leur ordre d'origine."""
    with source.open(encoding="utf-8-sig", newline="") as fichier:
        lecteur = csv.reader(fichier, strict=True)
        if next(lecteur, None) != list(types):
            raise ValueError(f"{source.name} : en-tête différent du contrat Bronze.")
        for ligne in lecteur:
            if len(ligne) != len(types) or any("\x00" in valeur for valeur in ligne):
                raise ValueError(f"{source.name} : ligne CSV invalide à la ligne {lecteur.line_num}.")
            yield ligne


def encoder_champs(champs: Sequence[str]) -> bytes:
    """Encode une séquence ordonnée sans ambiguïté liée aux séparateurs."""
    return json.dumps(champs, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def transformer_ligne(
    ligne: list[str], types: dict[str, str], cle_hash: bytes,
    *, sel_operateur: bytes | None = None,
) -> list[str]:
    """Ajoute les types et l’empreinte et pseudonymise si la source le demande."""
    empreinte = hmac.digest(cle_hash, encoder_champs(ligne), "sha256").hex()
    resultat = []
    for (colonne, type_colonne), valeur in zip(types.items(), ligne, strict=True):
        if sel_operateur is not None and colonne in CHAMPS_OPERATEUR and valeur:
            # Sépare les domaines nom et badge, même si une valeur se répète.
            valeur = hashlib.sha256(sel_operateur + b"\0" + encoder_champs([colonne, valeur])).hexdigest()
        resultat.extend((valeur, type_colonne))
    return [*resultat, empreinte]


def encoder_copy(valeur: str) -> str:
    """Protège les caractères réservés du format texte de COPY."""
    return valeur.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def preparer_chargement(
    flux: BinaryIO, source: Path, dataset: str, cle_hash: bytes,
    *, sel_operateur: bytes | None = None,
) -> int:
    types = TYPES_SOURCES[dataset]
    table = f'"bronze"."{dataset}"'
    colonnes = [f'"{nom}"' for colonne in types for nom in (colonne, f"{colonne}_type")]
    colonnes.append('"hash"')
    definitions = ", ".join(f"{nom} TEXT NOT NULL" for nom in colonnes)
    # Le remplacement et COPY partagent la même transaction.
    entete = [
        "BEGIN;",
        'CREATE SCHEMA IF NOT EXISTS "bronze";',
        f"CREATE TABLE IF NOT EXISTS {table} ({definitions});",
        f"TRUNCATE TABLE {table};",
        f"COPY {table} ({', '.join(colonnes)}) FROM STDIN;",
    ]
    flux.write(("\n".join(entete) + "\n").encode("utf-8"))
    nombre_lignes = 0
    for ligne in lire_csv_bronze(source, types):
        valeurs = transformer_ligne(ligne, types, cle_hash, sel_operateur=sel_operateur)
        texte = "\t".join(encoder_copy(valeur) for valeur in valeurs)
        flux.write((texte + "\n").encode("utf-8"))
        nombre_lignes += 1
    if not nombre_lignes:
        raise ValueError(f"{source.name} : aucune ligne à charger.")
    flux.write(b"\\.\nCOMMIT;\n")
    flux.seek(0)
    return nombre_lignes


def charger_psql(compose: Path, commandes: BinaryIO) -> None:
    subprocess.run(
        [
            "docker", "compose", "-f", str(compose), "exec", "-T",
            "-e", "PGCLIENTENCODING=UTF8", "db", "sh", "-c",
            'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
        ],
        stdin=commandes,
        check=True,
    )


def lire_secrets(dataset: str) -> tuple[bytes, bytes | None]:
    cle = os.environ.get("BRONZE_ROW_HASH_KEY", "").strip()
    if not cle:
        raise ValueError("BRONZE_ROW_HASH_KEY doit être non vide.")
    if dataset != "releves_incidents":
        return cle.encode("utf-8"), None
    sel = os.environ.get("BRONZE_OPERATOR_SALT", "").strip()
    if not sel or sel == cle:
        raise ValueError("BRONZE_OPERATOR_SALT doit être non vide et distincte de BRONZE_ROW_HASH_KEY.")
    return cle.encode("utf-8"), sel.encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=TYPES_SOURCES, nargs="?", default="releves_incidents")
    parser.add_argument("--compose-file", type=Path, default=Path("../docker-compose.yml"))
    parser.add_argument("--source", type=Path)
    options = parser.parse_args()
    source = options.source or Path("datas") / f"{options.dataset}.csv"
    try:
        cle_hash, sel_operateur = lire_secrets(options.dataset)
        # Valide le fichier complet avant de toucher à la table, avec une mémoire bornée.
        with TemporaryFile() as commandes:
            nombre_lignes = preparer_chargement(
                commandes, source, options.dataset, cle_hash, sel_operateur=sel_operateur
            )
            charger_psql(options.compose_file, commandes)
    except (ValueError, OSError, csv.Error, subprocess.CalledProcessError) as erreur:
        parser.exit(1, f"Échec du chargement Bronze : {erreur}\n")
    print(f"{nombre_lignes} lignes chargées dans bronze.{options.dataset}.")


if __name__ == "__main__":
    main()
