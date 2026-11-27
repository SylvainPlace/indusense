# Indusense — plan et décisions Bronze vers Silver

Version du dossier : 1.1 · 27 novembre 2026 · Contrat appliqué : silver-1.0

Ce dossier distingue les règles appliquées au lot Silver, les contrôles exploratoires et les décisions encore attendues. Les constats portent sur le lot du 27 novembre. Le Bronze a été diagnostiqué en lecture seule. Le Silver est déjà chargé dans PostgreSQL.

## Diagnostic disponible dans le notebook

La section « Étape 3 — Diagnostic Silver en lecture seule » du [notebook d’ingestion](../../ingestion.ipynb) contient le manifeste du lot, le bilan des motifs et des exemples rattachés au lot et au hash de la ligne Bronze. Le notebook réutilise la base locale démarrée. Le rechargement Bronze est désactivé par défaut.

Le diagnostic vérifie les formats sondés, les clés candidates, les références et les absences. Il signale les dépassements de capacité déclarée pour revue et laisse les limites physiques non validées au statut « Non évalué ». Les données et les motifs constatés restent distincts des décisions métier.

## Portrait de départ

| Table Bronze | Fichier | Lignes | Hash de ligne distincts |
| --- | --- | ---: | ---: |
| `releves_incidents` | `releves_incidents.csv` | 1 245 | 1 245 |
| `telemetry` | `telemetry.csv` | 135 626 | 135 626 |
| `machine` | `machine.sql.txt` | 15 | 15 |
| `maintenance` | `machine.sql.txt` | 115 | 115 |
| **Total** | **3 fichiers** | **137 001** | — |

- La télémétrie contient 1 340 couples machine/horodatage répétés, concernant 2 686 lignes. Toutes les empreintes de ligne de la télémétrie sont distinctes. Le métier a confirmé qu’il s’agit de réémissions pour ce fichier, même lorsque les valeurs diffèrent.
- La télémétrie contient 37 136 lignes où `pieces_produced` dépasse `max_hourly_capacity_pieces` pour la machine correspondante. Ce chiffre est mesuré sur le Bronze avant sélection de la première occurrence. Le compteur et la capacité sont tous deux horaires. Le métier interprète un dépassement comme un surcroît d’activité, sans exclusion.
- La télémétrie contient 995 pressions vides, 958 vitesses de rotation vides et 894 températures vides. Ce sont des absences par champ. Une ligne peut apparaître dans plusieurs compteurs.
- Les références machine présentes correspondent au référentiel. Les 25 références explicites de maintenance vers un incident correspondent également. Les 90 références de maintenance non renseignées restent des absences.
- Dans le script SQL, certaines colonnes ont un défaut déclaré mais aucune valeur explicite dans les `INSERT`. Par exemple, `created_at` et `updated_at` restent à `NULL` dans Bronze.

## Registre des décisions

