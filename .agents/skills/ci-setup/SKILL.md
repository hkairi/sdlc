---
name: ci-setup
description: Installe et branche les contrôles automatiques d'un projet du framework SDLC : copie .sdlc/templates/scripts/ci.sh et .sdlc/templates/scripts/check_thresholds.py dans scripts/, puis branche le pipeline selon ci.mode (integrate : ajoute un job/une étape qui appelle scripts/ci.sh sans rien retirer ; replace : sur décision explicite ; none) depuis .sdlc/templates/ci/<ci.tool>/, réutilise les commandes existantes via SDLC_<CONTRÔLE>_CMD et vérifie le script avec bash -n. Utiliser dès que l'utilisateur demande de « mettre en place la CI », « configurer les contrôles automatiques », « brancher le pipeline », « créer scripts/ci.sh », de « préparer l'étape 5b », ou de « faire passer lint, tests, couverture et sécurité ».
---

# Contrôles automatiques (`ci-setup`)

> **Chemins.** Les emplacements viennent de la section `paths` de `sdlc.config.yaml`
> (§ 13.3 de `.sdlc/workflow-sdlc.md`) : gabarits sous `paths.templates` (défaut
> `.sdlc/templates`), spec sous `paths.spec`, livrables sous les dossiers `paths.*`
> (défauts indiqués dans cette fiche).

## Objectif

Installer dans un projet les contrôles uniques du framework et brancher le pipeline retenu.
`scripts/ci.sh` est **la seule définition** des contrôles (§ 10 de `.sdlc/workflow-sdlc.md`) :
le pipeline de CI **ne fait que l'appeler** et publier `reports/`. Aucun contrôle n'est réécrit ailleurs.

## Entrées

- `sdlc.config.yaml` : `ci.tool`, `ci.mode`, `ci.coverage_min`, `ci.block_on`, `project.stack`,
  `paths.reports` (défaut `reports`), `paths.ci_script` (défaut `scripts/ci.sh`).
- `.sdlc/templates/scripts/ci.sh`, `.sdlc/templates/scripts/check_thresholds.py`, `.sdlc/templates/scripts/README.md`.
- `.sdlc/templates/ci/<ci.tool>/` (gabarit de pipeline et `integrate.md`) et son `README.md`.
- § 10 et § 13.4 de `.sdlc/workflow-sdlc.md` pour le contrat de sortie et les modes de CI.

## Modes (`ci.mode`, § 13.4)

| `ci.mode` | Comportement |
|---|---|
| `integrate` | **Défaut si une CI existe.** Ajouter un job ou une étape qui appelle `scripts/ci.sh` dans la CI en place, **sans rien retirer**. Extrait fourni par `<ci.tool>/integrate.md`. |
| `replace` | Remplacer la CI existante par le gabarit `.sdlc/templates/ci/<ci.tool>/` — **sur décision explicite seulement** (ADR ou accord humain). |
| `none` | Aucun pipeline ; contrôles exécutés en local (hook `pre-commit`/`pre-push`). |

## Table de correspondance des pipelines

| `ci.tool` | Gabarit source (`replace` / CI neuve) | Intégration (`integrate`) | Destination |
|---|---|---|---|
| `github-actions` | `.sdlc/templates/ci/github-actions/ci.yml` | `.sdlc/templates/ci/github-actions/integrate.md` | `.github/workflows/ci.yml` |
| `gitlab-ci` | `.sdlc/templates/ci/gitlab-ci/.gitlab-ci.yml` | `.sdlc/templates/ci/gitlab-ci/integrate.md` | `.gitlab-ci.yml` |
| `forgejo-actions` | `.sdlc/templates/ci/forgejo-actions/ci.yml` | `.sdlc/templates/ci/forgejo-actions/integrate.md` | `.forgejo/workflows/ci.yml` |
| `jenkins` | `.sdlc/templates/ci/jenkins/Jenkinsfile` | `.sdlc/templates/ci/jenkins/integrate.md` | `Jenkinsfile` |
| `none` | `.sdlc/templates/ci/none/README.md` | `.sdlc/templates/ci/none/integrate.md` | (aucun pipeline ; usage local) |

## Étapes

