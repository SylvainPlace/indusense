# Revue métier Bronze vers Silver

Dossier de préparation · 27 novembre 2026 · Décisions en attente

Cette réunion doit valider le contrat Silver en une seule fois. Le diagnostic porte sur le lot Bronze `98941e5d-36b2-4b32-8245-7489c8e2ee87`. Aucune ligne n’a été modifiée ni écartée. On peut approuver une règle, la refuser ou la laisser en attente. Une règle en attente ne change pas les données.

Supports à envoyer avant la réunion :

- [Notebook d’ingestion et diagnostic Silver](../../ingestion.ipynb), section « Étape 3 — Diagnostic Silver en lecture seule ».
- [Registre des décisions et dictionnaire des 47 colonnes](plan-et-decisions.md). Demander au métier de relire plus particulièrement les unités, les codes, les clés et les champs indispensables.

## Personnes à réunir et déroulé

Prévoir **75 minutes**. Réunir une personne habilitée à valider les règles métier, le propriétaire de la télémétrie ou du référentiel machine, une personne qui connaît les incidents et la maintenance, et un référent pour l’accès aux données opérateur si la publication est discutée. Plusieurs rôles peuvent être tenus par la même personne. Demander si possible le dictionnaire émetteur, la cadence d’acquisition et les références des compteurs en amont.

| Durée | Sujet | Résultat attendu |
| ---: | --- | --- |
| 5 min | Lot et périmètre | Confirmer les quatre tables et l’usage du Silver. |
| 15 min | Grain, clés, copies et révisions | Valider la clé d’un relevé, les autres identifiants et la règle de priorité en cas de conflit. |
| 15 min | Horloge, cadence, unités et capacité | Valider les fuseaux, la période des compteurs et les seuils qui ont un sens. |
| 15 min | Manquants, formats et références | Valider les champs obligatoires, les codes d’absence et les motifs bloquants. |
| 15 min | Champs opérateur, dictionnaire et publication | Valider l’usage des pseudonymes, des textes libres et le contenu des artefacts GitHub. |
| 10 min | Relire les décisions | Attribuer un responsable, une date et un périmètre à chaque accord ou point restant. |

## Chiffres et exemples à présenter

Le lot contient **137 001 lignes** : 135 626 mesures de télémétrie, 1 245 incidents, 15 machines et 115 interventions. Aucun hash de ligne répété, conflit d’identifiant, échec de conversion sondée ni référence inconnue n’a été détecté. Les limites physiques restent non évaluées. Les SHA‑256 des trois fichiers et les hash complets des exemples sont dans le notebook.

| Signal | Volume et exemple | Question à poser |
| --- | --- | --- |
| Même machine au même instant | 1 340 groupes, 2 686 lignes. Pour `MACH-01` le 1er juin 2025 à 00:00:00, deux lignes indiquent respectivement 46,332 et 46,348 pour `temperature_c`, 198,206 et 198,203 pour `pressure_bar`, avec 4 pièces dans les deux cas. Hash préfixes `32204f1643b0` et `45d2e441c188`. | Deux mesures légitimes, deux capteurs ou deux révisions d’un relevé ? |
| Capacité déclarée dépassée | 37 136 lignes. `MACH-01`, le 2 juin 2025 à 06:00:00, indique 49 pièces alors que la capacité déclarée est de 48 pièces/heure. Hash préfixe `2e71391386f6`. | Le compteur couvre-t-il une heure ? La valeur 48 indique-t-elle une limite ou une cadence nominale ? |
| Champs vides ou NULL | 2 958 lignes des quatre tables ont au moins un champ sondé vide ou NULL. En télémétrie, 2 828 lignes sont concernées : 995 pressions, 958 rotations et 894 températures sont vides. Exemple de rotation vide sur `MACH-01` le 5 juin 2025 à 11:00:00, hash préfixe `30b9a1c791a4`. | Absence normale, arrêt, panne de capteur ou donnée retardée ? Le champ est-il obligatoire pour l’usage envisagé ? |
| Références et valeurs absentes du SQL | Les 25 références explicites de maintenance vers des incidents aboutissent. Les 90 autres sont absentes. Les valeurs `created_at` et `updated_at` sont absentes des `INSERT`. | Le lien incident est-il facultatif ? Existe-t-il une source fiable des dates manquantes ? |

Les trois signaux télémétrie se recouvrent. **41 125 lignes distinctes** portent au moins un de ces signaux. 702 cumulent répétition et dépassement, 67 répétition et champ vide, 775 dépassement et champ vide, dont 19 cumulent les trois. Ces volumes mesurent l’impact d’un filtre potentiel. Ils ne représentent aucun rejet.

