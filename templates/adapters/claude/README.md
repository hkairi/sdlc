# Adaptateur Claude Code

Gabarit des fichiers que `sdlc-init` génère pour l'outil **Claude Code**.

## Fichiers du gabarit et destination dans le projet

| Gabarit | Copié vers | Rôle |
|---|---|---|
| `CLAUDE.md` | `CLAUDE.md` (racine) | règles communes (`@AGENTS.md`) + spécificités Claude Code |
| `settings.json` | `.claude/settings.json` | permissions : git en écriture et secrets refusés, CLI des exécutants autorisées |
| `agents/implementer.md` | `.claude/agents/implementer.md` | exécutant (écriture, tests) |
| `agents/reviewer.md` | `.claude/agents/reviewer.md` | relecteur (lecture seule) |
| `agents/doc-writer.md` | `.claude/agents/doc-writer.md` | rédacteur de documentation (écriture restreinte) |
| `agents/spec-challenger.md` | `.claude/agents/spec-challenger.md` | contradicteur de spec (lecture seule) |
| `commands/implement-task.md` | `.claude/commands/implement-task.md` | lance une implémentation |
| `commands/review.md` | `.claude/commands/review.md` | lance une relecture |
| `commands/update-suivi.md` | `.claude/commands/update-suivi.md` | met à jour le suivi d'avancement |

`settings.json` doit être **fusionné** avec un `.claude/settings.json` existant plutôt
qu'écrasé : conserver les entrées de l'humain et n'ajouter que les nôtres.

## Marqueurs `{{…}}` à remplacer

| Marqueur | Source dans `sdlc.config.yaml` |
|---|---|
| `{{nom-du-projet}}` | `project.name` |
| `{{modèle-build}}` | `agents.claude.models.build` |
| `{{modèle-think}}` | `agents.claude.models.think` |
| `{{cli-claude}}` | `agents.claude.cli` |
| `{{cli-codex}}` | `agents.codex.cli` |
| `{{cli-opencode}}` | `agents.opencode.cli` |
| `{{commande-ci}}` | `scripts/ci.sh` (contrôles locaux) |

Ne conserver dans `permissions.allow` que les CLI des agents **retenus** pour ce projet.

## Correspondance des quatre agents

| Agent | Contrainte | Levier Claude Code |
|---|---|---|
| `implementer` | écriture, git interdit | `tools` (whitelist) + `permissions.deny` de `settings.json` |
| `reviewer` | lecture seule | `disallowedTools` (retire `Edit`, `Write`, `NotebookEdit`) |
| `doc-writer` | écriture limitée à `docs/`, `README*`, `CHANGELOG*` | `tools` + consigne de périmètre |
| `spec-challenger` | lecture seule | `disallowedTools` (retire `Edit`, `Write`, `NotebookEdit`) |

## Points de vigilance

- Le `permissionMode` d'un sous-agent est **ignoré** si la session est en mode
  `auto`/`acceptEdits`/`bypass` ; les listes `tools`/`disallowedTools` sont le levier fiable.
- `permissions.deny` interdit la lecture des secrets. `.env.example` reste autorisé : la liste
  de motifs ne le cible pas.
- La restriction d'écriture de `doc-writer` repose sur une consigne de périmètre, car le
  frontmatter ne permet pas de limiter l'outil `Write` à un répertoire.
- Lancer les exécutants en non interactif avec `{{cli-claude}}` (ou la CLI d'un autre outil).
