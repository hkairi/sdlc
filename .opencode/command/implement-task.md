---
description: Implémente une tâche à partir de son paquet de passation et rend un rapport conforme au schéma
agent: implementer
model: "opencode-go/deepseek-v4.1-flash"
subtask: true
---



Implémente **une seule** tâche décrite dans le paquet de passation `$ARGUMENTS`.

## Étapes

1. Lire `.sdlc/workflow-sdlc.md` puis `sdlc.config.yaml`.
2. Lire le paquet `$ARGUMENTS`, conforme à `.sdlc/templates/handoff/input.md`.
3. Vérifier que chaque fichier à modifier figure dans les fichiers autorisés ; sinon s'arrêter et
   le signaler.
4. Appliquer les règles TDD : test d'abord, échec, code, passage.
5. Exécuter les vérifications, dont `scripts/ci.sh` si présent.
6. Remplir le rapport `.sdlc/templates/handoff/report.schema.json` dans `docs/journal/reports/` et le
   valider contre le schéma.

## Interdits

- Git en écriture : proposer un `commit_message` (Conventional Commits), ne pas commiter.
- Lire `.env*` (sauf `.env.example`), `*.pem`, `*.key`, `secrets/`.
- Sortir du périmètre. Inventer une donnée sans source.
