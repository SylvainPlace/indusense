"""Charge un instantané CSV ou SQL dans le schéma Bronze de PostgreSQL."""

import argparse
import csv
import hashlib
import hmac
import json
import os
import re
import subprocess
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from tempfile import TemporaryFile
from typing import BinaryIO
from uuid import UUID, uuid4

from sqlglot import exp, parse
from sqlglot.errors import ParseError, TokenError

from source_sql import DIALECTE_SQL, classer_colonne_sql, extraire_tables_sql

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
TABLES_MACHINE = ("machine", "maintenance")
type Valeur = str | None
type TableBronze = tuple[str, dict[str, str], Iterable[Sequence[Valeur]]]


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


def encoder_champs(champs: Sequence[Valeur]) -> bytes:
    """Encode une séquence ordonnée sans ambiguïté liée aux séparateurs."""
    return json.dumps(champs, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def transformer_ligne(
    ligne: Sequence[Valeur], types: dict[str, str], cle_hash: bytes,
    *, sel_operateur: bytes | None = None,
) -> list[Valeur]:
    """Ajoute les types et l’empreinte et pseudonymise si la source le demande."""
    empreinte = hmac.digest(cle_hash, encoder_champs(ligne), "sha256").hex()
    resultat = []
    for (colonne, type_colonne), valeur in zip(types.items(), ligne, strict=True):
        if sel_operateur is not None and colonne in CHAMPS_OPERATEUR and valeur:
            # Sépare les domaines nom et badge, même si une valeur se répète.
            valeur = hashlib.sha256(sel_operateur + b"\0" + encoder_champs([colonne, valeur])).hexdigest()
        resultat.extend((valeur, type_colonne))
    return [*resultat, empreinte]


def encoder_copy(valeur: Valeur) -> str:
    """Protège les caractères réservés du format texte de COPY."""
    if valeur is None:
        return r"\N"
    return valeur.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def valeur_sql(valeur: exp.Expr | None, contexte: str) -> Valeur:
    if valeur is None or isinstance(valeur, exp.Null):
        return None
    if isinstance(valeur, exp.Literal):
        return valeur.this
    if isinstance(valeur, exp.Neg) and isinstance(valeur.this, exp.Literal) and not valeur.this.is_string:
        return f"-{valeur.this.this}"
    if isinstance(valeur, exp.Boolean):
        return "true" if valeur.this else "false"
    raise ValueError(f"{contexte} : valeur SQL non littérale.")


def lire_tables_machine(source: Path) -> Iterator[tuple[str, dict[str, str], list[list[Valeur]]]]:
    """Lit les littéraux des INSERT dans l’ordre du schéma, sans exécuter le dump."""
    try:
        instructions = [i for i in parse(source.read_text(encoding="utf-8-sig"), read=DIALECTE_SQL) if i]
        tables = extraire_tables_sql(instructions)
        if tables.keys() != set(TABLES_MACHINE):
            raise ValueError("les tables machine et maintenance sont attendues.")
        for nom in TABLES_MACHINE:
            table = tables[nom]
            types = {col: classer_colonne_sql(d)[0] for col, d in table["definitions"].items()}
            lignes = [
                [valeur_sql(ligne.get(col), f"{nom}.{col}") for col in types]
                for ligne in table["lignes"]
            ]
            yield nom, types, lignes
    except (ValueError, ParseError, TokenError) as erreur:
        raise ValueError(f"{source.name} : {erreur}") from erreur


def ecrire_table_copy(
    flux: BinaryIO, nom_table: str, types: dict[str, str],
    lignes: Iterable[Sequence[Valeur]], *, run_id: UUID, autoriser_null: bool = False,
) -> int:
    table = f'"bronze"."{nom_table}"'
    colonnes = [nom for col in types for nom in (col, f"{col}_type")] + ["hash", "run_id"]
    if len(set(colonnes)) != len(colonnes) or any(
        not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", nom) for nom in colonnes
    ):
        raise ValueError(f"{nom_table} : noms de colonnes Bronze invalides ou en conflit.")
    definitions = ", ".join(
        f'"{nom}" TEXT' + ("" if autoriser_null and nom in types else " NOT NULL")
        for nom in colonnes[:-1]
    )
    noms_copy = ", ".join(f'"{nom}"' for nom in colonnes)
    entete = [
        f"CREATE TABLE IF NOT EXISTS {table} ({definitions}, run_id UUID NOT NULL);",
        f"TRUNCATE TABLE {table};",
        # Les tables des chargements précédents peuvent ne pas avoir cette colonne.
        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS run_id UUID;",
        f"ALTER TABLE {table} ALTER COLUMN run_id SET NOT NULL;",
        f"COPY {table} ({noms_copy}) FROM STDIN;",
    ]
    flux.write(("\n".join(entete) + "\n").encode("utf-8"))
    nombre_lignes = 0
    for ligne in lignes:
        texte = "\t".join(encoder_copy(valeur) for valeur in ligne)
        flux.write((texte + f"\t{run_id}\n").encode("utf-8"))
        nombre_lignes += 1
    if not nombre_lignes:
        raise ValueError(f"{nom_table} : aucune ligne à charger.")
    flux.write(b"\\.\n")
    return nombre_lignes


def lire_tables_bronze(source: Path, dataset: str) -> Iterator[TableBronze]:
    if dataset == "machine":
        yield from lire_tables_machine(source)
    else:
        types = TYPES_SOURCES[dataset]
        yield dataset, types, lire_csv_bronze(source, types)


def sha256_source(source: Path) -> str:
    with source.open("rb") as fichier:
        return hashlib.file_digest(fichier, "sha256").hexdigest()


def commit_git() -> Valeur:
    try:
        resultat = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return resultat.stdout.strip()


def ecrire_historique(
    flux: BinaryIO, run_id: UUID, volumes: Mapping[str, int],
    sources: Mapping[str, Path], empreintes: Mapping[Path, str],
) -> None:
    """Ajoute les entrées du lot à la transaction qui charge ses données."""
    flux.write(b"""CREATE TABLE IF NOT EXISTS bronze.ingestion_runs (
    run_id UUID NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    target_table TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_sha256 TEXT NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    git_commit TEXT,
    row_count BIGINT NOT NULL CHECK (row_count >= 0),
    PRIMARY KEY (run_id, target_table)
);
COPY bronze.ingestion_runs
    (run_id, target_table, source_file, source_sha256, git_commit, row_count) FROM STDIN;
""")
    revision = commit_git()
    for table, volume in volumes.items():
        source = sources[table]
        ligne = (str(run_id), table, source.name, empreintes[source], revision, str(volume))
        flux.write(("\t".join(encoder_copy(valeur) for valeur in ligne) + "\n").encode("utf-8"))
    flux.write(b"\\.\n")


def preparer_tables(
    flux: BinaryIO, tables: Iterable[TableBronze], *, run_id: UUID,
    sources: Mapping[str, Path], empreintes: Mapping[Path, str],
) -> dict[str, int]:
    """Prépare le chargement des tables et l’historique dans la même transaction."""
    flux.write(b'BEGIN;\nCREATE SCHEMA IF NOT EXISTS "bronze";\n')
    volumes = {
        nom: ecrire_table_copy(
            flux, nom, types, lignes, run_id=run_id, autoriser_null=nom in TABLES_MACHINE
        )
        for nom, types, lignes in tables
    }
    for source in dict.fromkeys(sources.values()):
        if sha256_source(source) != empreintes[source]:
            raise ValueError(f"{source.name} a changé pendant la préparation du chargement.")
    ecrire_historique(flux, run_id, volumes, sources, empreintes)
    flux.write(b"COMMIT;\n")
    flux.seek(0)
    return volumes


def preparer_chargement(
    flux: BinaryIO, source: Path, dataset: str, cle_hash: bytes,
    *, sel_operateur: bytes | None = None,
) -> dict[str, int]:
    def enrichir(types, lignes):
        for ligne in lignes:
            yield transformer_ligne(ligne, types, cle_hash, sel_operateur=sel_operateur)

    empreintes = {source: sha256_source(source)}
    noms = TABLES_MACHINE if dataset == "machine" else (dataset,)
    tables = (
        (nom, types, enrichir(types, lignes))
        for nom, types, lignes in lire_tables_bronze(source, dataset)
    )
    return preparer_tables(
        flux, tables, run_id=uuid4(),
        sources=dict.fromkeys(noms, source), empreintes=empreintes,
    )


def commande_psql(compose: Path, *arguments: str) -> list[str]:
    return [
        "docker", "compose", "-f", str(compose), "exec", "-T",
        "-e", "PGCLIENTENCODING=UTF8", "db", "sh", "-c",
        'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"',
        "psql", *arguments,
    ]


def charger_psql(compose: Path, commandes: BinaryIO) -> None:
    subprocess.run(commande_psql(compose), stdin=commandes, check=True)


def lire_secrets(
    dataset: str, environnement: Mapping[str, str] | None = None
) -> tuple[bytes, bytes | None]:
    variables = os.environ if environnement is None else environnement
    cle = variables.get("BRONZE_ROW_HASH_KEY", "").strip()
    if not cle:
        raise ValueError("BRONZE_ROW_HASH_KEY doit être non vide.")
    if dataset != "releves_incidents":
        return cle.encode("utf-8"), None
    sel = variables.get("BRONZE_OPERATOR_SALT", "").strip()
    if not sel or sel == cle:
        raise ValueError("BRONZE_OPERATOR_SALT doit être non vide et distincte de BRONZE_ROW_HASH_KEY.")
    return cle.encode("utf-8"), sel.encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=(*TYPES_SOURCES, "machine"), nargs="?", default="releves_incidents")
    parser.add_argument("--compose-file", type=Path, default=Path("../docker-compose.yml"))
    parser.add_argument("--source", type=Path)
    options = parser.parse_args()
    nom_source = "machine.sql.txt" if options.dataset == "machine" else f"{options.dataset}.csv"
    source = options.source or Path("datas") / nom_source
    try:
        cle_hash, sel_operateur = lire_secrets(options.dataset)
        # Valide le fichier complet avant de toucher à la table, avec une mémoire bornée.
        with TemporaryFile() as commandes:
            volumes = preparer_chargement(
                commandes, source, options.dataset, cle_hash, sel_operateur=sel_operateur
            )
            charger_psql(options.compose_file, commandes)
    except (ValueError, OSError, csv.Error, subprocess.CalledProcessError) as erreur:
        parser.exit(1, f"Échec du chargement Bronze : {erreur}\n")
    for table, nombre_lignes in volumes.items():
        print(f"{nombre_lignes} lignes chargées dans bronze.{table}.")


if __name__ == "__main__":
    main()
