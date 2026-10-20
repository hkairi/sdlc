---
description: Met à jour le fichier de suivi d'avancement à partir de l'état courant des tâches
argument-hint: [chemin-du-suivi ou identifiant-de-chantier]
allowed-tools: Read, Edit, Write, Bash, Glob, Grep
model: "{{modèle-build}}"
---

<!-- Commande générée par `sdlc-init` pour le projet {{nom-du-projet}}.
     Remplacer les marqueurs {{…}} puis supprimer ce commentaire. -->

Mets à jour le fichier de suivi d'avancement.

## Étapes

1. Lire `sdlc.config.yaml` et les point d'entrée du suivi (`docs/suivi/state.json`).
2. Charger la skill `suivi-taches` et suivre ses instructions.
3. Reporter l'avancement des tâches (`$ARGUMENTS`) sans inventer de statut : un statut non
   observé reste inchangé.
4. Régénérer le tableau de bord par son script, jamais à la main.

## Interdits

- Git en écriture. Lire un secret. Modifier un fichier généré sans le régénérer.

Les fichiers de suivi vivent sous `docs/suivi/` ; le tableau de bord est généré par `suivi-projet`.
