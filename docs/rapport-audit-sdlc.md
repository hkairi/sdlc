# Rapport d'audit — Framework SDLC AI-DRIVEN-SDLC

> Audit de l'état courant du framework (v0.1.0), réalisé le 2026-10-27.
> Toutes les valeurs sont **mesurées** sur le dépôt ; aucune estimation non sourcée.
> Périmètre : cohérence spec ↔ code, santé des tests et des contrôles, conformité aux principes du framework (§ 2 d'`AGENTS.md`).

## 1. Synthèse et verdict

| Dimension | Évaluation | Constat |
|---|---|---|
| Santé des tests | ✅ Verte | 222 tests, 0 échec (28 install + 26 e2e + 87 skills + 81 plugin). |
| Specs OpenSpec | ✅ Verte | 4 specs valides (`--strict`) + change `console-sdlc` valide. |
| Contrôles de dérive | ✅ Verts | `check_completeness.py` et `check_config.py` passent (config live + exemple). |
| CI | ✅ En place | 3 workflows : framework, plugin, Console. |
| Cohérence spec ↔ code | ⚠️ 1 écart | Copie obsolète et divergente `scripts/suivi/` + baseline découplée (cf. § 4.1). |
| Maturité exploitation | ⚠️ Partielle | Journaux et répertoires d'exploitation vides (cf. § 4.4). |

**Verdict global : sain.** Le framework est fonctionnellement complet et tout passe. Les deux seuls écarts de fond sont (a) une **copie legacy divergente** des scripts de suivi et (b) une **métadonnée de sous-titre figée** dans l'état de référence. Les autres points sont des résidus ou des décisions humaines.

## 2. Santé mesurée

### 2.1 Tests (222 au total, 0 échec)

| Suite | Exécution | Résultat |
|---|---|---|
| `tests.install.test_sdlc_install` | `python3 -m unittest` | 28 / 28 ✅ |
| `tests.e2e.test_e2e` | `python3 -m unittest` | 26 / 26 ✅ |
| `sdlc-init` — `test_detect.py` | `python3` | 3 ✅ |
| `sdlc-init` — `test_render_adapters.py` | `python3` | 6 ✅ |
| `suivi-taches` — `test_suivi_taches.py` | `python3` | 34 ✅ |
| `metrics` — `test_metrics.py` | `python3` | 11 ✅ |
| `suivi-projet` — `test_suivi_projet.py` | `python3` | 33 ✅ |
| Plugin `ai-sdlc-tracker` (TypeScript) | `node --experimental-strip-types --test` | 81 / 81 ✅ |
| Plugin `typecheck` | `tsc --noEmit` | 0 erreur ✅ |

### 2.2 Specs OpenSpec

| Spec | Exigences | Validation |
|---|---|---|
| `sdlc-tracking` | 18 | valide (`--strict`) |
| `agent-handoff` | 6 | valide (`--strict`) |
| `sdlc-learnings` | 5 | valide (`--strict`) |
| `sdlc-verification-environment` | 4 | valide (`--strict`) |
| change `console-sdlc` | — | valide |

### 2.3 Contrôles de dérive (non-régression)

| Contrôle | Sortie |
|---|---|
| `scripts/check_completeness.py` | ✅ 18 skills · 8 profils de déploiement · 5 outils CI · 3 adaptateurs · 14 gabarits docs |
| `scripts/check_config.py` (live + exemple) | ✅ clés de premier niveau, `paths.*` et version conformes au § 4 / § 13.3 |

### 2.4 CI

| Workflow | Rôle |
|---|---|
| `.github/workflows/ci.yml` | Framework : syntaxe shell, complétude, lint de config, tests install/e2e/skills. |
| `.github/workflows/ai-sdlc-tracker.yml` | Plugin : tests + typecheck sur Node 22/24/26. |
| `.github/workflows/console.yml` | Console SDLC (app de démonstration dogfooding). |

## 3. Conformité aux principes non négociables (§ 2)

| Principe | État |
|---|---|
| Git réservé à l'humain | ✅ respecté — aucune commande git en écriture par les agents ; commits proposés, validés par l'humain. |
| Pas de code sans spec validée | ✅ les deux changes (`ai-sdlc-tracker-state-json`, `check-sync-state-json`) sont archivés et leurs deltas appliqués à `sdlc-tracking`. |
| Markdown = source, HTML = rendu | ✅ suivi piloté par `docs/suivi/state.json`, HTML généré avec mention « fichier généré ». |
| Modes par agents et listes d'outils | ✅ adaptateurs Claude/Codex/OpenCode porteurs de permissions, pas de mode imposé par les skills. |
| Rien n'est inventé | ✅ journaux vides = « non mesuré » (cf. § 4.4), pas de chiffre fabriqué. |
| Contenu externe = données | ✅ aucun agent ne suit d'instructions trouvées dans les fichiers du dépôt. |
| Secrets | ✅ `.env*`/`*.pem`/`*.key` interdits en lecture ; contrôle `secrets` dans `scripts/ci.sh`. |

## 4. Anomalies et écarts

### 4.1 — Élevé · `scripts/suivi/` : copie obsolète, divergente et baseline découplée ✅ résolu le 2026-10-27

La source de vérité des scripts de suivi est **`.agents/skills/suivi-taches/`** (lue par le plugin via `scriptsDir` par défaut et par `scripts/check_sync.py`). Or il subsiste à la racine **`scripts/suivi/`**, une ancienne « vendorisation » qui a **divergé** :

- **Fichiers divergents** : `scripts/generate.py`, `scripts/phases.py`, `scripts/track.py`, `scripts/track_multi.py`, `scripts/track_phase.py`, et les assets `template.html`, `template-multi.html`, `manifest-example.json`.
- **Fichiers orphelins** (absents de la skill) : `generate_from_openspec.py`, `generate_multi.py`, `sourcedocs.py`.
- **Fichiers manquants** (présents uniquement dans la skill) : `check_sync.py`, `migrate_from_html.py`, `render.py`, `state_io.py`, `tracking.py`, `reader.js`, `vendor/`.
- `sync_from_skill.py` est un mécanisme **obsolète** (remplacé par `bin/plugin-sync-check`).

**Conséquence fonctionnelle — baseline découplée.** La fonctionnalité de « baseline de dette » (ratchet) est cassée par le déplacement :
- le générateur `scripts/suivi/baseline.py` écrit `scripts/suivi/baseline.json` (chemin codé en dur) ;
- le plugin (`tools/status.ts`, `tools/doctor.ts`) lit `baseline.json` depuis `config.scriptsDir` = `.agents/skills/suivi-taches/baseline.json`, **où le fichier n'existe pas**.

Résultat : le plugin signale toujours « baseline : absente » (toute dette est signalée comme neuve), et la documentation du plugin (README) indique désormais `.agents/skills/suivi-taches/baseline.json`, un chemin sans fichier ni générateur.

Seul consommateur restant de `scripts/suivi/` : `scripts/tests/test_baseline_ratchet.sh` (teste la fonction pure `ratchet_problems` de `baseline.py`).

**Résolution.** `scripts/suivi/` a été supprimé. `baseline.py` a été migré dans la skill en version portable (`.agents/skills/suivi-taches/scripts/baseline.py`) : il lit la source de vérité `docs/suivi/state.json` (plus le HTML), appelle `check_sync.py` voisin, et écrit `baseline.json` à la racine de la skill — là où le plugin le lit. `test_baseline_ratchet.sh` pointe désormais vers le nouvel emplacement ; le `baseline.json` périmé (données *Engagements*) n'a pas été conservé.

### 4.2 — Moyen · Métadonnée de sous-titre figée dans `state.json`

`docs/suivi/state.json` → `meta.subtitle` annonce « 40 tâches · 10 lots », alors que l'état réel contient **46 tâches** (40 done, 5 doing, 1 todo) réparties en **11 lots** (L1–L11). Le lot 11 (plugin) et ses 6 tâches n'ont pas été répercutés dans ce sous-titre.

### 4.3 — Moyen · Changements non commités (doc + fixtures du plugin)

La dernière passe de nettoyage du plugin n'est pas encore committée :

- modifiés : `README.md`, `GUIDE.md`, `tests/config.test.ts` (suppression des références à l'ancien modèle `scripts/suivi`/`engagements`) ;
- supprimés : le fixture `tests/fixtures/repo/scripts/suivi/` (13 fichiers).

Aucun risque fonctionnel (tests plugin 81/81 verts), mais c'est un état en attente de `commit`/`push` par l'humain.

### 4.4 — Faible · Journaux et répertoires d'exploitation vides

| Emplacement | État |
|---|---|
| `docs/journal/runs.jsonl` | 0 octet |
| `docs/journal/deploys.jsonl` | 0 octet |
| `docs/metrics/history.jsonl` | 0 octet |
| `docs/retro/`, `docs/incidents/`, `docs/client/` | vides |

Attendu : le framework ne « tourne » pas encore via la Console sur lui-même ; ces valeurs relèvent du « non mesuré » tant qu'aucun run n'est journalisé. À ne **pas** remplir artificiellement.

### 4.5 — Faible · Résidu local `bin/__pycache__/`

Présence de `bin/__pycache__/` (2 `.pyc`). Gitignoré (`__pycache__/`), donc non versionné et sans impact ; simple artefact local.

### 4.6 — Faible · Change `console-sdlc` non archivé

`openspec/changes/console-sdlc` est marqué « Complete » mais pas archivé (contrairement aux deux changes du plugin). Cohérent avec le fait que la Console reste en cours de développement (démonstration dogfooding) ; à archiver en fin de chantier.

## 5. Recommandations (priorisées)

1. **Résorber `scripts/suivi/`** (élevé) — ✅ **fait** : `scripts/suivi/` supprimé, `baseline.py` migré dans la skill en version portable (écrit `baseline.json` à la racine de la skill, là où le plugin le lit), `test_baseline_ratchet.sh` mis à jour, `baseline.json` périmé non conservé.
2. **Mettre à jour `state.json`** (`meta.subtitle` → « 46 tâches · 11 lots ») via `track.py`, pas à la main.
3. **Commit/push** des changements en attente (§ 4.3) par l'humain.
4. **Archiver `console-sdlc`** en fin de chantier Console (§ 4.6).
5. (Optionnel) nettoyer `bin/__pycache__/` et décider si les journaux doivent être peuplés par un premier run pilote réel.

## 6. Annexe — périmètre couvert par l'audit

- **18 skills** (`.agents/skills/`), chacune avec son `SKILL.md`.
- **8 profils de déploiement** (`templates/deploy/`), **5 outils de CI** (`templates/ci/`), **3 adaptateurs** (`templates/adapters/`).
- **14 gabarits documentaires** (`templates/docs/`).
- **Installateur** `bin/sdlc-install` + contrôle de dérive `bin/plugin-sync-check`.
- **Plugin OpenCode** `ai-sdlc-tracker` (7 outils, lecture `state.json`, règle « relecteur ≠ auteur »).
- **App de démonstration** Console SDLC (`apps/console/` : FastAPI + React/Vitest, migrations Alembic).
- **Spécification de référence** `.sdlc/workflow-sdlc.md` (314 lignes, 13 sections) et 4 specs OpenSpec.