| ID | Statut | Décision et raison | Preuve à produire |
| --- | --- | --- | --- |
| SIL-01 | Appliquée au lot | Vérifier le volume du lot Bronze et conserver son identifiant, le SHA‑256 des sources et la version du contrat dans le manifeste Silver. | Quatre entrées du manifeste concordent avec les tables et l’historique Bronze. |
| SIL-02 | Appliquée au lot | Conserver le lot et le hash Bronze par ligne. Pour la télémétrie, conserver aussi le numéro d’enregistrement du CSV. | Le journal relie chaque réémission à l’occurrence conservée. |
| SIL-03 | Appliquée pour les formats du lot | Garder les identifiants en texte et convertir les valeurs selon le contrat. Une valeur non vide à convertir qui ne respecte pas le format bloque la publication du lot pour revue. | Types PostgreSQL et provenance vérifiés dans le notebook. Les extensions du contrat restent soumises à validation. |
| SIL-04 | UTC et instant de saisie confirmés | Les deux CSV utilisent UTC. Combiner la date et l’heure des incidents dans un horodatage de saisie UTC. Séparer la saisie, le relevé et l’ingestion. Pour la maintenance, exploiter les décalages déjà explicites. | Vérifier qu’un horaire UTC garde la même heure et que l’horodatage d’incident est nommé comme un instant de saisie. |
| SIL-05 | Appliquée à telemetry.csv | Dans ce fichier, un même couple `(machine_id, timestamp)` représente une réémission. Garder la première occurrence dans l’ordre du CSV, même si les valeurs ultérieures diffèrent. | SHA‑256 et ordre du CSV vérifiés : 134 280 relevés conservés et 1 346 réémissions journalisées. |
| SIL-06 | Règle télémétrie validée, autres sources à revoir au cas par cas | La télémétrie applique SIL-05. Une copie ou un conflit dans une autre source fait l’objet d’une revue avant toute exclusion. | Tracer la ligne conservée et les réémissions. Vérifier que les autres sources ne subissent aucune déduplication automatique. |
| SIL-07 | Maintien des relevés et absence d’imputation validés | Une clé inutilisable ou une référence machine inconnue est signalée et n’entraîne pas d’exclusion automatique. Une maintenance sans incident associé est valide, avec `related_incident_id` à `NULL` et sans signalement. Conserver les relevés avec mesures manquantes à `NULL`, sans imputation, et tracer les périodes. | 2 793 relevés incomplets conservés, 364 périodes tracées et 90 maintenances sans incident conservées sans signalement. |
| SIL-08 | Fenêtre horaire et interprétation confirmées | Le nombre de pièces produites par heure est comparable à la capacité horaire déclarée. Un dépassement indique un surcroît d’activité et la ligne est conservée. Les mesures manquantes restent à `NULL`, sans imputation. | 36 784 surcroîts d’activité après sélection de la première occurrence. Aucun retrait. Les rapprochements utilisent l’heure qui précède le relevé UTC. |
| SIL-09 | Validée pour les incidents | `operator_name`, `operator_badge` et `comment` restent uniquement dans Bronze. Le lien de provenance permet de retrouver le commentaire si nécessaire. | Vérifier leur absence des colonnes Silver et des échantillons Silver publiés. |
| SIL-10 | Silver et artefacts produits, publication GitHub à faire | Le lot Silver complet est chargé dans PostgreSQL. Le notebook exécuté, le manifeste, les registres, le rapport et l’échantillon sont versionnés sur la branche de travail. | Liens et volumes vérifiés contre PostgreSQL. |
| SIL-11 | Conservation validée, lien entre incidents à examiner | Garder les quatre incidents qui se ressemblent sans modification. Les autres paires rapprochées restent elles aussi visibles. Un horaire de saisie commun ou proche ne suffit pas à établir une identité d’événement. | Exemples et comptages enregistrés dans le notebook. Comparer l’identité réelle des incidents avec le métier. |

## Précisions métier sur les mesures et les horodatages

Les dernières précisions remplacent les hypothèses précédentes sur l’heure de l’anomalie, l’heure couverte par le compteur, la pression relative et le caractère instantané des mesures. Le nombre de pièces produites pendant l’heure précédente est rapporté au moment du relevé. À 06:00 UTC, il couvre la période de 05:00 à 06:00 UTC. La température, la pression interne, la tension et la rotation sont des moyennes sur cette même heure précédente. Les cinq champs de télémétrie couvrent donc la période de 05:00 à 06:00 pour un relevé à 06:00 UTC.

Le rapprochement antérieur entre champs vides et signalements d’arrêt comparait les horaires saisis. Il ne permet pas d’écarter un lien avec un arrêt réel. Le lien vers l’incident reste consultable, avec l’heure de saisie comme repère.

## Validation métier avant toute modification

Le diagnostic peut repérer, compter et illustrer les écarts en lecture seule. Il marque les cas **à valider**. Toute règle qui change une valeur, son interprétation ou la composition du jeu Silver doit être discutée avec le métier et recevoir un accord explicite avant application. Cela couvre le typage avec perte, la déduplication, la quarantaine, l’imputation, la conversion d’unité, l’attribution d’un fuseau et la sélection d’une version en cas de conflit. En attendant cet accord, les lignes et leurs valeurs sont conservées dans Bronze et les propositions restent dans le rapport.

