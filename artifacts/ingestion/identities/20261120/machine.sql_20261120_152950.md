# Carte d'identité — machine.sql.txt

- Source: `C:\Users\Sylvain\Desktop\Formation\indusense\datas\machine.sql.txt`
- Filsize: 22.95 Ko
- ProcessBeginAt: 15:29:50
- ProcessEndAt: 15:29:50
- Charset: utf-8
- Rows Number: 130
- Cols Number: 22
- Dialecte: PostgreSQL
- Instructions: 10
- Tables: 2

Les lignes comptées correspondent aux tuples des INSERT. Les statistiques portent sur les valeurs explicites. Le symbole — indique une statistique indisponible ou sans objet, notamment pour les champs alimentés par DEFAULT NOW().

## Table `machine`

- Rows Number: 15
- Cols Number: 11

### Column list

| Colname | SQL Type | Inferred Type | Raison du classement |
| --- | --- | --- | --- |
| machine_code | VARCHAR(16) | IDENTITY | Clé primaire |
| commissioning_date | DATE | DATE | Type déclaré |
| max_daily_capacity | INT | NUMERIC | Type déclaré |
| max_hourly_capacity_pieces | INT | NUMERIC | Type déclaré |
| model | VARCHAR(32) | TEXT | Type déclaré |
| production_line | VARCHAR(16) | TEXT | Type déclaré |
| location | VARCHAR(16) | TEXT | Type déclaré |
| criticality | VARCHAR(8) | TEXT | Type déclaré |
| is_active | BOOLEAN | BOOLEAN | Type déclaré |
| created_at | TIMESTAMPTZ | DATETIME | Type déclaré |
| updated_at | TIMESTAMPTZ | DATETIME | Type déclaré |

### Statistiques

| Colname | Min value | Max value | Mean value | Median value |
| --- | --- | --- | --- | --- |
| commissioning_date | 2019-07-23 | 2025-05-25 | — | — |
| max_daily_capacity | 750 | 1428 | 1054.8666666666666 | 1027.0 |
| max_hourly_capacity_pieces | 47 | 89 | 65.86666666666666 | 64.0 |
| created_at | — | — | — | — |
| updated_at | — | — | — | — |

## Table `maintenance`

- Rows Number: 115
- Cols Number: 11

### Column list

| Colname | SQL Type | Inferred Type | Raison du classement |
| --- | --- | --- | --- |
| maintenance_id | INT | IDENTITY | Clé primaire |
| machine_code | VARCHAR(16) | IDENTITY | Référence |
| maintenance_at | TIMESTAMPTZ | DATETIME | Type déclaré |
| maintenance_type | VARCHAR(16) | TEXT | Type déclaré |
| action_type | VARCHAR(32) | TEXT | Type déclaré |
| component | VARCHAR(64) | TEXT | Type déclaré |
| description | TEXT | TEXT | Type déclaré |
| related_incident_id | VARCHAR(16) | IDENTITY | Convention de nommage (_id) |
| duration_hours | DECIMAL(6, 2) | NUMERIC | Type déclaré |
| created_at | TIMESTAMPTZ | DATETIME | Type déclaré |
| updated_at | TIMESTAMPTZ | DATETIME | Type déclaré |

### Statistiques

| Colname | Min value | Max value | Mean value | Median value |
| --- | --- | --- | --- | --- |
| maintenance_at | 2025-06-15T06:00:00+00:00 | 2026-05-30T22:00:00+00:00 | — | — |
| duration_hours | 1.0 | 8.0 | 2.94304347826087 | 2.64 |
| created_at | — | — | — | — |
| updated_at | — | — | — | — |
