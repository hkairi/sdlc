## Why

`scripts/check_sync.py` est le **contrôle de référence** de la synchronisation suivi ↔ `tasks.md` :
le hook git (`.githooks/pre-commit`), la CI et le plugin `ai-sdlc-tracker` l'appellent tous. Or ce
script lit encore le **HTML** (`docs/suivi-*.html` via `TASK_HTML_RE` / `FEATURE_DATA_RE`), alors que
la source de vérité du suivi est désormais **`docs/suivi/state.json`** (schéma 1, depuis le change
`ai-sdlc-tracker-state-json`).

Conséquence : une divergence entre `state.json` et `tasks.md` peut passer **inaperçue** du gate si le
HTML régénéré n'est pas re-synchronisé (ou l'inverse). La « source de vérité » n'est pas réellement
contrôlée. De plus, la « source » annoncée du script (la skill `suivi-taches`) **n'existe pas** dans
`.agents/skills/suivi-taches/scripts/` : la copie vendorisée n'a pas de foyer.

Côté plugin, `TRACKED_PATH` et `changeOfPath` (`hooks/shared.ts`) ne reconnaissent pas
`docs/suivi/state.json` : une écriture directe de l'état ne déclenche aucun signalement de dérive.

## What Changes

- `scripts/check_sync.py` lit **`state.json`** (plus le HTML) : les fonctions `read_suivi_tasks`,
  `read_suivi_task_notes`, `check_mono`, `check_multi`, `check_all` et `check_changes` s'appuient sur
  `features[].tasks[]` et `features[].tasks_file`.
- `changes_touched_by` reconnaît `docs/suivi/state.json` comme un **suivi global** (→ contrôle de tous
  les changes ouverts), comme `suivi-multi.html` le faisait.
- Le plugin reconnaît `docs/suivi/state.json` dans `TRACKED_PATH` et `changeOfPath` : une écriture
  directe de l'état est signalée, un commit qui touche `state.json` est contrôlé.
- `check_sync.py` est ajouté à la skill `suivi-taches` (`scripts/check_sync.py` du dépôt reste la
  **copie vendorisée**, avec l'indication de sa source).

## Capabilities

### Modified Capabilities

- `sdlc-tracking` : le contrôle de synchronisation lit `state.json` ; la source du script vendorisé
  vit dans la skill `suivi-taches`.

## Impact

- **Fichiers** : `scripts/check_sync.py`, `.agents/skills/suivi-taches/scripts/check_sync.py` (nouveau),
  `templates/adapters/opencode/plugins/ai-sdlc-tracker/hooks/shared.ts`, fixtures de test.
- **Dépendances** : aucune — lecture JSON natif via `json` (stdlib).
- **Compatibilité** : `check_sync.py` reste invocable avec les mêmes modes (`--all`, `--paths`,
  `--file`/`--state`, `--require-evidence`) ; le hook git et la CI ne changent pas d'appel.
- **Tests** : port des tests de `check_sync.py` vers `state.json` + tests du plugin (détection de
  `state.json`).