Pour chaque règle proposée, présenter le lot concerné, le filtre exact, des exemples repérables par table, run_id et hash Bronze, le volume touché, l’effet attendu et l’option de conserver les données en l’état. Enregistrer la décision métier avec le responsable, la date, le périmètre, le statut et la version de la règle. Si le responsable ou le critère manque, la règle reste en attente.

## Traitement des conversions impossibles

Une mesure vide reconnue comme absente reste à `NULL`. Une clé manquante ou une référence inconnue peut être signalée sans écarter sa ligne. Si une **valeur non vide qui doit être convertie** est illisible selon le contrat, le traitement indique le champ et la valeur et bloque la publication du lot. Il ne substitue aucune valeur et n’écarte aucune ligne sur ce motif. Les sources restent en Bronze.

Une erreur de préparation empêche l’écriture. En cas d’échec dans la transaction PostgreSQL, les écritures Silver sont annulées et les tables précédemment publiées restent en place. La reprise exige une décision métier sur le cas puis un rejeu du lot.

## Motifs à examiner avec le métier

| Code | Déclencheur et constat | Décision à faire valider |
| --- | --- | --- |
| COPIE_EXACTE | Même clé métier validée et même contenu source. Un hash répété sert à repérer les candidats, puis le contenu est comparé. Aucun hash de ligne répété dans le lot observé. | Confirmer que les lignes sont des réémissions du même événement. Définir quelle occurrence conserver et comment tracer les autres avant tout retrait. |
| CONFLIT_CLE | Même clé métier validée et contenus différents. | Déterminer si ce sont des révisions ou plusieurs événements. Désigner la source ou la version de référence. Toute mise à l’écart du jeu Silver demande un accord métier. |
| CLE_ABSENTE_OU_INVALIDE | Un champ indispensable manque ou son format empêche d’identifier l’événement, par exemple une date non interprétable. Un identifiant textuel avec des zéros initiaux ne relève pas de ce cas. | Valider les champs indispensables, leurs formats et les cas où l’on peut retrouver la clé. Définir quand la mise en quarantaine est justifiée. |
| REFERENCE_INCONNUE | Une référence renseignée ne correspond à aucun enregistrement du référentiel. Les 25 références d’incident renseignées en maintenance correspondent sur le lot observé. | Confirmer que le référentiel couvre le lot et définir les cas où une référence manquante rend la ligne inutilisable. Une référence facultative laissée vide relève d’un manquant. |
| CONVERSION_IMPOSSIBLE | Une valeur non vide échoue à la conversion proposée, par exemple une mesure textuelle hors du format convenu. | Valider le format, les codes spéciaux et le caractère obligatoire du champ. Toute correction, substitution par NULL ou exclusion exige une décision explicite. |
| VALEUR_IMPOSSIBLE | Une mesure enfreint une limite physique ou métier explicitement validée, dans l’unité et le contexte convenus. | Faire valider la limite, les régimes concernés et l’action. Une valeur rare ou un dépassement de capacité présumée déclenche une revue. |

Le diagnostic Bronze a conservé toutes les lignes. Le traitement Silver a appliqué la règle validée aux réémissions de télémétrie uniquement.

- Les 2 686 lignes réparties dans 1 340 groupes de réémissions restent visibles en Bronze. Après vérification du SHA‑256 et de l’ordre du CSV, 1 346 réémissions ont été écartées du Silver et 134 280 relevés conservés.
- Le diagnostic Bronze comptait 37 136 dépassements. En Silver, 36 784 relevés sont signalés comme surcroît d’activité au regard de la capacité nominale horaire. Tous sont conservés.
- Les valeurs vides en télémétrie et les dates absentes du script SQL restent en l’état. Une absence dans un champ facultatif ne suffit pas à écarter une ligne.

## Bilan des lignes après validation des règles

Pour le lot publié : **137 001 lignes Bronze = 135 655 lignes Silver + 1 346 réémissions écartées**. Aucune exclusion pour conflit ni quarantaine n’a été appliquée. Le [rapport qualité](../../artifacts/silver/silver-1.0/rapport.md) détaille le rapprochement par table.

