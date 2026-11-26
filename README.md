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

## Charger les incidents dans Bronze

Depuis la racine d'Indusense, démarre le service PostgreSQL du Compose fourni dans le dossier parent :

```powershell
docker compose -f ../docker-compose.yml up -d --wait db
```

Crée une seule fois un fichier local `.env.bronze` avec deux secrets aléatoires distincts. Git ignore ce fichier. Garde les mêmes secrets pour obtenir les mêmes empreintes et pseudonymes au prochain chargement.

```powershell
uv run --locked python -c "from pathlib import Path; from secrets import token_hex; f = Path('.env.bronze').open('x'); print('BRONZE_OPERATOR_SALT=' + token_hex(32), file=f); print('BRONZE_ROW_HASH_KEY=' + token_hex(32), file=f); f.close()"
uv run --locked --env-file .env.bronze python bronze_incidents.py
```

La commande utilise `psql` dans le conteneur `db`. Chaque chargement remplace le contenu de `bronze.releves_incidents` dans une transaction. Le jeu fourni donne **1 245 lignes et 37 colonnes**. Chaque champ source est suivi de son champ `_type`, issu du notebook, et `hash` termine la ligne.

Les valeurs source restent en texte, y compris les champs vides et les zéros initiaux. Les noms et badges sont remplacés séparément par des SHA-256 salés. Le hash de ligne est un HMAC-SHA‑256 calculé sur les 18 valeurs d'origine, dans l'ordre de l'en-tête, sérialisées en tableau JSON UTF-8 compact. Les autres champs, dont `comment`, sont copiés tels quels. Les commentaires de la source fournie ont été contrôlés pour les mentions exactes des noms complets et badges connus.

```powershell
uv run --locked python -m unittest discover -s tests
```

## Charger la télémétrie dans Bronze

Avec le même service `db` et le fichier `.env.bronze` déjà préparé :

```powershell
uv run --locked --env-file .env.bronze python bronze.py telemetry
```

Le chargement remplace `bronze.telemetry` dans une transaction, indépendamment des incidents. Le fichier fourni donne **135 626 lignes et 15 colonnes** : sept champs sources, sept champs `_type` et `hash`. Les zéros, la représentation des mesures et les champs vides sont conservés. Seule la clé `BRONZE_ROW_HASH_KEY` est utilisée pour cette source. Un rejeu avec le même fichier et la même clé reproduit les empreintes.

## Charger les machines et la maintenance dans Bronze

```powershell
uv run --locked --env-file .env.bronze python bronze.py machine
```

Le chargeur et le notebook partagent la lecture du script avec SQLGlot. Le script source `datas/machine.sql.txt` est analysé sans être exécuté. La commande charge `bronze.machine` (15 lignes) et `bronze.maintenance` (115 lignes) dans une même transaction. Chaque table a 23 colonnes : 11 champs sources, leurs 11 champs `_type` et `hash`.

Les valeurs explicites des `INSERT` sont conservées en texte. Un `NULL` explicite ou une colonne absente de l’`INSERT` donne un `NULL` en Bronze. La chaîne vide reste distincte. Les valeurs par défaut du script ne sont pas évaluées. Le HMAC de ligne est calculé avec la même clé que pour la télémétrie, sur les valeurs dans l’ordre du schéma, avec les valeurs SQL absentes ou nulles encodées en `null` JSON.
