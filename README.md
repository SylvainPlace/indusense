# Indusense

Le notebook `ingestion.ipynb` génère les cartes d’identité Markdown des deux CSV et du script PostgreSQL du sprint 1.

## Préparer l’environnement

Depuis la racine du dépôt, avec [uv](https://docs.astral.sh/uv/) installé :

```shell
uv python install 3.15
uv sync --locked
uv run --locked python -m ipykernel install --sys-prefix --name indusense --display-name "Python (indusense)"
```

Place les trois fichiers fournis dans `datas/`, au même niveau que le notebook :

- `releves_incidents.csv`
- `telemetry.csv`
- `machine.sql.txt`

## Exécuter le notebook

1. Ouvre la racine du dépôt dans VS Code avec les extensions **Python** et **Jupyter**.
2. Ouvre `ingestion.ipynb` et sélectionne le noyau **Python (indusense)** de l’environnement `.venv`.
3. Redémarre le noyau, puis lance **Tout exécuter**. Le notebook affiche les chemins des rapports générés.

Les cartes sont écrites dans `artifacts/ingestion/identities/AAAAMMJJ/` au format `nom_AAAAMMJJ_HHMMSS.md`. La date et l’heure correspondent au début de l’analyse de chaque source.

## Vérifier les cartes

| Source | Résultat attendu |
| --- | --- |
| `releves_incidents.csv` | 1 245 lignes, 18 colonnes |
| `telemetry.csv` | 135 626 lignes, 7 colonnes |
| `machine.sql.txt` | 10 instructions PostgreSQL, 15 lignes dans les `INSERT` de `machine` et 115 dans ceux de `maintenance`, 11 colonnes par table |

Chaque carte indique le chemin de la source, sa taille, les heures de traitement, l’encodage et le type de chaque colonne. Les valeurs manquantes sont exclues des statistiques. Le notebook analyse le SQL sans exécuter le script. Les statistiques SQL portent sur les valeurs explicites des `INSERT`, et les valeurs calculées en base comme `DEFAULT NOW()` sont signalées comme indisponibles.

## Chargement Bronze

Consulte la section « Étape 2 — Charger les sources dans Bronze » dans [ingestion.ipynb](ingestion.ipynb).