| Statut | Quand l’utiliser | Ce qu’il faut conserver |
| --- | --- | --- |
| Retenue | Ligne retenue selon le contrat. Un drapeau peut signaler un point encore en revue. | Provenance, valeurs et drapeaux éventuels. |
| Copie ou réémission écartée | Ligne visée par une règle de déduplication validée. | Occurrence retenue, comparaison, nombre de copies et référence à l’accord métier. |
| Conflit non retenu | Cas mis en attente hors du jeu Silver selon une règle validée. | Valeurs contradictoires ou lien Bronze, règle, version et décision attendue. |
| Quarantaine | Cas visé par un motif bloquant validé. | Colonne, valeur source ou lien Bronze, raison, règle et référence à l’accord métier. |

À vérifier par table et par lot : **lignes Bronze reçues = retenues + copies ou réémissions écartées + conflits non retenus + quarantaine**. Le statut « à valider » est un drapeau de revue. Il n’entre pas dans les exclusions et une ligne retenue qui le porte compte une seule fois.

## Questions métier à valider

Le [dossier de revue métier](revue-metier.md) regroupe les exemples, les questions à trancher et la fiche de décisions à remplir pendant la réunion.

| Sujet | Question | Comportement proposé en attendant |
| --- | --- | --- |
| Identité d’un relevé | Pour la télémétrie, le couple machine/UTC et la priorité à la première ligne du CSV sont confirmés. | Appliquer SIL-05 uniquement au fichier de télémétrie et tracer les réémissions. |
| Horloge des CSV | UTC confirmé pour les deux CSV. Les incidents sont horodatés au moment de la saisie. | Proposer des champs explicitement nommés en UTC et distinguer l’heure de saisie de l’heure réelle de l’anomalie. |
| Cadence et capacité | Le compteur couvre l’heure précédente. La capacité est horaire. | Comparer le nombre horaire à la capacité et signaler un surcroît d’activité. Aligner les rapprochements sur l’heure précédant le relevé. |
| Unités, fenêtres et absences | Pression interne en bar. Les moyennes de température, pression, tension et rotation couvrent l’heure précédente. Les motifs exacts des absences restent inconnus. | Conserver les unités confirmées : °C, bar, V et tr/min. Les mesures manquantes restent à `NULL`, sans imputation. |
| Périodes sans mesure | Signaler toute heure sans relevé. Préciser l’état d’arrêt lorsqu’il est connu. | Signaler le trou et indiquer l’état inconnu si aucune information fiable n’existe. |

Les réponses sont à consigner avec la date, la personne ou la source qui les valide, les règles concernées et l’effet sur les résultats déjà produits.

## Dictionnaire Silver proposé

**Statut : décisions confirmées signalées dans le registre. Les autres propositions restent à valider.** Les types indiqués sont des cibles PostgreSQL. Les unités tirées des noms de colonnes sont des indices à confirmer. « — » signifie qu’aucune unité physique ne s’applique. Les noms cibles restent ceux des sources, sauf proposition explicite. Le dictionnaire couvre les 47 colonnes sources. Il ne déclenche aucun chargement, changement de valeur ou retrait de ligne.

Le diagnostic distingue les chaînes vides de `NULL` et conserve les textes tels quels. Avant toute conversion, le métier doit confirmer les formats, les codes d’absence et les champs obligatoires. Une valeur illisible pourra être signalée avec sa provenance. Son remplacement ou son exclusion demande une règle approuvée.

### Relevés d’incidents — 18 colonnes

Les incidents sont saisis par les opérateurs. Pour leurs neuf indicateurs, 1 signifie « signalé » et 0 « non signalé ». Un zéro ne prouve pas l’absence du phénomène.

