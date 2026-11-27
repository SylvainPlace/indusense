# Indusense — plan et décisions Bronze vers Silver

Version du dossier : 0.2 · 27 novembre 2026 · Plan avant implémentation

Ce dossier fixe les choix à discuter avant d’écrire le traitement Silver. Les constats ci-dessous ont été mesurés sur le Bronze disponible le 27 novembre. Une décision **proposée** doit encore être relue. Une question **ouverte** demande une réponse métier. Chaque modification du contrat sera datée et reliée à son motif et à ses preuves. Aucune ligne n’a été écartée et aucune transformation Silver n’a été appliquée.

## Portrait de départ

| Table Bronze | Fichier | Lignes | Hash de ligne distincts |
| --- | --- | ---: | ---: |
| `releves_incidents` | `releves_incidents.csv` | 1 245 | 1 245 |
| `telemetry` | `telemetry.csv` | 135 626 | 135 626 |
| `machine` | `machine.sql.txt` | 15 | 15 |
| `maintenance` | `machine.sql.txt` | 115 | 115 |
| **Total** | **3 fichiers** | **137 001** | — |

- La télémétrie contient 1 340 couples machine/horodatage répétés, concernant 2 686 lignes. Toutes les empreintes de ligne de la télémétrie sont distinctes. Ces répétitions ne suffisent donc pas à établir des copies techniques.
- La télémétrie contient 37 136 lignes où `pieces_produced` dépasse `max_hourly_capacity_pieces` pour la machine correspondante. La cadence, la période couverte par le compteur et la portée de la capacité déclarée restent à confirmer.
- La télémétrie contient 995 pressions vides, 958 vitesses de rotation vides et 894 températures vides. Ce sont des absences par champ. Une ligne peut apparaître dans plusieurs compteurs.
- Les références machine présentes correspondent au référentiel. Les 25 références explicites de maintenance vers un incident correspondent également. Les 90 références de maintenance non renseignées restent des absences.
- Dans le script SQL, certaines colonnes ont un défaut déclaré mais aucune valeur explicite dans les `INSERT`. Par exemple, `created_at` et `updated_at` restent à `NULL` dans Bronze.

## Registre des décisions

| ID | Statut | Décision et raison | Preuve à produire |
| --- | --- | --- | --- |
| SIL-01 | Proposée | Transformer un lot Bronze identifié par son `run_id`. Relever au départ son historique, les SHA‑256 des sources, les volumes et la version du traitement. Cela permet de comparer le résultat au lot réellement lu. | Manifeste par lot et par table, rapprochement avec `bronze.ingestion_runs`. |
| SIL-02 | Proposée | Conserver dans Silver la provenance de chaque ligne via la table source, le `run_id` et le hash Bronze. Deux copies exactes peuvent partager ces valeurs. Pour leur audit, compter les occurrences et documenter l’éventuel rang utilisé dans le lot. | Exemple de remontée d’une ligne et registre indiquant la multiplicité des copies. |
| SIL-03 | Proposée | Garder les identifiants sous forme de texte et convertir les mesures, dates et indicateurs selon le dictionnaire, avec les unités source connues. Conserver l’accès aux valeurs d’origine par le lien Bronze. Une conversion impossible reçoit un motif explicite. | Dictionnaire complet, exemples avant/après et journal des erreurs de conversion. |
| SIL-04 | Proposée, fuseau ouvert | Combiner la date et l’heure des incidents. Conserver les horodatages CSV sans fuseau jusqu’à confirmation de leur horloge source. Pour la maintenance, exploiter les décalages déjà explicites. Garder l’heure d’ingestion séparée de l’heure métier. | Cas de contrôle pour une date sans fuseau, un décalage explicite et une date invalide. |
| SIL-05 | Proposée, grain ouvert | Conserver les relevés dont le couple machine/horodatage se répète et les signaler pour revue. Ce couple est une clé candidate, car aucun identifiant de capteur ni règle de révision n’est confirmé. | Registre des 1 340 couples candidats pour le lot observé et contrôle des 2 686 lignes concernées. |
| SIL-06 | Proposée | Avec une clé métier validée, écarter une copie seulement si son contenu source est identique à celui de l’occurrence conservée. Pour la même clé et des contenus différents, consigner un conflit et attendre une règle de priorité. | Cas de test distinguant copie, conflit et deux observations légitimes au même instant. |
| SIL-07 | Proposée | Laisser les mesures manquantes à `NULL`. Consigner les erreurs de conversion. Si une colonne indispensable à l’identité de l’événement est inutilisable, mettre la ligne en quarantaine avec le motif. Une mesure facultative invalide peut rester dans une ligne retenue avec un drapeau. | Compteurs par colonne, motif par ligne écartée et cas de test pour les deux niveaux de gravité. |
| SIL-08 | Proposée, limites ouvertes | Signaler les dépassements de capacité pour revue. Conserver les mesures tant que l’unité, la cadence et la limite métier ne sont pas validées. Laisser les manquants sans estimation en l’absence de règle validée. | Indicateur de dépassement, décompte avant/après et décision métier datée avant toute exclusion ou imputation. |
| SIL-09 | Proposée | Conserver la pseudonymisation en Silver. Relire les champs libres avant publication et limiter les échantillons publics aux champs utiles à la vérification. | Contrôle de l’échantillon publié et absence de noms ou badges source en clair. |
| SIL-10 | Proposée | Publier le Silver via une branche de travail et une PR. Versionner le contrat, les règles, les artefacts et les résultats du notebook, en les rattachant au lot d’entrée. Le dataset complet sera produit dans PostgreSQL, avec un échantillon vérifiable dans Git. | Commit, identifiant du lot, artefacts lisibles et étapes de reproduction. |

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

