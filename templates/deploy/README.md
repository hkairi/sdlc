# Procédures de déploiement par profil

Chaque profil décrit une cible de déploiement (`deploy.targets[].profile` dans
`sdlc.config.yaml`, valeurs autorisées au § 4 de la spec).

| Profil | Cible typique |
|---|---|
| [`vps-compose/`](vps-compose/) | Machine virtuelle avec Docker Compose |
| [`kubernetes/`](kubernetes/) | Cluster Kubernetes ou K3s |
| [`paas/`](paas/) | Plateforme applicative managée |
| [`static/`](static/) | Site statique / CDN |
| [`serverless/`](serverless/) | Fonctions managées |
| [`mobile/`](mobile/) | Application mobile (stores) |
| [`package/`](package/) | Bibliothèque publiée sur un registre |
| [`on-prem/`](on-prem/) | Installation chez le client |

## Contenu d'un profil

- `README.md` : quand choisir le profil, stratégie de préproduction, de rollback
  et de sauvegarde.
- `deploy.md` : procédure — prérequis (cases à cocher), étapes numérotées,
  vérifications, rollback, sauvegarde, journalisation.
- `runbook-sections.md` : fiches opérationnelles propres au profil
  (symptôme → diagnostic → remédiation → escalade).

## Utilisation

La skill `deploy-procedure` (étape 8) produit
`docs/ops/deploy-<composant>.md` en partant du `deploy.md` du profil retenu.
Les fiches de `runbook-sections.md` viennent compléter `docs/ops/runbook.md`
(skill `runbook`, étape 9).

## Journalisation

Tout déploiement (préproduction, production, rollback) est journalisé dans
`docs/journal/deploys.jsonl`, au format du § 12 de la spec. Le bloc exact est
rappelé dans chaque `deploy.md`.