1. Lire `sdlc.config.yaml` : retenir `ci.tool` et `ci.mode` (défaut **`integrate`** si une CI existe). Réutiliser les commandes existantes via `SDLC_<CONTRÔLE>_CMD` plutôt que de les redéfinir.
2. Copier **à l'identique** `.sdlc/templates/scripts/ci.sh` et `.sdlc/templates/scripts/check_thresholds.py` dans `scripts/` du projet, puis rendre `ci.sh` exécutable (`chmod +x scripts/ci.sh`). `check_thresholds.py` **doit rester à côté** de `ci.sh` (le script l'appelle via son propre dossier).
3. Brancher le pipeline selon `ci.mode` :
   - **`integrate`** : ouvrir `<ci.tool>/integrate.md` et **insérer** l'extrait (job ou étape) dans la CI existante, **sans rien retirer** ; remplacer les marqueurs `{{…}}` (runner, étapes d'installation).
   - **`replace`** (décision explicite seulement) : copier le gabarit du tableau ci-dessus à sa destination, remplacer les marqueurs `{{…}}`, puis supprimer le commentaire d'en-tête.
   - **`none`** : aucun pipeline ; documenter le garde-fou local (hook) dans les conventions.
4. Adapter les sections de stack : `ci.sh` détecte déjà les stacks par la présence de `package.json`, `Gemfile`, `pyproject.toml`/`requirements.txt`, `go.mod`, `pom.xml`/`build.gradle` ; **ne pas forker** le script. Pour une commande propre au projet, surcharger par variable d'environnement (`SDLC_LINT_CMD`, `SDLC_TEST_CMD`, `SDLC_COVERAGE_CMD`, `SDLC_SAST_CMD`, `SDLC_DEPS_CMD`, `SDLC_SECRETS_CMD`, `SDLC_BUILD_CMD`) plutôt que de modifier le script ; ces variables proviennent des commandes proposées par `etat-des-lieux` (§ 13.4).
5. Déclarer dans le pipeline les outils de sécurité retenus (analyse de code, dépendances, conteneurs, secrets), tous capables de produire du SARIF dans `reports/security/`.
6. Vérifier :

   ```sh
   bash -n scripts/ci.sh
   bash scripts/ci.sh --help
   python3 scripts/check_thresholds.py --help
   bash scripts/ci.sh --only tests,coverage
   ```

7. Ajouter `reports/` au `.gitignore` (les rapports ne sont pas versionnés).

## Livrables

- `scripts/ci.sh` et `scripts/check_thresholds.py` (copies à l'identique des gabarits).
- En mode `integrate` : l'extrait de `<ci.tool>/integrate.md` **inséré** dans la CI existante,
  sans rien retirer. En mode `replace` : le pipeline à l'emplacement du tableau. En mode `none` :
  aucun pipeline, un garde-fou local.
- `reports/summary.json` après la première exécution.

## Critères de fin

- [ ] `bash -n scripts/ci.sh` ne signale aucune erreur.
- [ ] `scripts/ci.sh` exécuté une fois en local produit `reports/summary.json`.
- [ ] Le mode `ci.mode` est appliqué : `integrate` n'a **rien retiré** de la CI existante ;
      `replace` n'a lieu que sur décision explicite.
- [ ] Le pipeline présent (ou le hook, si `none`) appelle bien `bash scripts/ci.sh` et publie
      `reports/`.
- [ ] Les commandes existantes sont réutilisées via `SDLC_<CONTRÔLE>_CMD`.
- [ ] `reports/` est ignoré par git.

## Gate et responsable

Contrôle **bloquant automatique** (étape 5b) : aucun gate humain. L'exécutant installe ;
l'orchestrateur **relance lui-même** `bash scripts/ci.sh` avant de valider une tâche.

## Pièges

- **`integrate` ne retire rien** : on ajoute un job ou une étape, jamais on ne supprime l'existant.
- **`replace` est destructeur** : ne l'appliquer que sur décision explicite (ADR CI ou accord humain).
- Ne jamais recopier une logique de contrôle dans le pipeline : il appelle `ci.sh`, rien d'autre.
- Ne pas coder en dur une valeur de projet dans `ci.sh` (commande, seuil) : passer par `sdlc.config.yaml` ou les variables `SDLC_*`.
- Un outil absent donne `not_run` + avertissement, **jamais** un faux succès.
- `ci.block_on` accepte `faible` (synonyme de `basse`) ; le résumé machine normalise en `basse`.
- `yq` est utilisé s'il est installé ; sinon la lecture `grep`/`sed` ne voit que les scalaires de premier niveau.
