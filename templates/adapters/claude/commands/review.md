---
description: Relit une tâche réalisée en lecture seule et rend un rapport de revue
argument-hint: <identifiant-de-tache ou chemin-du-rapport>
allowed-tools: Read, Bash, Glob, Grep
model: "{{modèle-think}}"
---

<!-- Commande générée par `sdlc-init` pour le projet {{nom-du-projet}}.
     Remplacer les marqueurs {{…}} puis supprimer ce commentaire. -->

Relis la tâche `$ARGUMENTS` en **lecture seule**.

## Étapes

1. Lire `.sdlc/workflow-sdlc.md`, `sdlc.config.yaml` et le paquet de passation.
2. Lire le rapport de l'exécutant et le diff proposé.
3. Vérifier la conformité au brief, aux exigences, aux ADR et à la spec gelée.
4. **Relancer toi-même** les vérifications (`{{commande-ci}}`, tests) : ne pas se fier au seul
   rapport de l'exécutant.
5. Rendre un verdict : `conforme`, `non conforme` ou `à revoir`, avec les points bloquants et
   mineurs.

## Interdits

- Modifier un fichier, exécuter une commande git en écriture, lire un secret.
- Relire une tâche dont tu es l'auteur.

Déléguer la revue au sous-agent `reviewer`.
