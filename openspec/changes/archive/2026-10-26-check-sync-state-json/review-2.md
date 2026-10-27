# Revue de spec n°2 — `check-sync-state-json`

> Seconde revue après correction. Réserve d'indépendance maintenue : même session que la rédaction.

## 0. Identification

| Champ | Valeur |
|---|---|
| Change | `check-sync-state-json` |
| Date | 2026-10-26 |

## Vérification des contestations

| # | Contestation (gravité) | Statut |
|---|---|---|
| 1 | Migration d'un projet existant (`state.json` absent) non spécifiée (majeure) | ✅ **Levée** — scénario « State.json absent » (code 2 → `migrate_from_html.py`). |
| 2 | Ciblage d'une feature (`--state`/`--tasks`) (mineure) | ✅ **Levée** — `--state` + `--tasks` précisé dans le design. |
| 3 | Change sans feature dans `state.json` (mineure) | ✅ **Levée** — scénario « Change sans feature » (problème signalé). |
| 4 | `schema` ≠ 1 (mineure) | ✅ **Levée** — scénario « Version de schéma non reconnue » (code 2). |
| 5 | JSON invalide (mineure) | ✅ **Levée** — scénario « JSON illisible » (code 2). |
| 6 | Traçabilité tâches ↔ exigences (mineure) | ✅ **Levée** — table ajoutée à `tasks.md`. |
| 7 | Compatibilité hook git / CI (mineure) | ✅ **Levée** — les modes `--all`/`--paths` sont conservés (vérifié en smoke test). |

## Verdict

- Contestations bloquantes : 0
- Contestations majeures : 0
- Contestations mineures : 0

**Verdict** : **prêt pour spec_freeze** — la majeure et les six mineures sont levées ; le change est
implémenté et vert (81 tests plugin, typecheck, smoke test de `check_sync.py` sur les cas limites).
