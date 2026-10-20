# Journal des changements — plugin ai-sdlc-tracker

## 0.2.1 — 2026-10-19 — Correction de l'identifiant de phase

### Corrigé

- `sdlc_phase` transmet l'identifiant réel `plan` pour la phase « Planification ». Avec `planification`,
  `track_phase.py` répondait **sans erreur et sans rien appliquer** (constaté en clôturant les deux
  changes : les items restaient à `todo`).
- `sdlc_phase` relit l'item après l'appel : un identifiant inconnu produit désormais un avertissement
  explicite au lieu d'un succès apparent.
- `sdlc_doctor` affiche les compteurs réels de la baseline (dérives connues, tâches sans preuve) au lieu d'un
  nombre d'« entrées » qui n'existe pas dans le fichier.

## 0.2.0 — 2026-10-19 — Durcissement pour un usage quotidien

### Ajouté

- **`sdlc_doctor`** : contrôle de santé en lecture seule (version, périmètre, configuration,
  scripts et gabarits, hook git, baseline, binaire Python, délai), avec un verdict et les actions.
- **Baseline de dette** : `scripts/suivi/baseline.py --write` fige les problèmes connus à une date
  dans `scripts/suivi/baseline.json` ; `sdlc_status` distingue le neuf du connu et rappelle la dette.
- **Bornes de temps** : option `commandTimeoutMs` (défaut 10 000 ms) sur `python3` et `git` ; un
  dépassement donne le code 124 et un message explicite, et refuse le commit plutôt que de laisser
  passer une dérive non vérifiée.
- **Portabilité** : option `pythonBin` (`python3`, ou `python` sous Windows).
- **CI** : workflow `ai-sdlc-tracker.yml` (Node 22/24/26, `npm ci`, tests, `tsc --noEmit`).
- **Harnais d'intégration** : `tests/e2e.test.ts` exerce le câblage complet de `createTracker`.
- **Version et changelog** : `VERSION`, matrice de compatibilité dans le README.

### Modifié

- `projectName` est **déduit du dépôt** (plus de défaut « Engagements »).
- `sdlc_status` ne crie plus la dette historique : « 0 nouvelle dérive · N connues depuis <date> ».
- Le filtre de chemins ne réagit qu'à `tasks.md` et aux fichiers de suivi (plus de contrôle à chaque
  `proposal.md` ou `design.md`).
- `git status` est lu avec `-uall` : les fichiers non suivis sont vus un par un, plus par dossier.

### Corrigé

- **Un défaut interne ne fait plus échouer un outil** : `BlockError` pour les refus volontaires,
  garde `guarded` qui journalise et avale le reste ; l'installation de chaque contrôle est isolée.
- Une mise à jour non appliquée est signalée (contrôle optimiste) au lieu d'être présentée comme un
  succès.
- Le message de génération rappelle de **demander l'accord de l'utilisateur avant d'ouvrir** le suivi.

### Compatibilité

| Élément | Version |
|---|---|
| OpenCode | 2.0.32 (API V2 des plugins) |
| Node | ≥ 22.18 (exécution native des `.ts`) ; testé en 22, 24, 26 |
| Python | ≥ 3.9 |
| `@opencode/plugin` | 2.0.32 (épinglé) |

## 0.1.0 — 2026-10-19 — Première version

Six outils (`check`, `track`, `phase`, `generate`, `status`, `report`), quatre contrôles (commit,
validation stricte, écriture directe, fin de tour), scripts vendorisés et contrôle de dérive.
