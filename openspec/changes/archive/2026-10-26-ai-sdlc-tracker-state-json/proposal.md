## Why

Le plugin OpenCode `ai-sdlc-tracker` (distribué dans `templates/adapters/opencode/plugins/`) a été
copié depuis le dépôt d'origine `engagements`, dont le modèle d'état est le **HTML** :
`docs/suivi-<id>.html` (mono) ou `docs/suivi-multi.html` (multi), avec `scripts/suivi/` et
`scripts/check_sync.py` vendorisés.

Le framework a fait évoluer ce modèle : la **source de vérité** du suivi est désormais
`docs/suivi/state.json` (format commun `suivi-taches` / `suivi-projet`, schéma 1), le HTML étant un
rendu généré. Résultat : dans un projet installé par le framework, le plugin ne reconnaît pas son
périmètre et reste **inerte** (fail-open) — le `GUIDE.md` le documente explicitement.

De plus, le framework impose une règle que le plugin ne vérifie pas : le **relecteur doit être
différent de l'auteur** (`reviewer ≠ executor`), avec suivi des itérations de revue et de
l'escalade. Ces informations vivent dans `state.json` (`executor`, `reviewer`, `review_iteration`,
`escalated`, `ready_to_commit`, `commit_message`) et sont aujourd'hui ignorées par le plugin.

## What Changes

- Le plugin **lit et écrit `docs/suivi/state.json`** (plus le HTML) : détection du périmètre,
  résolution de cible, lecture de l'état et mise à jour passent par le format JSON.
- Les scripts de référence passent de `scripts/suivi/` (vendorisés depuis `engagements`) aux scripts
  de la skill `suivi-taches` (`track.py`, `track_phase.py`, `state_io.py`).
- La règle **« relecteur ≠ auteur »** est appliquée : à la clôture (`done`) d'une tâche, le système
  signale (et, selon le mode, bloque) un `reviewer` identique à l'`executor`.
- Les rôles (`executor`, `reviewer`, `review_iteration`, `escalated`, `ready_to_commit`,
  `commit_message`) sont **typés** et exposés dans l'état.
- Les **77 tests** sont portés du modèle HTML vers le modèle `state.json` ; les fixtures du dépôt
  d'origine sont remplacées par des fixtures autonomes du framework.
- Le `GUIDE.md` et le `README.md` de l'adaptateur sont mis à jour (le plugin n'est plus « inerte »).

## Capabilities

### Modified Capabilities

- `sdlc-tracking` : la source de vérité du suivi devient `docs/suivi/state.json` ; ajout de la règle
  « relecteur ≠ auteur » et du typage des rôles.

## Impact

- **Fichiers** : `templates/adapters/opencode/plugins/ai-sdlc-tracker/**` (`core.ts`, `types.ts`,
  `tools/*.ts`, `hooks/*.ts`, `tests/**`), `templates/adapters/opencode/README.md`.
- **Dépendances** : aucune nouvelle — le plugin lit un JSON avec `node:fs`, aucun parseur externe.
- **Scripts** : le contrôle de synchronisation de référence devient celui du framework
  (`scripts/check_sync.py` de la skill `suivi-taches`), plus celui vendorisé depuis `engagements`.
- **Compatibilité** : le plugin reste **inerte** (fail-open) dans un dépôt qui ne contient ni
  `state.json` ni change OpenSpec.
- **Tests** : 77 tests portés ; la CI (`ai-sdlc-tracker.yml`, Node 22/24/26) reste inchangée.
