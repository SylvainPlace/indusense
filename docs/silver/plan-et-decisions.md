# Indusense — plan et décisions Bronze vers Silver

Version du dossier : 0.8 · 27 novembre 2026 · Plan avant implémentation

Ce dossier fixe les choix à discuter avant d’écrire le traitement Silver. Les constats ci-dessous ont été mesurés sur le Bronze disponible le 27 novembre. Une décision **proposée** doit encore être relue. Une question **ouverte** demande une réponse métier. Chaque modification du contrat sera datée et reliée à son motif et à ses preuves. Aucune ligne n’a été écartée et aucune transformation Silver n’a été appliquée.

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

- La télémétrie contient 1 340 couples machine/horodatage répétés, concernant 2 686 lignes. Toutes les empreintes de ligne de la télémétrie sont distinctes. Ces répétitions ne suffisent donc pas à établir des copies techniques.
- La télémétrie contient 37 136 lignes où `pieces_produced` dépasse `max_hourly_capacity_pieces` pour la machine correspondante. Ce chiffre est mesuré sur le Bronze avant sélection de la première occurrence. Le compteur et la capacité sont tous deux horaires. Le métier interprète un dépassement comme un surcroît d’activité, sans exclusion.
- La télémétrie contient 995 pressions vides, 958 vitesses de rotation vides et 894 températures vides. Ce sont des absences par champ. Une ligne peut apparaître dans plusieurs compteurs.
- Les références machine présentes correspondent au référentiel. Les 25 références explicites de maintenance vers un incident correspondent également. Les 90 références de maintenance non renseignées restent des absences.
- Dans le script SQL, certaines colonnes ont un défaut déclaré mais aucune valeur explicite dans les `INSERT`. Par exemple, `created_at` et `updated_at` restent à `NULL` dans Bronze.

## Registre des décisions

| ID | Statut | Décision et raison | Preuve à produire |
| --- | --- | --- | --- |
| SIL-01 | Proposée | Transformer un lot Bronze identifié par son `run_id`. Relever au départ son historique, les SHA‑256 des sources, les volumes et la version du traitement. Cela permet de comparer le résultat au lot réellement lu. | Manifeste par lot et par table, rapprochement avec `bronze.ingestion_runs`. |
| SIL-02 | Proposée | Conserver dans Silver la provenance de chaque ligne via la table source, le `run_id` et le hash Bronze. Deux copies exactes peuvent partager ces valeurs. Pour leur audit, compter les occurrences et documenter l’éventuel rang utilisé dans le lot. | Exemple de remontée d’une ligne et registre indiquant la multiplicité des copies. |
| SIL-03 | Proposée | Garder les identifiants sous forme de texte et convertir les mesures, dates et indicateurs selon le dictionnaire, avec les unités source connues. Conserver l’accès aux valeurs d’origine par le lien Bronze. Une conversion impossible reçoit un motif explicite. | Dictionnaire complet, exemples avant/après et journal des erreurs de conversion. |
| SIL-04 | UTC et instant de saisie confirmés | Les deux CSV utilisent UTC. Combiner la date et l’heure des incidents dans un horodatage de saisie UTC. Séparer la saisie, le relevé et l’ingestion. Pour la maintenance, exploiter les décalages déjà explicites. | Vérifier qu’un horaire UTC garde la même heure et que l’horodatage d’incident est nommé comme un instant de saisie. |
| SIL-05 | Proposée, grain ouvert | Conserver les relevés dont le couple machine/horodatage se répète et les signaler pour revue. Ce couple est une clé candidate, car aucun identifiant de capteur ni règle de révision n’est confirmé. | Registre des 1 340 couples candidats pour le lot observé et contrôle des 2 686 lignes concernées. |
| SIL-06 | Proposée | Avec une clé métier validée, écarter une copie seulement si son contenu source est identique à celui de l’occurrence conservée. Pour la même clé et des contenus différents, consigner un conflit et attendre une règle de priorité. | Cas de test distinguant copie, conflit et deux observations légitimes au même instant. |
| SIL-07 | Proposée | Laisser les mesures manquantes à `NULL`. Consigner les erreurs de conversion. Si une colonne indispensable à l’identité de l’événement est inutilisable, mettre la ligne en quarantaine avec le motif. Une mesure facultative invalide peut rester dans une ligne retenue avec un drapeau. | Compteurs par colonne, motif par ligne écartée et cas de test pour les deux niveaux de gravité. |
| SIL-08 | Fenêtre horaire et interprétation confirmées | Le nombre de pièces produites par heure est comparable à la capacité horaire déclarée. Un dépassement indique un surcroît d’activité et la ligne est conservée. L’imputation reste à valider. | Recompter les surcroîts d’activité après sélection de la première occurrence. Vérifier l’alignement sur l’heure UTC qui précède le relevé lors des rapprochements temporels. Documenter tout changement ou toute estimation avant application. |
| SIL-09 | Proposée | Conserver la pseudonymisation en Silver. Relire les champs libres avant publication et limiter les échantillons publics aux champs utiles à la vérification. | Contrôle de l’échantillon publié et absence de noms ou badges source en clair. |
| SIL-10 | Proposée | Publier le Silver via une branche de travail et une PR. Versionner le contrat, les règles, les artefacts et les résultats du notebook, en les rattachant au lot d’entrée. Le dataset complet sera produit dans PostgreSQL, avec un échantillon vérifiable dans Git. | Commit, identifiant du lot, artefacts lisibles et étapes de reproduction. |

