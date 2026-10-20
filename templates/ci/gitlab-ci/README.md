# Pipeline GitLab CI

## Quand le choisir

Quand le dépôt est hébergé sur **GitLab** (gitlab.com ou instance auto-hébergée)
et que `ci.tool: gitlab-ci` dans `sdlc.config.yaml`.

## Où copier le fichier

Copier `.gitlab-ci.yml` **tel quel** à la **racine** du projet :

```
.gitlab-ci.yml
```

Ajouter `reports/` au `.gitignore`.

## Secrets attendus

À déclarer dans **Settings > CI/CD > Variables** (masquées) :

| Variable | Usage |
|---|---|
| `DEPLOY_TOKEN` | Jeton de déploiement pour la préproduction et la production. |

## Adaptation

1. Remplacer les marqueurs `{{…}}` (image de base, commandes d'installation,
   de build, de déploiement et de recette, URL, branche principale).
2. Créer les environnements `preproduction` et `production` dans
   **Operate > Environments**.
3. Protéger la production : **Settings > CI/CD > Protected environments** →
   ajouter `production`, puis autoriser uniquement les rôles habilités. Le job
   `production` est en `when: manual` : il ne part jamais sans action humaine.
4. Le job `controles` appelle uniquement `scripts/ci.sh`.
5. `python3` doit être présent dans l'image (requis par `check_thresholds.py`).

## Enchaînement

contrôles → build → préproduction → tests de bout en bout → **production
(manuelle, environnement protégé)**.

## Variante Forgejo

Si le forge est Forgejo (Codeberg ou auto-hébergé), utiliser
`.sdlc/templates/ci/forgejo-actions/`.
