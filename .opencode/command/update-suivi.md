---
description: Met à jour le fichier de suivi d'avancement à partir de l'état courant des tâches
agent: doc-writer
model: "opencode-go/deepseek-v4.1-flash"
subtask: true
---



Mets à jour le fichier de suivi d'avancement `$ARGUMENTS`.

## Étapes

1. Lire `sdlc.config.yaml` puis `docs/suivi/state.json`.
2. Charger la skill `suivi-taches` et suivre ses instructions.
3. Reporter l'avancement sans inventer de statut : un statut non observé reste inchangé.
4. Régénérer le tableau de bord par son script, jamais à la main.

## Interdits

- Git en écriture. Lire un secret. Modifier un fichier généré sans le régénérer.
