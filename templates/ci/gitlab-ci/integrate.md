# Intégration dans une CI GitLab existante (`ci.mode: integrate`)

> Extrait à **insérer** dans le `.gitlab-ci.yml` existant. Ne rien retirer : on ajoute seulement
> un job qui appelle `scripts/ci.sh`.

## Quand l'utiliser

Quand `ci.mode: integrate` et que le dépôt a **déjà** un `.gitlab-ci.yml`. On ne remplace pas le
pipeline ; on y ajoute les contrôles uniques.

## Prérequis

- `scripts/ci.sh` et `scripts/check_thresholds.py` installés par la skill `ci-setup` (copies de
  `.sdlc/templates/scripts/`).
- `python3` présent dans l'image.
- Les commandes existantes fournies par `SDLC_<CONTRÔLE>_CMD` : `ci.sh` les réutilise au lieu
  d'imposer ses détecteurs.

## Extrait à insérer

Ajouter un **stage** (s'il n'existe pas déjà) puis le job, sans retirer les jobs existants :

```yaml
stages:
  - # … stages existants conservés …
  - controles

# Job ajouté par le framework SDLC : contrôles uniques via scripts/ci.sh.
controles:
  stage: controles
  script:
    - bash scripts/ci.sh
  artifacts:
    when: always
    expire_in: 1 week
    paths:
      - reports/
    reports:
      junit: reports/junit/*.xml
```

Si un stage approprié existe déjà (`test`, `verify`…), utiliser celui-ci au lieu d'en créer un :
remplacer la valeur de `stage:` et ne pas modifier la section `stages:` existante.

## Variante — étape dans un job existant

Insérer `bash scripts/ci.sh` comme étape **supplémentaire** dans le `script:` d'un job existant,
sans retirer ses étapes actuelles.

## Vérification

```sh
bash -n scripts/ci.sh
# après un push : le job « controles » doit apparaître et publier reports/
```

Les rapports ne sont pas versionnés : `reports/` doit figurer dans `.gitignore`.