## Précisions métier sur les mesures et les horodatages

Les dernières précisions remplacent les hypothèses précédentes sur l’heure de l’anomalie, l’heure couverte par le compteur, la pression relative et le caractère instantané des mesures. Le nombre de pièces produites pendant l’heure précédente est rapporté au moment du relevé. À 06:00 UTC, il couvre la période de 05:00 à 06:00 UTC. La température et la pression interne sont des moyennes sur un intervalle dont les bornes restent à préciser.

Le rapprochement antérieur entre champs vides et signalements d’arrêt comparait les horaires saisis. Il ne permet pas d’écarter un lien avec un arrêt réel. Le lien vers l’incident reste consultable, avec l’heure de saisie comme repère.

## Validation métier avant toute modification

Le diagnostic peut repérer, compter et illustrer les écarts en lecture seule. Il marque les cas **à valider**. Toute règle qui change une valeur, son interprétation ou la composition du jeu Silver doit être discutée avec le métier et recevoir un accord explicite avant application. Cela couvre le typage avec perte, la déduplication, la quarantaine, l’imputation, la conversion d’unité, l’attribution d’un fuseau et la sélection d’une version en cas de conflit. En attendant cet accord, les lignes et leurs valeurs sont conservées dans Bronze et les propositions restent dans le rapport.

Pour chaque règle proposée, présenter le lot concerné, le filtre exact, des exemples repérables par table, run_id et hash Bronze, le volume touché, l’effet attendu et l’option de conserver les données en l’état. Enregistrer la décision métier avec le responsable, la date, le périmètre, le statut et la version de la règle. Si le responsable ou le critère manque, la règle reste en attente.

## Motifs à examiner avec le métier

| Code | Déclencheur et constat | Décision à faire valider |
| --- | --- | --- |
| COPIE_EXACTE | Même clé métier validée et même contenu source. Un hash répété sert à repérer les candidats, puis le contenu est comparé. Aucun hash de ligne répété dans le lot observé. | Confirmer que les lignes sont des réémissions du même événement. Définir quelle occurrence conserver et comment tracer les autres avant tout retrait. |
| CONFLIT_CLE | Même clé métier validée et contenus différents. | Déterminer si ce sont des révisions ou plusieurs événements. Désigner la source ou la version de référence. Toute mise à l’écart du jeu Silver demande un accord métier. |
| CLE_ABSENTE_OU_INVALIDE | Un champ indispensable manque ou son format empêche d’identifier l’événement, par exemple une date non interprétable. Un identifiant textuel avec des zéros initiaux ne relève pas de ce cas. | Valider les champs indispensables, leurs formats et les cas où l’on peut retrouver la clé. Définir quand la mise en quarantaine est justifiée. |
| REFERENCE_INCONNUE | Une référence renseignée ne correspond à aucun enregistrement du référentiel. Les 25 références d’incident renseignées en maintenance correspondent sur le lot observé. | Confirmer que le référentiel couvre le lot et définir les cas où une référence manquante rend la ligne inutilisable. Une référence facultative laissée vide relève d’un manquant. |
| CONVERSION_IMPOSSIBLE | Une valeur non vide échoue à la conversion proposée, par exemple une mesure textuelle hors du format convenu. | Valider le format, les codes spéciaux et le caractère obligatoire du champ. Toute correction, substitution par NULL ou exclusion exige une décision explicite. |
| VALEUR_IMPOSSIBLE | Une mesure enfreint une limite physique ou métier explicitement validée, dans l’unité et le contexte convenus. | Faire valider la limite, les régimes concernés et l’action. Une valeur rare ou un dépassement de capacité présumée déclenche une revue. |

