"""Inspection des définitions et des INSERT PostgreSQL avec SQLGlot."""

from sqlglot import exp

DIALECTE_SQL = "postgres"
TYPES_SQL_NUMERIQUES = {"SMALLINT", "INT", "BIGINT", "DECIMAL", "FLOAT", "DOUBLE"}


def extraire_tables_sql(instructions: list[exp.Expr]) -> dict:
    tables = {}
    for instruction in instructions:
        if not isinstance(instruction, exp.Create) or instruction.kind != "TABLE":
            continue
        schema = instruction.this
        if not isinstance(schema, exp.Schema):
            raise ValueError(f"Colonnes non déclarées pour la table {schema.name}.")
        nom_table = schema.this.sql(dialect=DIALECTE_SQL)
        tables[nom_table] = {
            "definitions": {
                colonne.name: colonne for colonne in schema.expressions
                if isinstance(colonne, exp.ColumnDef)
            },
            "lignes": [],
        }

    for instruction in instructions:
        if not isinstance(instruction, exp.Insert):
            continue
        cible = instruction.this
        table = cible.this if isinstance(cible, exp.Schema) else cible
        nom_table = table.sql(dialect=DIALECTE_SQL)
        if nom_table not in tables or not isinstance(instruction.expression, exp.Values):
            raise ValueError(f"INSERT non pris en charge pour {nom_table}.")
        donnees = tables[nom_table]
        definitions = donnees["definitions"]
        noms = [colonne.name for colonne in cible.expressions] if isinstance(
            cible, exp.Schema
        ) else list(definitions)
        if len(noms) != len(set(noms)) or not set(noms) <= definitions.keys():
            raise ValueError(f"Colonnes INSERT invalides pour {nom_table}.")
        for ligne in instruction.expression.expressions:
            if len(ligne.expressions) != len(noms):
                raise ValueError(f"Nombre de valeurs INSERT incorrect pour {nom_table}.")
            donnees["lignes"].append(dict(zip(noms, ligne.expressions, strict=True)))
    return tables


def classer_colonne_sql(colonne: exp.ColumnDef) -> tuple[str, str]:
    contraintes = tuple(contrainte.kind for contrainte in colonne.constraints)
    if any(isinstance(contrainte, exp.PrimaryKeyColumnConstraint) for contrainte in contraintes):
        return "IDENTITY", "Clé primaire"
    if any(isinstance(contrainte, exp.Reference) for contrainte in contraintes):
        return "IDENTITY", "Référence"
    if colonne.name.endswith("_id"):
        return "IDENTITY", "Convention de nommage (_id)"

    type_sql = colonne.kind.this.name
    if type_sql in TYPES_SQL_NUMERIQUES:
        return "NUMERIC", "Type déclaré"
    type_colonne = {
        "BOOLEAN": "BOOLEAN", "DATE": "DATE", "TIME": "TIME",
        "TIMESTAMP": "DATETIME", "TIMESTAMPTZ": "DATETIME",
    }.get(type_sql, "TEXT")
    return type_colonne, "Type déclaré"
