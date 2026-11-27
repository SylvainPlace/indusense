# Revue métier Bronze vers Silver

État au 27 novembre 2026 · Contrat appliqué : `silver-1.0`

Le Silver du lot Bronze `98941e5d-36b2-4b32-8245-7489c8e2ee87` est chargé dans PostgreSQL. Les décisions validées ci-dessous ont été appliquées au lot. Les signalements qui restent à discuter n’ont déclenché aucune exclusion. Les tables et fichiers Bronze sont restés intacts.

- [Notebook exécuté](../../ingestion.ipynb) · diagnostic Bronze, chargement Silver et contrôle des ressemblances.
- [Registre et dictionnaire des 47 colonnes](plan-et-decisions.md) · règles et points en attente.
- [Rapport qualité](../../artifacts/silver/silver-1.0/rapport.md) · [manifeste](../../artifacts/silver/silver-1.0/manifeste.csv) · [journal des réémissions](../../artifacts/silver/silver-1.0/reemissions.csv) · [périodes manquantes](../../artifacts/silver/silver-1.0/periodes_manquantes.csv).

## Bilan du lot

| Table | Lignes Bronze | Lignes Silver | Réémissions écartées du Silver |
| --- | ---: | ---: | ---: |
| Télémétrie | 135 626 | 134 280 | 1 346 |
| Incidents | 1 245 | 1 245 | 0 |
| Machines | 15 | 15 | 0 |
| Maintenance | 115 | 115 | 0 |
| **Total** | **137 001** | **135 655** | **1 346** |

- **Réémissions :** le Bronze contient 1 340 groupes, soit 2 686 lignes. Le Silver conserve la première occurrence du CSV pour chaque groupe. Le journal identifie les deux positions et les deux hash.
- **Manquants :** 2 793 relevés Silver sont conservés avec au moins une mesure à `NULL`. Les 2 812 valeurs absentes se répartissent entre la pression (982), la rotation (948) et la température (882), sur 364 périodes par machine et mesure. Aucune imputation. Aucune heure entière sans relevé dans les plages observées.
- **Activité :** 36 784 relevés Silver dépassent la capacité nominale horaire et sont signalés comme surcroît d’activité. Les 37 136 dépassements du diagnostic Bronze incluaient les réémissions. Le rapport recense aussi 1 392 relevés atypiques à examiner selon un critère statistique. Toutes ces lignes restent en Silver.
- **Références :** les 25 références de maintenance renseignées vers un incident sont résolues. Les 90 interventions sans incident associé restent à `NULL`, sans signalement.

## Décisions validées et points restant à examiner

| Point | Décision appliquée | Point ouvert |
| --- | --- | --- |
| M1 — Grain de la télémétrie | Même machine et même horodatage = réémission dans ce fichier. Garder la première occurrence dans l’ordre du CSV. | Examiner au cas par cas les clés des autres sources si un conflit apparaît. |
| M2 — Copies et conflits | Le journal trace les 1 346 réémissions écartées. Les quatre incidents similaires et les autres saisies rapprochées sont conservés. | Déterminer si plusieurs saisies décrivent la même anomalie et quelle preuve pourrait les relier. |
| M3 — Horaires | Les deux CSV utilisent UTC. La date et l’heure des incidents indiquent la saisie. Les cinq mesures télémétriques couvrent l’heure précédente. À 06:00 UTC, elles décrivent 05:00–06:00. | L’instant de l’anomalie n’est pas connu à partir du fichier d’incidents. |
| M4 — Unités et capacité | Température moyenne en °C, pression interne moyenne en bar, tension moyenne en V, rotation moyenne en tr/min et pièces en nombre entier sur l’heure précédente. Un dépassement de capacité nominale indique un surcroît d’activité. | Aucune limite physique n’a été validée. Les mesures atypiques sont conservées pour revue. |
| M5 — Manquants et formats | Garder les relevés incomplets, laisser les mesures à `NULL`, tracer les périodes et ne rien imputer. Signaler les heures sans relevé et indiquer un arrêt seulement s’il est documenté. | Cause des manquants et éventuels codes spéciaux à examiner sur les prochains lots. |
| M6 — Références et clés | Une intervention sans incident associé est valide. Une machine inconnue ou une clé inutilisable se traite au cas par cas, sans retrait automatique. | Aucune machine inconnue ni clé inutilisable n’a été détectée sur ce lot. Examiner le cas s’il apparaît. |
| M7 — Incidents et opérateurs | Les incidents sont saisis par les opérateurs. `severity` est leur appréciation, avec 5 comme niveau le plus grave. Pour les neuf indicateurs, 1 signifie « signalé » et 0 « non signalé ». `operator_name`, `operator_badge` et `comment` restent dans Bronze. | Libellés détaillés des niveaux et sens des autres codes métier si un usage les exige. |
| M8 — Traçabilité et livraison | Le notebook, les artefacts et les tables sont rattachés au lot par leur identifiant et les empreintes. Le manifeste, les registres et un échantillon sont dans le dépôt local. | La publication GitHub du Silver reste à faire. |

## Si une valeur ne peut pas être convertie

Une mesure vide reconnue comme manquante reste à `NULL`, avec sa période. Une référence inconnue ou un champ de clé manquant qui peut être représenté sans altérer sa valeur est signalé pour revue.

Si une **valeur non vide à convertir** ne respecte pas le contrat, par exemple une date invalide ou un nombre illisible, le traitement signale le champ et la valeur et **bloque la publication du lot Silver**. Il ne remplace pas la valeur par `NULL` et ne retire pas la ligne. Le lot Bronze reste disponible. Si un chargement échoue pendant l’écriture, la transaction Silver est annulée et le Silver déjà publié reste en place. Pour reprendre, faire valider la règle de traitement avec le métier, puis rejouer le lot.

## Exemples à montrer au métier

| Cas | Constat | Question restante |
| --- | --- | --- |
| `INC-000986` et `INC-000987` | Même machine, heure de saisie et contenu Silver. Même commentaire en Bronze, avec des paires de pseudonymes différentes. | Plusieurs saisies pour une même anomalie ou deux événements distincts ? |
| `INC-001052` et `INC-001053` | Même machine, heure de saisie et contenu Silver. Commentaires et paires de pseudonymes différents en Bronze. | Quel identifiant ou fait indépendant permet de relier les saisies ? |
| `INC-000107` et `INC-000108` | Une minute d’écart et mêmes indicateurs sur `MACH-03`. Sévérités 3 et 2. | Réévaluation du même incident ou autre anomalie ? |

Le diagnostic trouve 35 paires de saisies à 5 minutes ou moins, 91 à 15 minutes ou moins et 196 à une heure ou moins pour une même machine et les mêmes indicateurs, hors saisies simultanées. Ces seuils sont exploratoires et les comptages s’emboîtent. La décision SIL‑11 conserve toutes ces lignes.

Pour les points ouverts, consigner la règle exacte, son périmètre, la personne qui la valide, la date et le contrôle attendu. Les confirmations actuelles sont celles relayées dans l’échange métier. Aucun nom de responsable n’a été renseigné pour les accords.
