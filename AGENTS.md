# AGENTS.md

Ces consignes s’appliquent à tout le dépôt Indusense. Je veux du code simple, lisible, fiable et facile à faire évoluer.

## Écrire du code lisible

- Respecte les conventions Python et le style des fichiers existants. Utilise des noms explicites et cohérents pour les fonctions, les variables et les types.
- Donne une responsabilité claire à chaque fonction. Rends ses entrées, ses sorties et ses effets visibles. Ajoute des annotations de type lorsqu’elles clarifient le contrat.
- Préfère le code direct. Réutilise la logique existante et factorise les répétitions qui expriment la même règle. Introduis une abstraction ou une dépendance seulement si elle résout un besoin concret.
- Explique dans les commentaires les décisions et les cas particuliers. Ajoute une courte docstring quand le contrat d’une fonction mérite d’être précisé.

## Traiter les données avec soin

- Sépare la lecture, la validation, les calculs et la production des fichiers. Dans un notebook, organise les cellules pour pouvoir tout exécuter dans l’ordre depuis un noyau neuf.
- Rends explicites les hypothèses sur les formats, les types et les valeurs manquantes. Préserve les identifiants et indique le fichier ou la colonne concernée en cas d’erreur.
- Garde les fichiers sources intacts. Utilise des chemins relatifs au projet dans le code.

## Livrer des changements vérifiables

- Garde chaque changement centré sur la demande. Préserve les comportements qui doivent rester compatibles et évite les refactorisations sans rapport.
- Utilise `uv` et la version de Python déclarée par le projet. Avant de livrer, exécute le parcours concerné et les vérifications existantes. Ajoute un test ciblé quand il protège une règle métier ou un cas limite qui risquerait de régresser.
- Travaille sur une branche dédiée et fais des commits cohérents, avec des messages qui décrivent leur intention. Publie uniquement `main` après fusion, conformément aux consignes du sprint.