| Sujet | Question | Comportement proposé en attendant |
| --- | --- | --- |
| Identité d’un relevé | Existe-t-il un identifiant de mesure ou de capteur, une séquence ou un ordre de révision ? | Garder les collisions de la clé candidate et les signaler. |
| Horloge des CSV | Quel est le fuseau de la télémétrie et de la date/heure des incidents ? | Conserver le temps local de la source et laisser le fuseau indéterminé. |
| Cadence et capacité | À quelle période se rapporte `pieces_produced` ? La capacité est-elle nominale ou une limite validée ? | Un dépassement déclenche un drapeau. |
| Unités et absences | La pression est-elle absolue ou relative ? Quels codes désignent une absence ou une panne de capteur ? | Conserver l’unité indiquée par la source. Traiter les champs vides comme absents et documenter tout autre code avant de le convertir. |
| Périodes sans mesure | Dispose-t-on des états machine et d’une durée maximale d’estimation validée ? | Conserver les trous. |

Les réponses sont à consigner avec la date, la personne ou la source qui les valide, les règles concernées et l’effet sur les résultats déjà produits.

## Ordre de réalisation et livrables

1. Capturer le manifeste et le portrait Bronze. Prouver les volumes, les SHA‑256, les absences et les répétitions du lot choisi.
2. Compléter le dictionnaire par colonne et annoter les règles validées ou suspendues. Donner une version au contrat avant de typer les données.
3. Exécuter les transformations approuvées par le métier et qualifier les quatre tables. Afficher dans le notebook le code appliqué, des valeurs avant/après et des exemples de décisions traçables.
4. Générer le journal des transformations, les registres de copies, conflits et quarantaines, ainsi que la liste des cas à revoir. Un registre vide doit dire clairement que le contrôle a été exécuté.
5. Produire le rapport qualité et un échantillon Silver versionné. Comparer les volumes et les manquants avant/après, expliquer les écarts et enregistrer la version du contrat et du traitement.
6. Vérifier les artefacts depuis un noyau neuf, puis ouvrir la PR avec le notebook exécuté et les documents de suivi.

Pour toute nouvelle règle, ajouter une entrée au registre avec son identifiant, son statut, les colonnes visées, la raison, l’alternative écartée si elle éclaire le choix, l’impact mesuré et le contrôle associé.

Références de formation : `14_bronze_vers_silver_guide_stagiaires-complete.md`, sections 2, 3 et 6, et `14_bronze_vers_silver_guide_stagiaires-didactique.md`, sections 2, 3 et 5. Les guides sont fournis dans le dossier parent du projet.