| Colonne Bronze | Type Silver proposé | Unité ou format source | Règle proposée | À valider avec le métier |
| --- | --- | --- | --- | --- |
| `incident_id` | `TEXT` | — | Garder le code intact, zéros compris. Clé candidate de l’incident. | Unicité entre lots, réouvertures et révisions d’un incident. |
| `date` | `DATE` | `AAAA-MM-JJ` | Interpréter la date civile. Conserver la provenance Bronze. | Date attribuée automatiquement lors de la saisie. Le moment de l’anomalie peut être antérieur. |
| `time` | `TIME WITHOUT TIME ZONE` | `HH:MM` | Interpréter l’heure de saisie UTC à la précision de la minute. | Confirmer la précision disponible si une analyse exige les secondes. |
| `operator_name` | Bronze uniquement | Pseudonyme SHA‑256 salé | Conserver le pseudonyme dans Bronze. | Exclu du Silver par décision métier. |
| `machine_id` | `TEXT` | Code machine | Garder le texte. Proposer le rapprochement avec `machine.machine_code`. | Stabilité du code et traitement des références inconnues. |
| `severity` | `SMALLINT` | Appréciation ordinale de l’opérateur. Valeurs observées 2 à 5. | Garder le score. Le niveau 5 est le plus grave. | Libellés détaillés des niveaux si un usage en a besoin. |
| `operator_badge` | Bronze uniquement | Pseudonyme SHA‑256 salé | Conserver le pseudonyme dans Bronze. | Exclu du Silver par décision métier. |
| `comment` | Bronze uniquement | Texte libre | Conserver le commentaire dans Bronze. Le lien de provenance permet de le consulter. | Exclu du Silver par décision métier. |
| `shift` | `TEXT` | Code de poste | Garder les codes observés `matin`, `apres-midi`, `nuit`. | Horaires, postes traversant minuit et référentiel de libellés. |
| `type_surchauffe` | `BOOLEAN` | Indicateur `0/1` | Proposer `1 → true`, `0 → false`, valeur absente conservée comme inconnue. | Critère de surchauffe et sens d’un zéro. |
| `type_baisse_pression` | `BOOLEAN` | Indicateur `0/1` | Appliquer la même proposition de conversion binaire. | Seuil ou constat qui déclenche la baisse de pression. |
| `type_vibration` | `BOOLEAN` | Indicateur `0/1` | Traiter comme indicateur d’incident, sans en déduire une mesure de vibration. | Signalement opérateur, diagnostic ou alerte de capteur. |
| `type_bruit_mecanique` | `BOOLEAN` | Indicateur `0/1` | Appliquer la proposition de conversion binaire. | Définition du bruit anormal et fiabilité du signalement. |
| `type_surconsommation` | `BOOLEAN` | Indicateur `0/1` | Appliquer la proposition de conversion binaire. | Grandeur de référence et période d’observation. |
| `type_blocage_mecanique` | `BOOLEAN` | Indicateur `0/1` | Appliquer la proposition de conversion binaire. | Définition d’un blocage et lien avec l’arrêt machine. |
| `type_alarme_capteur` | `BOOLEAN` | Indicateur `0/1` | Garder l’indicateur sans déduire la cause de l’alarme. | Distinction entre une alarme valide et un défaut de capteur. |
| `type_arret_urgence` | `BOOLEAN` | Indicateur `0/1` | Garder l’indicateur sans en déduire la durée de l’arrêt. | Arrêt déclenché ou confirmé, et règle de codage du zéro. |
| `type_defaut_qualite` | `BOOLEAN` | Indicateur `0/1` | Appliquer la proposition de conversion binaire. | Critère de défaut qualité et possibilité de plusieurs indicateurs par incident. |

### Télémétrie — 7 colonnes

