# Intégration dans une CI GitHub Actions existante (`ci.mode: integrate`)

> Extrait à **insérer** dans un workflow GitHub Actions déjà en place. Ne rien retirer de
> l'existant : on ajoute seulement un job qui appelle `scripts/ci.sh`.

## Quand l'utiliser

Quand `ci.mode: integrate` et que le dépôt a **déjà** des workflows
(`.github/workflows/*.yml`). On ne remplace pas le pipeline ; on y ajoute les contrôles uniques.

## Prérequis

- `scripts/ci.sh` et `scripts/check_thresholds.py` installés par la skill `ci-setup` (copies de
  `.sdlc/templates/scripts/`).
- `python3` disponible (requis par `check_thresholds.py`).
- Les commandes de projet existantes fournies par les variables `SDLC_<CONTRÔLE>_CMD`
  (`SDLC_TEST_CMD`, `SDLC_LINT_CMD`, `SDLC_COVERAGE_CMD`, `SDLC_SAST_CMD`, `SDLC_DEPS_CMD`,
  `SDLC_SECRETS_CMD`, `SDLC_BUILD_CMD`) : `ci.sh` les réutilise au lieu d'imposer ses détecteurs.

## Extrait à insérer

À ajouter sous `jobs:` du workflow existant (n'en retirer aucun autre job) :

```yaml
  # Job ajouté par le framework SDLC : contrôles uniques via scripts/ci.sh.
  controles-sdlc:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.x"
      - name: Installer les dépendances du projet
        run: |
          {{etapes-installation}}     # ex. npm ci / bundle install / pip install -r requirements.txt
      - name: Contrôles (lint, tests, couverture, sécurité, build)
        run: bash scripts/ci.sh
      - name: Publier les rapports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: rapports-sdlc
          path: reports/
          if-no-files-found: ignore
```

## Variante — étape dans un job existant

Pour éviter un job supplémentaire, insérer les deux étapes suivantes dans un job déjà présent,
**sans supprimer** ses étapes actuelles :

```yaml
      - name: Contrôles (lint, tests, couverture, sécurité, build)
        run: bash scripts/ci.sh
      - name: Publier les rapports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: rapports-sdlc
          path: reports/
          if-no-files-found: ignore
```

## Vérification

```sh
bash -n scripts/ci.sh
# après un push : le job « controles-sdlc » doit apparaître et publier rapports-sdlc
```

Les rapports ne sont pas versionnés : `reports/` doit figurer dans `.gitignore`.
