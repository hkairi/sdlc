# Indicateurs du projet — 2026-10-27

> Calculés à partir des journaux (`docs/journal/runs.jsonl`, `docs/journal/deploys.jsonl`,
> `docs/metrics/history.jsonl`) et de l'état de référence `docs/suivi/state.json`.
> Conformément au principe « rien n'est inventé », une valeur non mesurable s'affiche
> **« non mesuré »**.

## 1. Avancement

| Indicateur | Valeur |
|---|---|
| Tâches du framework | **46 / 46 terminées** (100 %) |
| Lots | 11 / 11 |
| Phases (cadrage → clôture) | 6 / 6 `done` |
| Changes OpenSpec ouverts | 0 |
| Specs de référence | 9 (4 `sdlc-*` + 5 `console-*`) |

## 2. Qualité

| Indicateur | Valeur |
|---|---|
| Tests automatisés | **222 / 222 verts** (28 install + 26 e2e + 87 skills + 81 plugin) |
| Lint / typecheck | ruff + mypy (Console), `tsc` (plugin) — verts |
| Couverture Console | mesurée par `scripts/ci.sh` (seuil 80 %) |
| Dérives `state.json` ↔ `tasks.md` | **0** |

## 3. Agents et revue

| Indicateur | Valeur |
|---|---|
| Tâches par agent | **non mesuré** — `docs/journal/runs.jsonl` vide |
| Part validée dès la 1re revue | **non mesuré** — historique de revue non journalisé |
| Escalades | **non mesuré** — aucune tâche `escalated` dans `state.json` |
| Coût IA | **non mesuré** — pas de consommation journalisée |

## 4. Mise en production

| Indicateur | Valeur |
|---|---|
| Délai spec → production | **non mesuré** — `spec_freeze_ts` / `deploys.jsonl` absents |
| Déploiements journalisés | **non mesuré** — `docs/journal/deploys.jsonl` vide |
| Rollbacks | **non mesuré** — aucun déploiement journalisé |

## 5. Lecture

Les indicateurs d'avancement et de qualité sont **mesurés** (état de référence et tests).
Les indicateurs de coût, de revue et de délai restent **non mesurés** : les journaux
`runs.jsonl`/`deploys.jsonl` ne sont pas encore alimentés. Pour les obtenir, renseigner ces
journaux lors des prochains runs et déploiements (format § 12 de la spec), puis relancer la
skill `metrics`.
