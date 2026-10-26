## Context

`state.json` (schéma 1) est la source de vérité du suivi ; le HTML est un rendu généré. Le change
`ai-sdlc-tracker-state-json` a fait lire **`state.json`** au plugin. Reste le **contrôle de
synchronisation** : `check_sync.py` (hook git + CI + plugin) lit encore le HTML. Ce change le fait
lire `state.json`, et aligne la détection des chemins du plugin.

## Goals / Non-Goals

**Goals:**

- `check_sync.py` lit `state.json` (plus le HTML) : le verdict `suivi ↔ tasks.md` porte sur la source
  de vérité.
- Un commit qui touche `docs/suivi/state.json` est contrôlé (mode `--paths`), une écriture directe de
  l'état est signalée par le plugin.
- `check_sync.py` a un foyer : la skill `suivi-taches` (`scripts/check_sync.py` du dépôt reste la copie
  vendorisée).

**Non-Goals:**

- Réécrire `state_io.py` / `tracking.py` (le script les réutilise pour lire `state.json`).
- Changer l'interface d'appel du hook git ou de la CI (mêmes modes).

## Decisions

- **Lecture** : `check_sync.py` lit `state.json` via `json` et compare `features[].tasks[]` (statut,
  note) aux cases de `features[].tasks_file` — la même logique que `check_feature` actuel, étendue au
  fichier unique.
- **Modes conservés** : `--all` (tous les changes ouverts), `--paths` (changes touchés), `--file`
  (alias `--state` : `docs/suivi/state.json`) + `--tasks` pour une feature. La sortie JSON reste
  `{file, tasks, problems}`.
- **Détection des chemins** : `changes_touched_by` traite `docs/suivi/state.json` comme un suivi
  global (→ `--all`), comme `suivi-multi.html` le faisait.
- **Plugin** : `TRACKED_PATH` ajoute `docs/suivi/state\.json` ; `changeOfPath` renvoie `undefined`
  pour `state.json` (suivi global, tous les changes) — le signalement passe par `--paths` + `--all`.
- **Foyer** : `.agents/skills/suivi-taches/scripts/check_sync.py` est la source ; `scripts/check_sync.py`
  la copie vendorisée (commentaire « copié depuis la skill » conservé).

## Risks / Trade-offs

- `state.json` est un fichier unique multi-features : un `--file` ciblé doit nommer la feature
  (`--tasks`), sinon tout est contrôlé.
- La preuve (`EVIDENCE_RE`) reste inchangée : elle porte sur la note de la tâche, lue dans `state.json`.