| Colonne Bronze | Type Silver proposé | Unité ou format source | Règle proposée | À valider avec le métier |
| --- | --- | --- | --- | --- |
| `machine_id` | `TEXT` | Code machine | Garder le code. Rapprocher du référentiel avec la correspondance approuvée. | Stabilité du code et présence éventuelle d’un identifiant de capteur. |
| `timestamp` | `TIMESTAMP WITH TIME ZONE` | Horodatage du relevé à la seconde, UTC confirmé par le métier | Donner le type PostgreSQL avec fuseau en préservant l’heure UTC. | Confirmer les bornes temporelles des mesures associées au relevé. |
| `temperature_c` | `NUMERIC` | °C, moyenne de l’heure précédente | Lire le décimal sans arrondi. Garder les absences et les pics visibles. | Fenêtre confirmée : 05:00–06:00 pour un relevé à 06:00 UTC. |
| `pressure_bar` | `NUMERIC` | bar, pression interne moyenne de l’heure précédente | Lire le décimal sans arrondi. Conserver l’unité et la référence instrumentale source. | Fenêtre confirmée : 05:00–06:00 pour un relevé à 06:00 UTC. |
| `voltage_mean_v` | `NUMERIC` | V, moyenne de l’heure précédente | Lire le décimal sans arrondi. Conserver la moyenne fournie. | Fenêtre confirmée : 05:00–06:00 pour un relevé à 06:00 UTC. |
| `rotation_mean_rpm` | `NUMERIC` | tr/min, moyenne de l’heure précédente | Lire le décimal sans arrondi. Conserver la moyenne fournie. Les mesures manquantes restent à `NULL`, sans imputation. | Fenêtre confirmée : 05:00–06:00 pour un relevé à 06:00 UTC. |
| `pieces_produced` | `BIGINT` | Nombre entier de pièces produites pendant l’heure précédente | Lire la valeur entière. Signaler un surcroît d’activité au-delà de la capacité horaire sans écarter la ligne. | Fenêtre confirmée : à 06:00 UTC, production de 05:00 à 06:00 UTC. |

### Référentiel machine — 11 colonnes

| Colonne Bronze | Type Silver proposé | Unité ou format source | Règle proposée | À valider avec le métier |
| --- | --- | --- | --- | --- |
| `machine_code` | `TEXT` | Code machine | Garder la clé primaire déclarée dans le SQL sous forme de texte. | Réutilisation des codes et rapprochement historique. |
| `commissioning_date` | `DATE` | `AAAA-MM-JJ` | Lire la date de mise en service déclarée. | Date de première mise en service ou de remise en service. |
| `max_daily_capacity` | `INTEGER` | Capacité par jour, unité à confirmer | Lire l’entier déclaré. Utiliser la contrainte source positive comme point à vérifier. | Pièces par jour ou autre unité, régime de référence et capacité nominale. |
| `max_hourly_capacity_pieces` | `INTEGER` | Pièces/heure d’après le nom | Lire l’entier déclaré. Le comparer à la télémétrie à titre de diagnostic. | Conditions métier et éventuelles variations de la capacité déclarée. Un dépassement horaire indique un surcroît d’activité. |
| `model` | `TEXT` | Code ou libellé de modèle | Conserver le libellé source. Poser les regroupements en revue. | Catalogue des modèles et équivalences de libellés. |
| `production_line` | `TEXT` | Code de ligne de production | Garder le code. | Affectations successives et dates de validité. |
| `location` | `TEXT` | Code ou libellé de localisation | Garder la localisation déclarée. | Niveau du référentiel et suivi des déplacements. |
| `criticality` | `TEXT` | Codes SQL `LOW`, `MEDIUM`, `HIGH` | Conserver les codes déclarés. Documenter les codes inattendus. | Sens des niveaux et validité dans le temps. |
| `is_active` | `BOOLEAN` | État déclaré, absent des `INSERT` du lot | Lire un état explicite s’il existe. Conserver l’absence actuelle. | Définition de « active », date de référence et usage éventuel du défaut SQL. |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | Horaire SQL avec fuseau, absent du lot | Interpréter seulement un horodatage explicite. | Sémantique de création et disponibilité d’une date source fiable. |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | Horaire SQL avec fuseau, absent du lot | Interpréter seulement un horodatage explicite. | Sémantique de mise à jour et règle pour les versions successives. |

### Maintenance — 11 colonnes

