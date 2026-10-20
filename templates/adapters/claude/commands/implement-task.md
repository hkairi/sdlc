---
description: Implémente une tâche à partir de son paquet de passation et rend un rapport conforme au schéma
argument-hint: <chemin-du-paquet-input.md>
allowed-tools: Read, Edit, Write, Bash, Glob, Grep, TodoWrite
model: "{{modèle-build}}"
---

<!-- Commande générée par `sdlc-init` pour le projet {{nom-du-projet}}.
     Remplacer les marqueurs {{…}} puis supprimer ce commentaire. -->

Implémente **une seule** tâche décrite dans le paquet de passation fourni.

## Étapes

1. Lire `.sdlc/workflow-sdlc.md`, puis `sdlc.config.yaml`.
2. Lire le paquet `$ARGUMENTS`, conforme à `.sdlc/templates/handoff/input.md`.
3. Vérifier que chaque fichier à modifier figure dans les fichiers autorisés. Sinon, s'arrêter et
   le signaler.
4. Appliquer les règles TDD : écrire le test, le faire échouer, écrire le code, le faire passer.
5. Exécuter les commandes de vérification indiquées, dont `{{commande-ci}}` si présent.
6. Remplir un rapport au format `.sdlc/templates/handoff/report.schema.json` dans
   `docs/journal/reports/`, puis le valider contre le schéma.

## Interdits

- Git en écriture : proposer un `commit_message` (Conventional Commits), ne pas commiter.
- Lire `.env*` (sauf `.env.example`), `*.pem`, `*.key`, `secrets/`.
- Dépasser le périmètre du paquet de passation. Inventer une donnée sans source.

Déléguer l'implémentation au sous-agent `implementer`.
