# Intégration dans une CI Forgejo existante (`ci.mode: integrate`)

> Extrait à **insérer** dans un workflow Forgejo Actions existant. Ne rien retirer : on ajoute
> seulement un job qui appelle `scripts/ci.sh`.

## Quand l'utiliser

Quand `ci.mode: integrate` et que le dépôt a **déjà** des workflows
(`.forgejo/workflows/*.yml` ou `.gitea/workflows/*.yml`).

## Prérequis

- `scripts/ci.sh` et `scripts/check_thresholds.py` installés par la skill `ci-setup` (copies de
  `.sdlc/templates/scripts/`).
- `python3` présent dans l'environnement du runner.
- Les commandes existantes fournies par `SDLC_<CONTRÔLE>_CMD` : `ci.sh` les réutilise.

## Extrait à insérer

À ajouter sous `jobs:` du workflow existant (n'en retirer aucun autre job) :

```yaml
  # Job ajouté par le framework SDLC : contrôles uniques via scripts/ci.sh.
  controles-sdlc:
    runs-on: {{runner-label}}
    steps:
      - uses: actions/checkout@v4
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

Forgejo Actions est compatible avec la syntaxe GitHub Actions ; si les `uses: actions/...` ne sont
pas disponibles sur l'instance, remplacer par des étapes `run:` équivalentes (`python3` requis).

## Variante — étape dans un job existant

Insérer les mêmes étapes `run: bash scripts/ci.sh` et de publication **en plus** des étapes
actuelles d'un job existant, sans rien retirer.

## Vérification

```sh
bash -n scripts/ci.sh
# après un push : le job « controles-sdlc » doit apparaître et publier rapports-sdlc
```

Les rapports ne sont pas versionnés : `reports/` doit figurer dans `.gitignore`.
