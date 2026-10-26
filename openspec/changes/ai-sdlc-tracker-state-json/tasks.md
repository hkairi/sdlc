# Tasks — ai-sdlc-tracker-state-json

## 1. Lecture de l'état en `state.json`

- [x] 1.1 Remplacer `detectScope` / `listSuivis` : détecter `docs/suivi/state.json` (et les changes OpenSpec), plus `docs/suivi-*.html`
- [x] 1.2 Remplacer `parseMonoTasks` / `parseMultiFeatures` par `parseStateJson` (lecture de `features[].tasks[]`)
- [x] 1.3 Réécrire `resolveTarget` : cible unique `docs/suivi/state.json`, feature résolue par `features[].id` ↔ `openspec/changes/<id>/`
- [x] 1.4 Typer les rôles dans `types.ts` (`executor`, `reviewer`, `review_iteration`, `escalated`, `ready_to_commit`, `commit_message`)
- [x] 1.5 Gérer `schema` ≠ 1 et `state.json` invalide : inerte + signalement (jamais une lecture silencieuse, jamais un refus volontaire)

## 2. Règle « relecteur ≠ auteur »

- [x] 2.1 Ajouter la vérification `reviewer ≠ executor` à la clôture (`done`) : refus (ou signalement) si identiques
- [x] 2.2 Refuser (ou signaler) une clôture sans `reviewer` assigné (`null`/absent)
- [x] 2.3 Appliquer la règle aux itérations : `review_iteration` incrémenté, `escalated` si `> max_review_iterations` (lu depuis `sdlc.config.yaml`)
- [x] 2.4 Étendre `canStartTask` : une tâche ne peut passer `done` sans relecteur distinct assigné

## 3. Écriture via les scripts `suivi-taches`

- [x] 3.1 Remplacer les appels `scripts/suivi/track*.py` par les scripts `suivi-taches` (`track.py`, `track_phase.py`, `generate.py`)
- [x] 3.2 Aligner le contrôle de synchronisation sur `scripts/check_sync.py` du framework (plus celui d'`engagements`)
- [x] 3.3 Résoudre le chemin de script sous le répertoire de la skill, refuser tout chemin hors périmètre (erreur interne journalisée)

## 4. Port des tests

- [x] 4.1 Remplacer les fixtures HTML du dépôt d'origine par des fixtures `state.json` autonomes
- [x] 4.2 Porter les 77 tests vers le modèle `state.json` (lecture, résolution, règles, écriture)
- [x] 4.3 Ajouter les tests de la règle « relecteur ≠ auteur » (identique, absent, distinct), des itérations/escalade, de `schema` ≠ 1 et du JSON invalide
- [x] 4.4 `npm test` → 77+ tests verts ; `npm run typecheck` → exit 0 ; `bin/plugin-sync-check` → rc 0 sur une installation resynchronisée

## 5. Documentation

- [x] 5.1 Mettre à jour `GUIDE.md` : le plugin n'est plus « inerte », il agit sur `state.json`
- [x] 5.2 Mettre à jour `templates/adapters/opencode/README.md` : retirer l'encadré « limite connue », le remplacer par la description du modèle `state.json`

### Critères d'acceptation

Une tâche est acceptée lorsque les scénarios des exigences associées passent, que
`npm test` et `npm run typecheck` sont verts et que la revue croisée (relecteur ≠ auteur) est faite.

| Lot | Critères d'acceptation |
|---|---|
| 1. Lecture | `detectScope` reconnaît `state.json` ; `resolveTarget` résout la feature par `id` ; `schema` ≠ 1 et JSON invalide → inerte/erreur interne |
| 2. Règle | `reviewer == executor` → refus ; `reviewer` absent → refus ; itérations et escalade correctes |
| 3. Écriture | mise à jour atomique via `track.py`, synchronisation alignée sur `check_sync.py`, chemin de script borné à la skill |
| 4. Tests | 77 tests (ou plus) verts, typecheck OK, `plugin-sync-check` rc 0 |
| 5. Documentation | `GUIDE.md` et `README.md` à jour, plus de mention « inerte » ni « limite connue » erronée |

### Traçabilité exigences ↔ tâches

| Exigence (delta) | Tâches |
|---|---|
| Cible résolue et annoncée | 1.1, 1.3 |
| Mise à jour d'une tâche en une seule opération | 3.1, 3.2 |
| Génération du suivi après validation | 3.1 |
| Signalement des écritures directes | 3.2 |
| Repli sûr hors périmètre | 1.1 |
| Scripts de référence uniques et contrôlés | 3.1, 3.2, 3.3 |
| Source de vérité unique dans state.json | 1.2, 1.5 |
| Relecteur différent de l'auteur | 1.4, 2.1, 2.2, 2.3, 2.4 |
