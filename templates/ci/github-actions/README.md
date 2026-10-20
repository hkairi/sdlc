# Pipeline GitHub Actions

## Quand le choisir

Quand le dépôt est hébergé sur **GitHub** et que la CI retenue
(`ci.tool: github-actions` dans `sdlc.config.yaml`) est GitHub Actions.

## Où copier le fichier

Copier `ci.yml` **tel quel** vers :

```
.github/workflows/ci.yml
```

Les rapports ne sont pas versionnés : ajouter `reports/` au `.gitignore`.

## Secrets attendus

À déclarer dans **Settings > Secrets and variables > Actions** :

| Secret | Usage |
|---|---|
| `DEPLOY_TOKEN` | Jeton de déploiement utilisé par les jobs de préproduction et de production. |

La protection de la production utilise l'environnement **production**
(Settings > Environments). Voir « Adaptation ».

## Adaptation

1. Remplacer les marqueurs `{{…}}` (branche principale, version Python, étapes
   d'installation, commandes de build, de déploiement et de recette, URL).
2. Créer les environnements `preproduction` et `production` dans
   **Settings > Environments**, puis, pour `production`, activer
   **Required reviewers** (au minimum une personne). C'est cette protection qui
   rend le déploiement en production **manuel et protégé**.
3. Si un autre outil de CI que GitHub Actions a été choisi (`ci.tool`), ce
   gabarit n'est **pas** à installer : voir `.sdlc/templates/ci/` pour l'outil retenu.
4. Le job `controles` appelle uniquement `scripts/ci.sh` : ne pas dupliquer les
   contrôles dans le workflow.
5. `python3` est requis par `check_thresholds.py` ; l'étape `setup-python`
   l'installe.

## Enchaînement

contrôles → build → préproduction → tests de bout en bout → **production
(manuelle, protégée par l'environnement)**.