Trois situations observées sont **des signaux à examiner**. Le plan n’en déduit aucun retrait :

- Les 2 686 lignes qui partagent l’un des 1 340 couples machine/horodatage répétés restent visibles. Il faut d’abord confirmer ce qu’une ligne de télémétrie représente.
- Les 37 136 dépassements de la capacité horaire déclarée restent visibles. Il faut d’abord confirmer la période couverte par le nombre de pièces et la portée de la capacité.
- Les valeurs vides en télémétrie et les dates absentes du script SQL restent en l’état. Une absence dans un champ facultatif ne suffit pas à écarter une ligne.

## Bilan des lignes après validation des règles

| Statut | Quand l’utiliser | Ce qu’il faut conserver |
| --- | --- | --- |
| Retenue | Ligne retenue selon le contrat. Un drapeau peut signaler un point encore en revue. | Provenance, valeurs et drapeaux éventuels. |
| Copie écartée | Copie visée par une règle de déduplication validée. | Occurrence retenue, comparaison, nombre de copies et référence à l’accord métier. |
| Conflit non retenu | Cas mis en attente hors du jeu Silver selon une règle validée. | Valeurs contradictoires ou lien Bronze, règle, version et décision attendue. |
| Quarantaine | Cas visé par un motif bloquant validé. | Colonne, valeur source ou lien Bronze, raison, règle et référence à l’accord métier. |

À vérifier par table et par lot : **lignes Bronze reçues = retenues + copies écartées + conflits non retenus + quarantaine**. Le statut « à valider » est un drapeau de revue. Il n’entre pas dans les exclusions et une ligne retenue qui le porte compte une seule fois.

## Questions métier à valider

Le [dossier de revue métier](revue-metier.md) regroupe les exemples, les questions à trancher et la fiche de décisions à remplir pendant la réunion.

| Sujet | Question | Comportement proposé en attendant |
| --- | --- | --- |
| Identité d’un relevé | Existe-t-il un identifiant de mesure ou de capteur, une séquence ou un ordre de révision ? | Garder les collisions de la clé candidate et les signaler. |
| Horloge des CSV | UTC confirmé pour les deux CSV. Les incidents sont horodatés au moment de la saisie. | Proposer des champs explicitement nommés en UTC et distinguer l’heure de saisie de l’heure réelle de l’anomalie. |
| Cadence et capacité | Le compteur couvre l’heure précédente. La capacité est horaire. | Comparer le nombre horaire à la capacité et signaler un surcroît d’activité. Aligner les rapprochements sur l’heure précédant le relevé. |
| Unités, fenêtres et absences | La pression interne est en bar. Température et pression sont des moyennes. Quelles sont les bornes exactes de leur intervalle et quels codes désignent une absence ou une panne de capteur ? | Conserver les valeurs et unités sources. Traiter les champs vides comme absents et documenter tout autre code avant de le convertir. |
| Périodes sans mesure | Dispose-t-on des états machine et d’une durée maximale d’estimation validée ? | Conserver les trous. |

Les réponses sont à consigner avec la date, la personne ou la source qui les valide, les règles concernées et l’effet sur les résultats déjà produits.

## Dictionnaire Silver proposé

**Statut commun : à valider avec le métier.** Les types indiqués sont des cibles PostgreSQL. Les unités tirées des noms de colonnes sont des indices à confirmer. « — » signifie qu’aucune unité physique ne s’applique. Les noms cibles restent ceux des sources, sauf proposition explicite. Le dictionnaire couvre les 47 colonnes sources. Il ne déclenche aucun chargement, changement de valeur ou retrait de ligne.

Le diagnostic distingue les chaînes vides de `NULL` et conserve les textes tels quels. Avant toute conversion, le métier doit confirmer les formats, les codes d’absence et les champs obligatoires. Une valeur illisible pourra être signalée avec sa provenance. Son remplacement ou son exclusion demande une règle approuvée.

### Relevés d’incidents — 18 colonnes