| Colonne Bronze | Type Silver proposé | Unité ou format source | Règle proposée | À valider avec le métier |
| --- | --- | --- | --- | --- |
| `maintenance_id` | `TEXT` | Identifiant déclaré entier dans le SQL | Garder l’identifiant comme code. Clé primaire déclarée. | Unicité entre extractions et révisions d’une intervention. |
| `machine_code` | `TEXT` | Code machine | Garder la référence déclarée vers `machine.machine_code`. | Traitement d’une intervention dont la machine est inconnue. |
| `maintenance_at` | `TIMESTAMP WITH TIME ZONE` | Décalage explicite dans la source | Interpréter le décalage pour comparer les instants. Garder le texte original accessible dans Bronze. | Début, fin ou date de saisie de l’intervention. |
| `maintenance_type` | `TEXT` | Codes SQL `proactive`, `reactive` | Garder le code déclaré. Signaler les valeurs hors vocabulaire approuvé. | Définitions, autres catégories et recodage éventuel. |
| `action_type` | `TEXT` | Code d’action | Garder le code. | Catalogue des actions et regroupements autorisés. |
| `component` | `TEXT` | Libellé de composant | Garder le texte, accents compris. | Référentiel équipement et correspondances entre libellés. |
| `description` | `TEXT` | Texte libre | Conserver le texte dans un usage autorisé. Relire avant publication. | Données identifiantes éventuelles, accès et intérêt métier. |
| `related_incident_id` | `TEXT` | Référence facultative | Garder les codes renseignés. Une maintenance sans incident est valide. Conserver `NULL` sans signalement. | Traiter une référence renseignée inconnue au cas par cas. |
| `duration_hours` | `NUMERIC` | Heures, précision SQL à deux décimales | Lire la durée en heures sans arrondi supplémentaire. | Durée d’intervention ou d’arrêt, recouvrements et traitement des valeurs atypiques. |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | Horaire SQL avec fuseau, absent du lot | Conserver l’absence en attendant une valeur explicite. | Horodatage de création de l’intervention ou de son enregistrement. |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | Horaire SQL avec fuseau, absent du lot | Conserver l’absence en attendant une valeur explicite. | Horodatage fiable pour départager des révisions. |

### Champs techniques et dérivations proposées

| Provenance ou champ cible | Type proposé | Règle et point à valider |
| --- | --- | --- |
| `bronze_run_id` depuis `run_id` | `UUID` | Conserver le lien avec `bronze.ingestion_runs` et confirmer la politique d’historique Bronze. |
| `bronze_hash` depuis `hash` | `TEXT` | Recopier le hash Bronze. Les lignes identiques peuvent le partager. Valider un identifiant d’occurrence si le suivi doit distinguer deux copies exactes. |
| Colonnes `_type` du Bronze | Étiquettes de provenance | Conserver leur accès dans Bronze. Les types PostgreSQL du Silver seront définis par le contrat approuvé. |
| `incident_recorded_at_utc` depuis `date` et `time` | `TIMESTAMP WITH TIME ZONE` | Proposer un horodatage combiné de la saisie. Pour une analyse temporelle, vérifier à quel moment cette information était disponible. |
| Date et SHA‑256 du lot d’entrée | `TIMESTAMP WITH TIME ZONE` et `TEXT` | Reprendre le manifeste de lot pour tracer l’ingestion. La date métier reste distincte de la date de chargement. Le manifeste Silver conserve le SHA‑256. La date de chargement Bronze se retrouve dans `bronze.ingestion_runs` en reliant le lot et la table. |

Les domaines déclarés dans le script et les valeurs observées sont des éléments de discussion. Pour chaque règle approuvée, renseigner dans le registre le responsable, la date, le périmètre, la preuve et la version du contrat.

## Règle validée pour les mesures manquantes

Après sélection de la première occurrence, le lot de télémétrie contient 134 280 relevés. Le métier valide de conserver les 2 793 relevés incomplets : 982 pressions, 948 vitesses de rotation et 882 températures restent à `NULL`. Le registre des périodes précise la machine, la mesure, les bornes UTC et le nombre de relevés concernés. La cause reste inconnue.

Le [notebook](../../ingestion.ipynb) exécute le traitement du contrat `silver-1.0`. Les tables complètes sont en PostgreSQL et les [artefacts du lot](../../artifacts/silver/silver-1.0/) rassemblent le manifeste, les réémissions, les périodes, un échantillon et le rapport qualité. Les données Bronze restent consultables avec leur lot et leur hash.

## Incidents semblables à présenter au métier

Sur le lot Bronze `98941e5d-36b2-4b32-8245-7489c8e2ee87`, deux paires ont le même contenu métier en Silver en dehors de leur identifiant. **Les quatre lignes sont conservées sans modification.** Le [notebook](../../ingestion.ipynb) montre les résultats du contrôle de similarité en lecture seule.

