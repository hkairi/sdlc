# Intégration sans serveur de CI (`ci.mode: none` ou CI absente)

> Il n'y a **aucun** pipeline à modifier. `ci.mode: integrate` ne s'applique pas : installer les
> scripts et exécuter les contrôles localement.

## Quand l'utiliser

Quand `ci.tool: none` ou qu'aucune CI n'est en place et que `ci.mode` vaut `none` (ou reste à
`integrate` mais sans pipeline cible) : les contrôles restent obligatoires, exécutés en local.

## Où copier quoi

Installer uniquement les scripts (copies de `.sdlc/templates/scripts/`) :

```
scripts/ci.sh
scripts/check_thresholds.py
```

puis `chmod +x scripts/ci.sh`.

## Recommandation — hook local

À défaut de pipeline, ajouter un hook `pre-commit` (ou `pre-push`) qui lance `bash scripts/ci.sh`,
ou utiliser un gestionnaire de hooks (`lefthook`, `husky`, `pre-commit`). Les commandes existantes
du projet restent réutilisées via `SDLC_<CONTRÔLE>_CMD`.

## Passage à une CI

Si une CI est ajoutée plus tard, repasser `ci.mode` à `integrate` et suivre l'`integrate.md` de
l'outil retenu (GitHub Actions, GitLab CI, Forgejo Actions ou Jenkins).

Les rapports ne sont pas versionnés : `reports/` doit figurer dans `.gitignore`.
