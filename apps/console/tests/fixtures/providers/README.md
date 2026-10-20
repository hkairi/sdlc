# Fixtures fournisseurs hors réseau

Ces fichiers permettent de tester l’ingestion GitHub, GitLab et CI sans aucun appel réseau.
Ils ne contiennent aucun jeton ni secret.

| Fichier | Contenu |
|---|---|
| `github_pulls.json` | PR GitHub brutes (`pull_requests`) et revues indexées par numéro (`reviews`) |
| `gitlab_merge_requests.json` | MR GitLab brutes (`merge_requests`) et approbations (`approvals`) |
| `github_checks.json` | Check runs GitHub Actions (`check_runs`) |
| `gitlab_pipelines.json` | Pipelines GitLab CI (`pipelines`) |
| `github_quota.json` | Réponse de quota GitHub (HTTP 429) |
| `github_unauthorized.json` | Réponse d’authentification GitHub (HTTP 401) |

Le mode fichier des collecteurs accepte directement `github_pulls.json` et
`gitlab_merge_requests.json`. Les fichiers CI sont des fixtures de référence pour la détection
de processus et ne sont pas encore consommés par un collecteur dédié.
