# Carte d'identité — machine.sql.txt

- Source: `C:\Users\Sylvain\Desktop\Formation\indusense\datas\machine.sql.txt`
- Filsize: 22.95 Ko
- ProcessBeginAt: 14:28:00
- ProcessEndAt: 14:28:00
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

| Colname | SQL Type | Inferred Type |
| --- | --- | --- |
| machine_code | VARCHAR(16) | IDENTITY |
| commissioning_date | DATE | DATE |
| max_daily_capacity | INT | NUMERIC |
| max_hourly_capacity_pieces | INT | NUMERIC |
| model | VARCHAR(32) | TEXT |
| production_line | VARCHAR(16) | TEXT |
| location | VARCHAR(16) | TEXT |
| criticality | VARCHAR(8) | TEXT |
| is_active | BOOLEAN | BOOLEAN |
| created_at | TIMESTAMPTZ | DATETIME |
| updated_at | TIMESTAMPTZ | DATETIME |

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

| Colname | SQL Type | Inferred Type |
| --- | --- | --- |
| maintenance_id | INT | IDENTITY |
| machine_code | VARCHAR(16) | IDENTITY |
| maintenance_at | TIMESTAMPTZ | DATETIME |
| maintenance_type | VARCHAR(16) | TEXT |
| action_type | VARCHAR(32) | TEXT |
| component | VARCHAR(64) | TEXT |
| description | TEXT | TEXT |
| related_incident_id | VARCHAR(16) | IDENTITY |
| duration_hours | DECIMAL(6, 2) | NUMERIC |
| created_at | TIMESTAMPTZ | DATETIME |
| updated_at | TIMESTAMPTZ | DATETIME |

### Statistiques

| Colname | Min value | Max value | Mean value | Median value |
| --- | --- | --- | --- | --- |
| maintenance_at | 2025-06-15T06:00:00+00:00 | 2026-05-30T22:00:00+00:00 | — | — |
| duration_hours | 1.0 | 8.0 | 2.94304347826087 | 2.64 |
| created_at | — | — | — | — |
| updated_at | — | — | — | — |
