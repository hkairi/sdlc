# Pipeline `none` — usage local uniquement

## Quand le choisir

Quand `ci.tool: none` dans `sdlc.config.yaml` : aucun serveur de CI n'est
installé. Les contrôles restent obligatoires ; ils sont exécutés **localement**
avant chaque commit ou chaque mise en production.

## Où copier quoi

Il n'y a aucun fichier de pipeline à copier. Installer uniquement les scripts :

```
scripts/ci.sh
scripts/check_thresholds.py
```

puis `chmod +x scripts/ci.sh`.

## Usage

```sh
# Avant un commit (au minimum) :
bash scripts/ci.sh

# Vérification ciblée pendant le développement :
bash scripts/ci.sh --only tests,coverage
```

Le code de sortie vaut **0** si aucun contrôle bloquant n'échoue, **1** sinon.
Les rapports sont écrits dans `reports/` (`summary.json` inclus).

## Garde-fous recommandés

Sans serveur de CI, la discipline repose sur des garde-fous locaux :

- un **hook `pre-commit`** (ou `pre-push`) qui lance `bash scripts/ci.sh` ;
- ou un hook géré par un outil comme `lefthook`, `husky` ou `pre-commit`
  (voir la documentation de l'outil retenu) ;
- la même commande exécutée manuellement avant chaque `go/no-go` de production.

Ajouter `reports/` au `.gitignore`.

## Limites

- Pas de déploiement automatisé enchaîné : la procédure de déploiement
  (`.sdlc/templates/deploy/`) est appliquée manuellement.
- Pas d'artefact de CI : les rapports restent sur le poste. Les journaliser dans
  `docs/journal/` si l'orchestrateur en a besoin.

## Passage à un vrai outil de CI

Voir `.sdlc/templates/ci/github-actions/`, `gitlab-ci/`, `forgejo-actions/` ou
`jenkins/`. Dans tous les cas, le pipeline appelle le **même** `scripts/ci.sh` :
rien d'autre n'est à réécrire.
