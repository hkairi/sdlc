# Tasks — check-sync-state-json

## 1. Migration de `check_sync.py` vers `state.json`

- [x] 1.1 Lire `state.json` (`features[].tasks[]` + `features[].tasks_file`) au lieu du HTML
- [x] 1.2 Adapter `--file`/`--state` et `--tasks` pour cibler une feature dans `state.json`
- [x] 1.3 `changes_touched_by` : reconnaître `docs/suivi/state.json` comme suivi global (→ tous les changes)
- [x] 1.4 `state.json` absent (mais `tasks.md` présent) → code 2 orientant vers `migrate_from_html.py`
- [x] 1.5 Un change ouvert sans feature dans `state.json` → signalé comme problème
- [x] 1.6 `schema` ≠ 1 ou JSON invalide → code 2 avec message explicite

## 2. Foyer de la skill `suivi-taches`

- [x] 2.1 Ajouter `check_sync.py` à `.agents/skills/suivi-taches/scripts/` (la source)
- [x] 2.2 Conserver `scripts/check_sync.py` comme copie vendorisée (indication de source conservée)

## 3. Détection des chemins dans le plugin

- [x] 3.1 `TRACKED_PATH` : ajouter `docs/suivi/state.json`
- [x] 3.2 `changeOfPath` : `state.json` = suivi global (signalement via `--paths` + `--all`)

## 4. Tests

- [x] 4.1 Porter les tests de `check_sync.py` vers `state.json`
- [x] 4.2 Tests du plugin : détection de `state.json` (écriture directe, commit)
- [x] 4.3 `check_sync.py` et plugin verts (hook git et CI inchangés)

### Critères d'acceptation

| Lot | Critères |
|---|---|
| 1. Migration | `check_sync.py --all` et `--paths` lisent `state.json` ; un `--file` cible une feature |
| 2. Foyer | `.agents/skills/suivi-taches/scripts/check_sync.py` existe ; `scripts/check_sync.py` est la copie |
| 3. Plugin | une écriture directe de `state.json` est signalée ; un commit touchant `state.json` est contrôlé |
| 4. Tests | tests de `check_sync.py` et du plugin verts ; `npm test` + typecheck du plugin OK |

### Traçabilité exigences ↔ tâches

| Exigence (delta) | Tâches |
|---|---|
| Synchronisation appliquée dans la session | 1.1, 1.2, 1.3, 1.4, 1.5, 3.1, 3.2 |
| Scripts de référence uniques et contrôlés | 1.6, 2.1, 2.2 |
