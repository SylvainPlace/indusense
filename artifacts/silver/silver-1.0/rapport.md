# Rapport qualité Silver

Contrat : silver-1.0

| Table | Bronze | Silver | Réémissions écartées |
| --- | ---: | ---: | ---: |
| telemetry | 135626 | 134280 | 1346 |
| releves_incidents | 1245 | 1245 | 0 |
| machine | 15 | 15 | 0 |
| maintenance | 115 | 115 | 0 |

- Relevés avec une mesure manquante : 2793.
- Mesures manquantes : 2812. Aucune imputation.
- Périodes par mesure manquante : 364.
- Heures de relevé absentes dans les plages observées : 0.
- Relevés avec surcroît d’activité : 36784. Ils restent en Silver.
- Relevés atypiques à revoir : 1392. Aucun retrait.

Chaque réémission trace sa position dans le CSV (hors en-tête), son hash et l’occurrence conservée.
Les périodes se rapportent à l’heure précédente du relevé. Les limites physiques restent non évaluées.
Le repérage exploratoire utilise un écart de trois écarts interquartiles au-delà de Q1 ou Q3, par machine et mesure.
Le registre des décisions documente les règles et les interprétations métier.
