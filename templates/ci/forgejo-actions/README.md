# Pipeline Forgejo Actions

## Quand le choisir

Quand le dépôt est hébergé sur **Forgejo** (Codeberg ou instance auto-hébergée)
et que `ci.tool: forgejo-actions` dans `sdlc.config.yaml`.

## Où copier le fichier

Copier `ci.yml` **tel quel** vers :

```
.forgejo/workflows/ci.yml
```

Ajouter `reports/` au `.gitignore`.

## Secrets attendus

À déclarer dans **Settings > Actions > Secrets** (ou au niveau de
l'organisation) :

| Secret | Usage |
|---|---|
| `DEPLOY_TOKEN` | Jeton de déploiement pour la préproduction et la production. |

## Adaptation

1. Remplacer les marqueurs `{{…}}` (étiquette de runner `{{runner-label}}`,
   commandes, URL, branche principale).
2. Forgejo Actions est compatible avec la syntaxe de GitHub Actions ; les
   `uses: actions/...` fonctionnent si un proxy compatibilité est configuré sur
   l'instance. Sinon, remplacer par des étapes `run:` équivalentes.
3. Un runner doit être enregistré avec l'étiquette choisie pour `runs-on`.
4. **Production manuelle et protégée** : le job `production` restreint son
   déclenchement à la branche principale via `if:`. Selon la version de Forgejo,
   les approbations d'environnement peuvent être absentes : **exiger alors un
   `workflow_dispatch` manuel** ou une règle de branche protégée pour lancer la
   production (documenter le choix dans l'ADR CI).
5. Le job `controles` appelle uniquement `scripts/ci.sh`.
6. `python3` doit être présent dans l'environnement du runner (requis par
   `check_thresholds.py`).

## Enchaînement

contrôles → build → préproduction → tests de bout en bout → **production
(manuelle, protégée)**.

## Variante GitLab

Si le forge est GitLab, utiliser `.sdlc/templates/ci/gitlab-ci/`.