| Colonne Bronze | Type Silver proposé | Unité ou format source | Règle proposée | À valider avec le métier |
| --- | --- | --- | --- | --- |
| `incident_id` | `TEXT` | — | Garder le code intact, zéros compris. Clé candidate de l’incident. | Unicité entre lots, réouvertures et révisions d’un incident. |
| `date` | `DATE` | `AAAA-MM-JJ` | Interpréter la date civile. Conserver la provenance Bronze. | Date attribuée automatiquement lors de la saisie. Le moment de l’anomalie peut être antérieur. |
| `time` | `TIME WITHOUT TIME ZONE` | `HH:MM` | Interpréter l’heure de saisie UTC à la précision de la minute. | Confirmer la précision disponible si une analyse exige les secondes. |
| `operator_name` | `TEXT` | Pseudonyme SHA‑256 salé | Garder le pseudonyme Bronze si l’usage le justifie. | Utilité analytique, accès et politique de publication. |
| `machine_id` | `TEXT` | Code machine | Garder le texte. Proposer le rapprochement avec `machine.machine_code`. | Stabilité du code et traitement des références inconnues. |
| `severity` | `SMALLINT` | Score ordinal, valeurs observées 2 à 5 | Lire le score entier. Conserver la valeur et signaler les codes hors du domaine approuvé. | Échelle complète, définition de chaque niveau et sens de l’ordre. |
| `operator_badge` | `TEXT` | Pseudonyme SHA‑256 salé | Garder le pseudonyme Bronze si nécessaire. Éviter de déduire l’identité à partir du badge seul. | Badges partagés ou réattribués, finalité et accès. |
| `comment` | `TEXT` | Texte libre | Conserver le texte dans un usage autorisé. Relire avant toute publication. | Données identifiantes éventuelles, accès et intérêt métier. |
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
| `temperature_c` | `NUMERIC` | °C, moyenne sur un intervalle | Lire le décimal sans arrondi. Garder les absences et les pics visibles. | Bornes de l’intervalle, emplacement du capteur et précision. |
| `pressure_bar` | `NUMERIC` | bar, pression interne moyenne sur un intervalle | Lire le décimal sans conversion d’unité. | Bornes de l’intervalle et référence instrumentale si une conversion l’exige. |
| `voltage_mean_v` | `NUMERIC` | V d’après le nom | Lire la moyenne fournie, sans la recalculer. | Fenêtre de moyenne, tension mesurée et unité. |
| `rotation_mean_rpm` | `NUMERIC` | tr/min d’après le nom | Lire la moyenne fournie, sans imputer les valeurs vides. | Fenêtre de moyenne, sens de zéro et régime machine. |
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
| `related_incident_id` | `TEXT` | Référence facultative | Garder les codes renseignés. Une absence ne désigne aucun incident. | Couverture du lien, caractère facultatif et gestion des références inconnues. |
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
| Date et SHA‑256 du lot d’entrée | `TIMESTAMP WITH TIME ZONE` et `TEXT` | Reprendre le manifeste de lot pour tracer l’ingestion. La date métier reste distincte de la date de chargement. |

Les domaines déclarés dans le script et les valeurs observées sont des éléments de discussion. Pour chaque règle approuvée, renseigner dans le registre le responsable, la date, le périmètre, la preuve et la version du contrat.

## Ordre de réalisation et livrables

1. Capturer le manifeste et le portrait Bronze. Prouver les volumes, les SHA‑256, les absences et les répétitions du lot choisi.
2. Compléter le dictionnaire par colonne et annoter les règles validées ou suspendues. Donner une version au contrat avant de typer les données.
3. Exécuter les transformations approuvées par le métier et qualifier les quatre tables. Afficher dans le notebook le code appliqué, des valeurs avant/après et des exemples de décisions traçables.
4. Générer le journal des transformations, les registres de copies, conflits et quarantaines, ainsi que la liste des cas à revoir. Un registre vide doit dire clairement que le contrôle a été exécuté.
5. Produire le rapport qualité et un échantillon Silver versionné. Comparer les volumes et les manquants avant/après, expliquer les écarts et enregistrer la version du contrat et du traitement.
6. Vérifier les artefacts depuis un noyau neuf, puis ouvrir la PR avec le notebook exécuté et les documents de suivi.

Pour toute nouvelle règle, ajouter une entrée au registre avec son identifiant, son statut, les colonnes visées, la raison, l’alternative écartée si elle éclaire le choix, l’impact mesuré et le contrôle associé.

Références de formation : `14_bronze_vers_silver_guide_stagiaires-complete.md`, sections 2, 3 et 6, et `14_bronze_vers_silver_guide_stagiaires-didactique.md`, sections 2, 3 et 5. Les guides sont fournis dans le dossier parent du projet.
