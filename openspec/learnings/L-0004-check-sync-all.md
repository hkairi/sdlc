+++
id = "L-0004"
title = "check_sync --all échoue : ne jamais l'utiliser comme gate"
kind = "pitfall"
created = "2026-10-26"
status = "active"
scope = ["scripts/check_sync.py", ".githooks", ".github/workflows"]
tags = ["suivi", "check-sync", "ci", "dette", "baseline"]
source_change = "audit-chaine-ia-2026-10-26"

[[evidence]]
cmd = "python3 scripts/check_sync.py --all --require-evidence"
result = "55 problèmes : 22 tâches done sans preuve + dette de la baseline (110)"
+++

## Règle

Un hook ou un job bloquant doit appeler `check_sync.py --paths <chemins>`,
jamais `--all` : la dette historique ferait échouer tous les commits.

## Pourquoi

La CI exécute `--all --require-evidence` en `continue-on-error: true` et le
hook local filtre par chemins. Résultat : le contrôle global existe mais
n'empêche rien, et 33 tâches de `add-whatsapp-number-requests` restent `done`
sans preuve. `--all` est un outil d'audit, pas un gate.

## Comment vérifier

```sh
python3 scripts/check_sync.py --paths openspec/changes/<id> docs/suivi-<id>.html
# 0 attendu sur un change propre
python3 scripts/check_sync.py --all --require-evidence
# 1 attendu tant que la baseline n'est pas résorbée — c'est l'audit, pas le gate
```
