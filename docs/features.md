# Fonctionnalités du framework AI-DRIVEN-SDLC

> Vue d'ensemble des capacités du framework (v0.1.0), pour un lecteur qui découvre le dépôt.
> Les détails de mise en œuvre sont dans [`architecture/architecture.md`](architecture/architecture.md)
> et [`conception/workflow-sdlc.md`](conception/workflow-sdlc.md).

## Pilotage du cycle de vie complet

Le framework couvre les 13 étapes du SDLC, du cadrage à la clôture, sous contrôle humain :

1. **Initialisation** (`sdlc-init`) — détection des CLI, questions par blocs, `sdlc.config.yaml`, adaptateurs.
2. **État des lieux** (`etat-des-lieux`) — cartographie d'un projet existant, conventions, dette.
3. **Cadrage** (`cadrage`) — brief, objectifs mesurables, exigences non fonctionnelles.
4. **Conception** (`adr`) — ADR, analyse des menaces.
5. **Spécification** (`spec-review`) — change OpenSpec contesté avant gel.
6. **Planification** (`suivi-taches`, `suivi-projet`) — `tasks.md`, suivi, tableau de bord.
7. **Implémentation** (`tdd`) — test d'abord, une tâche à la fois, rapport de passation.
8. **Contrôles** (`ci-setup`) — `scripts/ci.sh`, lint, tests, couverture, sécurité, build.
9. **Revue croisée** — relecteur ≠ auteur.
10. **Documentation** (`changelog`) — README, CHANGELOG, notes de version.
11. **Recette** (`recette`) — tests de bout en bout, matrice scénario → test → résultat.
12. **Déploiement** (`deploy-procedure`) — 8 profils (VPS/compose, Kubernetes, PaaS, statique, serverless, mobile, package, on-prem).
13. **Runbook et supervision** (`runbook`).
14. **Clôture** (`retro`, `metrics`, `client-report`) — archive, rétro, indicateurs, rapport client.

Voies transverses : `change-request` (évolution après gel) et `hotfix` (incident + post-mortem).

## 18 skills

`adr`, `cadrage`, `change-request`, `changelog`, `ci-setup`, `client-report`, `deploy-procedure`,
`etat-des-lieux`, `hotfix`, `metrics`, `recette`, `retro`, `runbook`, `sdlc-init`, `spec-review`,
`suivi-projet`, `suivi-taches`, `tdd`.

## Trois outils d'agents

Adaptateurs **Claude Code**, **Codex** et **OpenCode** (configs, agents, permissions, commandes),
générés par `sdlc-init` pour les seuls outils retenus.

## Installation dans un projet

`bin/sdlc-install --target <projet>` : non destructif, idempotent, manifeste sha256,
`--dry-run`/`--upgrade`/`--uninstall`. Espace de noms `.sdlc/`, fusion non destructive
d'`AGENTS.md`/`CLAUDE.md`/`opencode.json`.

## Suivi d'avancement

- **Source de vérité** : `docs/suivi/state.json` (format partagé avec `suivi-projet`).
- **Rendus** : `docs/suivi-<id>.html` (mono/multi), charte commune (sidebar, cartes, KPI, thème clair/sombre).
- **Plugin OpenCode `ai-sdlc-tracker`** : 7 outils (`sdlc_check`, `sdlc_track`, `sdlc_phase`, `sdlc_generate`, `sdlc_status`, `sdlc_report`, `sdlc_doctor`) + hooks (commit, validate, écritures).
- **Rapport de clôture** : `docs/rapport-<change>.html`, accessible depuis le suivi.

## CI et déploiement

`scripts/ci.sh` = seule définition des contrôles (lint, tests, couverture, sécurité, dépendances,
secrets, build) ; le pipeline de l'outil choisi ne fait que l'appeler. Sorties dans `reports/`.

## Console SDLC (dogfooding)

Application locale (FastAPI + React/Vitest + SQLite) qui met le framework en œuvre : features,
tickets, changes OpenSpec, runs d'agents, qualité, coûts, incidents.