| Incidents | Machine | Heure de saisie UTC | Sévérité | Constat en Bronze |
| --- | --- | --- | ---: | --- |
| `INC-000986`, `INC-000987` | `MACH-13` | 26 mars 2026 à 15:11 | 3 | Même commentaire. Deux paires de pseudonymes opérateur différentes. |
| `INC-001052`, `INC-001053` | `MACH-05` | 11 avril 2026 à 23:38 | 3 | Commentaires et paires de pseudonymes opérateur différents. |

À demander au métier : les opérateurs ont-ils saisi plusieurs signalements pour une même anomalie, ou ont-ils signalé des anomalies distinctes ? Préciser le signal fiable qui permettrait de relier deux incidents. L’heure enregistrée est celle de la saisie. La règle de réémission de la télémétrie ne s’applique pas aux incidents.

En excluant les saisies au même instant, le contrôle retrouve **35 paires à 5 minutes ou moins**, **91 à 15 minutes ou moins** et **196 à une heure ou moins**, sur une même machine et avec les mêmes indicateurs. Les volumes sont cumulatifs et une ligne peut appartenir à plusieurs paires. Par exemple, `INC-000107` et `INC-000108` sont saisis à une minute d’intervalle sur `MACH-03`, avec des sévérités 3 et 2. C’est un cas à discuter, sans retrait ni fusion automatique.

### Contrôles complémentaires sur le même lot

- Les clés contrôlées sont uniques dans les quatre tables : machine/horodatage pour les 134 280 relevés Silver, identifiant pour les 1 245 incidents et les 115 maintenances, code pour les 15 machines. Dans les référentiels machine et maintenance, aucun contenu métier entièrement identique hors identifiant n’a été trouvé.
- Sur 131 116 paires complètes d’heures consécutives d’une même machine, deux passent les seuils exploratoires suivants : au plus 0,1 °C, 0,1 bar, 0,5 V et 10 tr/min d’écart, avec le même nombre de pièces. En doublant ces seuils, le contrôle retrouve 30 paires. Aucune mesure complète ne répète à l’identique les cinq valeurs sur la même machine hors horodatage. Les relevés comparés couvrent des heures distinctes et restent en Silver.
- Exemple de télémétrie : sur MACH-15, le 22 août 2025 à 05:00 puis à 06:00 UTC, les températures sont 57,554 et 57,534 °C et le nombre de pièces est de 61 pour chacun des deux intervalles.
- Aucun groupe d’interventions de maintenance sur une même machine au même instant n’a été détecté.

Les seuils de proximité servent uniquement à illustrer les ressemblances. Les quatre incidents, les paires rapprochées et les relevés de télémétrie sont conservés. Les contrôles ont été effectués en lecture seule.

## Ordre de réalisation et livrables

1. Capturer le manifeste et le portrait Bronze. Prouver les volumes, les SHA‑256, les absences et les répétitions du lot choisi.
2. Compléter le dictionnaire par colonne et annoter les règles validées ou suspendues. Donner une version au contrat avant de typer les données.
3. Exécuter les transformations approuvées par le métier et qualifier les quatre tables. Afficher dans le notebook le code appliqué, des valeurs avant/après et des exemples de décisions traçables.
4. Générer le journal des transformations, les registres de copies, conflits et quarantaines, ainsi que la liste des cas à revoir. Un registre vide doit dire clairement que le contrôle a été exécuté.
5. Produire le rapport qualité et un échantillon Silver versionné. Comparer les volumes et les manquants avant/après, expliquer les écarts et enregistrer la version du contrat et du traitement.
6. Vérifier les artefacts depuis un noyau neuf, puis ouvrir la PR avec le notebook exécuté et les documents de suivi.

Pour toute nouvelle règle, ajouter une entrée au registre avec son identifiant, son statut, les colonnes visées, la raison, l’alternative écartée si elle éclaire le choix, l’impact mesuré et le contrôle associé.

Références de formation : `14_bronze_vers_silver_guide_stagiaires-complete.md`, sections 2, 3 et 6, et `14_bronze_vers_silver_guide_stagiaires-didactique.md`, sections 2, 3 et 5. Les guides sont fournis dans le dossier parent du projet.
