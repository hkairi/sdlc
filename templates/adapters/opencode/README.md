# Adaptateur OpenCode

Gabarit des fichiers que `sdlc-init` génère pour l'outil **OpenCode**.

## Fichiers du gabarit et destination dans le projet

| Gabarit | Copié vers | Rôle |
|---|---|---|
| `opencode.json` | `opencode.json` (racine) | permissions : git en écriture et secrets refusés, `external_directory` refusé |
| `agent/implementer.md` | `.opencode/agent/implementer.md` | exécutant (écriture, tests) |
| `agent/reviewer.md` | `.opencode/agent/reviewer.md` | relecteur (lecture seule) |
| `agent/doc-writer.md` | `.opencode/agent/doc-writer.md` | rédacteur de documentation (écriture restreinte) |
| `agent/spec-challenger.md` | `.opencode/agent/spec-challenger.md` | contradicteur de spec (lecture seule) |
| `command/implement-task.md` | `.opencode/command/implement-task.md` | lance une implémentation |
| `command/review.md` | `.opencode/command/review.md` | lance une relecture |
| `command/update-suivi.md` | `.opencode/command/update-suivi.md` | met à jour le suivi d'avancement |
| `plugins/ai-sdlc-tracker/**` | `.opencode/plugins/ai-sdlc-tracker/**` | plugin de suivi : six outils `sdlc_*`, quatre points de contrôle |

**Foyer de développement du plugin** : `plugins/ai-sdlc-tracker/` (tests, typecheck, CI). Une
installation est une copie non éditée ; contrôle : `bin/plugin-sync-check --target <installation>`.

**Plugin `ai-sdlc-tracker`.** Le plugin lit `docs/suivi/state.json` (source de vérité du framework) et
applique la règle « relecteur ≠ auteur ». Il délègue l'écriture et la génération aux scripts de la
skill `suivi-taches` (`track.py`, `track_phase.py`, `generate.py`). Voir `plugins/ai-sdlc-tracker/GUIDE.md`.

`opencode.json` doit être **fusionné** avec un fichier existant plutôt qu'écrasé. OpenCode lit
`AGENTS.md` nativement : aucun fichier de règles supplémentaire n'est nécessaire.

## Marqueurs `{{…}}` à remplacer

| Marqueur | Source dans `sdlc.config.yaml` |
|---|---|
| `{{nom-du-projet}}` | `project.name` |
| `{{modèle-build}}` | `agents.opencode.models.build` (format `provider/modèle`) |
| `{{modèle-think}}` | modèle de réflexion retenu pour OpenCode |
| `{{commande-ci}}` | `scripts/ci.sh` |

## Correspondance des quatre agents

| Agent | `mode` | Contrainte | Levier OpenCode |
|---|---|---|---|
| `implementer` | `subagent` | écriture, git interdit | `permission.edit: allow` + `permission.bash` (git refusé) |
| `reviewer` | `subagent` | lecture seule | `permission.edit: deny` et `permission.write: deny` |
| `doc-writer` | `subagent` | écriture limitée à `docs/`, `README*`, `CHANGELOG*` | `permission.edit: allow` + consigne de périmètre |
| `spec-challenger` | `subagent` | lecture seule | `permission.edit: deny` et `permission.write: deny` |

## Points de vigilance

- Dans `permission.bash`, **la dernière règle qui correspond l'emporte** : `"*": "allow"` vient
  d'abord, puis les règles `git …` en `deny`, puis la lecture seule de git en `allow`.
- Dans `permission.read`, `"*.env.example": "allow"` est placé **après** `"*.env.*": "deny"` pour
  rétablir l'exception prévue par les règles communes.
- `external_directory: deny` empêche la lecture hors du projet.
- Lancer les exécutants en non interactif avec `opencode run`.
