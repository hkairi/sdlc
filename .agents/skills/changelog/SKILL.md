---
name: changelog
description: Produit et tient à jour le CHANGELOG.md et les notes de version (docs/release-notes/<version>.md à partir de .sdlc/templates/docs/release-notes.md) à partir des changes OpenSpec archivés, des rapports de runs et des déploiements. Utiliser dès que l'utilisateur demande un « changelog », des « notes de version », de « documenter une release », de « lister les nouveautés et corrections » ou de préparer l'« étape 7 » (documentation).
---

# CHANGELOG et notes de version (`changelog`)

> **Chemins.** Les emplacements viennent de la section `paths` de `sdlc.config.yaml`
> (§ 13.3 de `.sdlc/workflow-sdlc.md`) : gabarits sous `paths.templates` (défaut
> `.sdlc/templates`), spec sous `paths.spec`, livrables sous les dossiers `paths.*`
> (défauts indiqués dans cette fiche).

## Objectif

Tenir le journal des modifications destiné au suivi de version : `CHANGELOG.md` à la racine, et des
notes de version datées. Tout provient des **changes OpenSpec archivés**, des **rapports de runs** et
des **déploiements** — aucune entrée n'est inventée.

## Entrées

- `sdlc.config.yaml` : `project.name`, `organisation.commit_cadence`, `gates.default`.
- `openspec/changes/archive/*/` : changes archivés (proposal, deltas, tasks) = source des entrées.
- `docs/journal/runs.jsonl` et `docs/journal/reports/*.json` : rapports de tâches (résultats, statuts).
- `docs/journal/deploys.jsonl` : versions livrées (`version`, `env`, `result`).
- `.sdlc/templates/docs/release-notes.md` : gabarit des notes de version.
- `docs/incidents/*.md` : correctifs issus d'un hotfix.

## Étapes

1. Lire `sdlc.config.yaml` et lister les changes **archivés** dans `openspec/changes/archive/`.
2. Regrouper les entrées par version (tag/version de `deploys.jsonl`), en cohérence avec
   `organisation.commit_cadence`.
3. Classer chaque modification selon `.sdlc/templates/docs/release-notes.md` :
   nouveautés, corrections, changements techniques, changements cassants.
4. Mettre à jour `CHANGELOG.md` (racine) : une section par version, la plus récente en haut.
5. Pour une version livrée, créer `docs/release-notes/<version>.md` à partir de
   `.sdlc/templates/docs/release-notes.md` (informations générales, instructions de mise à jour, problèmes connus).
6. Faire relire par un **relecteur différent de l'auteur**.

## Livrables

- `CHANGELOG.md` (racine du projet).
- `docs/release-notes/<version>.md` (une par version livrée).
- Le cas échéant, mise à jour du `README.md` et de la documentation d'API (livrables de l'étape 7).

## Critères de fin

- [ ] Chaque version livrée a une section dans `CHANGELOG.md`.
- [ ] Chaque entrée provient d'un change archivé, d'un rapport ou d'un déploiement identifié.
- [ ] Les notes de version suivent `.sdlc/templates/docs/release-notes.md`.
- [ ] Le document a été relu par un relecteur ≠ auteur.

## Gate et responsable

Relecture (relecteur ≠ auteur) ; responsable : `gates.default` de `sdlc.config.yaml`. Aucune version n'est
publiée sans entrée de changelog correspondante.

## Pièges

- N'écrire que ce qui est traçable : un élément sans change archivé ni rapport est absent, pas inventé.
- La date de publication est la date **réelle** du déploiement (`deploys.jsonl`), jamais une date prévue.
- Un échec de déploiement (`result: "failed"`) ou un rollback n'est pas une nouveauté : le signaler dans
  les problèmes connus ou les changements cassants si pertinent.
- Un bon de correction issu d'un `hotfix` provient du post-mortem `docs/incidents/<id>.md`.
