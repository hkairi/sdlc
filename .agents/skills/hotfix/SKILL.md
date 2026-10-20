---
name: hotfix
description: Voie rapide de correctif d'incident — diagnostic, correctif minimal avec test de non-régression, contrôles 5b, revue par un relecteur ≠ auteur, gate go/no-go, déploiement journalisé, post-mortem dans docs/incidents/ et mise à jour a posteriori de la spec. Utiliser dès qu'un incident de production est signalé (« la prod est cassée », « il y a une panne », « correction urgente », « correctif à chaud ») ou qu'il faut documenter un incident et son post-mortem.
---

# Voie de correctif d'incident (`hotfix`)

> **Chemins.** Les emplacements viennent de la section `paths` de `sdlc.config.yaml`
> (§ 13.3 de `.sdlc/workflow-sdlc.md`) : gabarits sous `paths.templates` (défaut
> `.sdlc/templates`), spec sous `paths.spec`, livrables sous les dossiers `paths.*`
> (défauts indiqués dans cette fiche).

## Objectif

Remettre en service rapidement, sans casser le cadre : correctif **minimal**, toujours accompagné d'un
**test de non-régression**, vérifié, relu, déployé sous gate, puis analysé après coup.

## Entrées

- `sdlc.config.yaml` : `gates.go_no_go`, `organisation.max_review_iterations`, `organisation.task_timeout_min`.
- `.sdlc/templates/docs/incident-post-mortem.md` : gabarit du post-mortem.
- `scripts/ci.sh` : contrôles 5b.
- `docs/ops/deploy-<composant>.md` (procédure de déploiement et de rollback).
- `docs/journal/deploys.jsonl` (format § 12) et `docs/journal/runs.jsonl`.

## Étapes

1. **Diagnostic** : caractériser l'incident (symptôme, impact, composant, heure de début), consulter le
   runbook `docs/ops/runbook.md` et les journaux.
2. **Correctif minimal** : ne corriger que la cause de l'incident, sans refactoring de circonstance.
3. **Test de non-régression** : ajouter/étendre un test qui échoue avant le correctif et passe après.
   Le correctif est **incomplet sans ce test**.
4. **Contrôles 5b** : faire passer `bash scripts/ci.sh` (lint, tests, couverture, sécurité). Aucun court-circuit.
5. **Revue** : faire relire par un relecteur **≠ auteur** (max `max_review_iterations`, sinon escalade).
6. **Gate go / no-go** : obtenir la validation du responsable avant tout déploiement en production.
7. **Déploiement** : appliquer la procédure `docs/ops/deploy-<composant>.md` ; **journaliser** chaque
   déploiement (y compris un rollback, `result: "rollback"`) dans `docs/journal/deploys.jsonl`.
8. **Post-mortem** : écrire `docs/incidents/<INC-id>.md` à partir de `.sdlc/templates/docs/incident-post-mortem.md`
   (chronologie, impact, cause racine, actions, leçons).
9. **Mise à jour de la spec a posteriori** : si le comportement diverge de la spec, ouvrir une
   **demande de changement** (`change-request`) liée — jamais modifier une spec gelée directement.

## Livrables

- Le correctif et son **test de non-régression**.
- Le rapport de passation conforme à `.sdlc/templates/handoff/report.schema.json`.
- `docs/incidents/<INC-id>.md` (post-mortem).
- L'entrée correspondante dans `docs/journal/deploys.jsonl`.
- Le change lié a posteriori si la spec évolue (`change-request`).

## Critères de fin

- [ ] Un test de non-régression encadre le correctif (échoue sans lui, passe avec).
- [ ] `bash scripts/ci.sh` est vert.
- [ ] Un relecteur ≠ auteur a relu le correctif.
- [ ] Le déploiement est journalisé avec le résultat réel.
- [ ] Le post-mortem est écrit et les actions de fond sont tracées.

## Gate et responsable

Gate **go / no-go**, responsable `gates.go_no_go` de `sdlc.config.yaml`. La revue croisée est obligatoire
(relecteur ≠ auteur). Post-mortem **sans recherche de responsabilité** : on analyse le système, pas les personnes.

## Pièges

- Un correctif sans test de non-régression est un risque de récidive : ne pas livrer sans lui.
- Ne pas sauter les contrôles 5b au motif de l'urgence ; un outil absent donne `not_run`, jamais un faux succès.
- Ne pas contourner le gate go/no-go ni le relecteur : l'urgence ne suspend pas les règles.
- Le post-mortem n'est pas facultatif : sans lui, l'incident n'est pas clos.
- Une correction de comportement doit être réconciliée avec la spec (change-request lié).
