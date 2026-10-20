---
name: deploy-procedure
description: Produit, pour chaque composant de deploy.targets, la procédure docs/ops/deploy-<composant>.md depuis .sdlc/templates/deploy/<profil>/deploy.md, intègre les fiches de runbook-sections.md au runbook et rappelle le gate go/no-go et la journalisation dans docs/journal/deploys.jsonl. Utiliser dès que l'utilisateur demande la « procédure de déploiement », de « préparer un déploiement », « déployer le composant X », de « définir le rollback », d'« ajouter la fiche runbook du profil » ou de passer le gate « go / no-go ».
---

# Procédure de déploiement (`deploy-procedure`)

> **Chemins.** Les emplacements viennent de la section `paths` de `sdlc.config.yaml`
> (§ 13.3 de `.sdlc/workflow-sdlc.md`) : gabarits sous `paths.templates` (défaut
> `.sdlc/templates`), spec sous `paths.spec`, livrables sous les dossiers `paths.*`
> (défauts indiqués dans cette fiche).

## Objectif

Écrire, pour **chaque composant** de `deploy.targets`, la procédure de déploiement
`docs/ops/deploy-<composant>.md` à partir du gabarit du profil retenu : prérequis, étapes,
vérifications, **rollback**, sauvegarde et journalisation. Ajouter au runbook les fiches propres au profil.

## Entrées

- `sdlc.config.yaml` : `deploy.targets[]` (`component`, `profile`), `gates.go_no_go`, `project.stack`.
- `.sdlc/templates/deploy/<profil>/deploy.md`, `README.md`, `runbook-sections.md`.
- `.sdlc/templates/deploy/README.md` (vue d'ensemble des profils et de la journalisation).
- § 12 de `.sdlc/workflow-sdlc.md` (format `deploys.jsonl`).

Profils autorisés (§ 4) et gabarits correspondants :

| Profil | Gabarit de procédure |
|---|---|
| `vps-compose` | `.sdlc/templates/deploy/vps-compose/deploy.md` |
| `kubernetes` | `.sdlc/templates/deploy/kubernetes/deploy.md` |
| `paas` | `.sdlc/templates/deploy/paas/deploy.md` |
| `static` | `.sdlc/templates/deploy/static/deploy.md` |
| `serverless` | `.sdlc/templates/deploy/serverless/deploy.md` |
| `mobile` | `.sdlc/templates/deploy/mobile/deploy.md` |
| `package` | `.sdlc/templates/deploy/package/deploy.md` |
| `on-prem` | `.sdlc/templates/deploy/on-prem/deploy.md` |

## Étapes

1. Lire `sdlc.config.yaml` : lister les `deploy.targets` et le responsable `gates.go_no_go`.
2. Pour **chaque** cible, choisir le profil, copier `.sdlc/templates/deploy/<profil>/deploy.md` vers
   `docs/ops/deploy-<composant>.md`, puis remplacer les marqueurs `{{…}}` (hôte, répertoire, commandes,
   URLs, tags, version précédente, contact).
3. Lire `.sdlc/templates/deploy/<profil>/README.md` pour adapter la préproduction, la stratégie de rollback et
   la sauvegarde au contexte du projet.
4. Vérifier que la procédure contient bien : les prérequis en cases à cocher (dont `scripts/ci.sh` vert et
   le gate **go/no-go**), les étapes numérotées, les vérifications, la section **rollback** et la section
   **journalisation**.
5. Fournir les fiches `.sdlc/templates/deploy/<profil>/runbook-sections.md` à la skill `runbook` pour intégration
   dans `docs/ops/runbook.md` (étape 9).
6. Contrôler qu'aucun `component` de `deploy.targets` n'est laissé sans procédure.

## Livrables

- `docs/ops/deploy-<composant>.md` pour chaque `deploy.targets[]`.
- Les fiches de profil transmises pour `docs/ops/runbook.md`.
- Une entrée par déploiement dans `docs/journal/deploys.jsonl`.

## Critères de fin

- [ ] Chaque composant de `deploy.targets` a sa procédure.
- [ ] Chaque procédure référence le gate **go/no-go** (`gates.go_no_go`).
- [ ] Le bloc de journalisation `docs/journal/deploys.jsonl` au format § 12 est présent.
- [ ] Une procédure de rollback est décrite et rattachée à la version précédente.

## Gate et responsable

Gate **go / no-go** (`gates.go_no_go` dans `sdlc.config.yaml`). L'orchestrateur **rédige** la procédure ;
l'**humain ou la CI exécute** le déploiement. Aucune mise en production sans ce gate.

## Journalisation (rappel)

Une ligne par déploiement (préproduction, production, rollback) dans `docs/journal/deploys.jsonl` :

```json
{"ts":"{{horodatage-iso-8601}}","env":"production","component":"{{composant}}","version":"{{version}}","result":"success","duration_s":null,"by":"{{operateur-ou-pipeline}}","note":"{{note}}"}
```

`result` ∈ `success` | `rollback` | `failed`. Un rollback **est** un déploiement : il est journalisé avec
`result: "rollback"`. Les champs inconnus valent `null`, jamais une valeur inventée.

## Pièges

- Le profil `vps-compose` référence la skill **`vps-db-backup`** : toujours sauvegarder la base avant une migration.
- Ne jamais déployer un tag `latest` en production : tags immuables uniquement.
- Les secrets (jetons, mots de passe) ne sont **jamais** dans le dépôt : ils vivent dans la CI ou chez l'humain.
- Ne pas dupliquer la procédure d'un composant pour un autre : chaque `component` a sa fiche.
- La préproduction doit utiliser des secrets distincts de la production.