## Décisions à obtenir pendant la réunion

| Point et lien avec le registre | Réponse concrète attendue | Proposition en attendant la validation |
| --- | --- | --- |
| M1 — Grain télémétrie et clés des événements · SIL-05, SIL-06 | Dire ce que représente une ligne. Donner la clé exacte, son périmètre d’unicité et les éventuels identifiants de capteur, de séquence ou de révision. Confirmer aussi les clés des incidents, machines et interventions. | Garder les relevés au même instant. Afficher les groupes pour revue. |
| M2 — Copies et conflits · SIL-02, SIL-06 | Définir la preuve d’une copie technique, le critère d’occurrence à conserver et la source ou version prioritaire en cas de valeurs contradictoires. Préciser si un conflit peut rester en Silver avec un drapeau. | Conserver les occurrences. Le hash sert à retrouver les cas. |
| M3 — Temps · SIL-04 | Nommer le fuseau des deux CSV, le traitement des changements d’heure et la signification de chaque horodatage. Confirmer si la date et l’heure d’incident décrivent le même événement. | Garder les horaires comme enregistrés avec les décalages SQL explicites. |
| M4 — Unités, capacité, valeurs atypiques · SIL-03, SIL-08 | Confirmer l’unité et la fenêtre de mesure de chaque grandeur, le sens de `pieces_produced` et de la capacité, les régimes concernés et les limites éventuelles. Associer à chaque limite l’action autorisée et un exemple frontière. | Signaler les dépassements. Garder les valeurs et leurs unités sources. |
| M5 — Absences, conversions et imputation · SIL-03, SIL-07, SIL-08 | Lister les formats et codes d’absence permis par colonne. Distinguer les champs indispensables des champs facultatifs. Si une estimation est souhaitée, préciser la méthode, la durée maximale du trou et les situations où elle est permise. | Garder les absences et les valeurs brutes. Consigner l’écart pour revue. |
| M6 — Références et quarantaine · SIL-07 | Confirmer les référentiels et leur période de validité. Fixer quand une référence inconnue ou une clé illisible rend une ligne inutilisable. Décider où et comment conserver les lignes mises en attente. | Signaler la référence ou la clé en cause. Garder la ligne. |
| M7 — Codes métier et données opérateur · SIL-03, SIL-09 | Valider l’échelle et le sens de `severity`, de `shift`, des indicateurs `0/1`, des codes machine et maintenance. Définir quels pseudonymes et champs libres sont nécessaires en Silver et autorisés dans les artefacts. | Garder les codes, les pseudonymes et les valeurs d’origine dans Bronze. Partager des exemples sans données opérateur. |
| M8 — Traçabilité, publication et acceptation · SIL-01, SIL-02, SIL-10 | Confirmer les champs de traçabilité (lot, hash, occurrence), les contrôles d’acceptation, le destinataire des rapports et le contenu de l’échantillon GitHub. | Documenter le lot, les écarts et les preuves. Garder les fichiers et tables Bronze intacts. |

Utiliser le dictionnaire des 47 colonnes pendant M3 à M7. Valider les règles communes par famille, puis noter les exceptions avec le nom exact de la colonne. Le silence sur une exception ne vaut pas accord.

## Compte rendu à remplir pendant la réunion

Pour chaque point, enregistrer **validé**, **refusé** ou **en attente**. Une réponse comme « nettoyer les doublons » doit préciser la clé, le filtre exact, les exemples concernés et la règle de conservation. Si l’effet d’une règle change le nombre de lignes, indiquer le volume estimé avant application et le contrôle attendu après application.

| Point | Statut | Règle exacte et périmètre | Responsable métier et date | Exemple, impact et contrôle |
| --- | --- | --- | --- | --- |
| M1 | En attente | — | — | — |
| M2 | En attente | — | — | — |
| M3 | En attente | — | — | — |
| M4 | En attente | — | — | — |
| M5 | En attente | — | — | — |
| M6 | En attente | — | — | — |
| M7 | En attente | — | — | — |
| M8 | En attente | — | — | — |

En fin de réunion, relire les décisions avec la personne habilitée. Reporter les accords dans le registre, faire évoluer la version du contrat et appliquer uniquement le périmètre approuvé. Pour les points restants, consigner le document ou la donnée attendue et son responsable. Les propositions de modification ou d’exclusion restent suspendues tant que l’accord manque.
