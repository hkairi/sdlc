# Adaptateur Codex

Gabarit des fichiers que `sdlc-init` génère pour l'outil **Codex**.

## Fichiers du gabarit et destination dans le projet

| Gabarit | Copié vers | Rôle |
|---|---|---|
| `config.toml` | `.codex/config.toml` | modèle, effort de raisonnement, bac à sable, politique d'approbation, déclaration des agents |
| `agents/implementer.toml` | `.codex/agents/implementer.toml` | exécutant (écriture, tests) |
| `agents/reviewer.toml` | `.codex/agents/reviewer.toml` | relecteur (lecture seule) |
| `agents/doc-writer.toml` | `.codex/agents/doc-writer.toml` | rédacteur de documentation (écriture restreinte) |
| `agents/spec-challenger.toml` | `.codex/agents/spec-challenger.toml` | contradicteur de spec (lecture seule) |
| `rules/sdlc.rules` | `.codex/rules/sdlc.rules` | règles de commandes (Starlark) : git en écriture interdit |

Codex lit `AGENTS.md` nativement : aucun fichier de règles Markdown supplémentaire n'est
nécessaire.

## Prérequis : projet « trusted »

**La configuration et les règles de `.codex/` ne se chargent que si le projet est marqué
« trusted » par Codex.** Tant que le projet ne l'est pas, `config.toml`, `agents/*.toml` et
`rules/sdlc.rules` sont ignorés : git en écriture n'est alors pas bloqué par les règles. Après
génération, `sdlc-init` doit le **signaler explicitement à l'humain** et celui-ci doit approuver
le projet auprès de Codex avant de lancer un exécutant.

## Marqueurs `{{…}}` à remplacer

| Marqueur | Source dans `sdlc.config.yaml` |
|---|---|
| `{{nom-du-projet}}` | `project.name` |
| `{{modèle-build}}` | `agents.codex.models.build` |
| `{{modèle-think}}` | `agents.codex.models.think` |
| `{{cli-claude}}` | `agents.claude.cli` |
| `{{cli-codex}}` | `agents.codex.cli` |
| `{{cli-opencode}}` | `agents.opencode.cli` |
| `{{commande-ci}}` | `scripts/ci.sh` |

Dans `rules/sdlc.rules`, les règles `decision = "allow"` des CLI des exécutants sont **en
commentaire** : `sdlc-init` décommente et remplace les marqueurs pour les seuls agents retenus,
puis supprime les règles des agents non utilisés.

## Correspondance des quatre agents

| Agent | Contrainte | Levier Codex |
|---|---|---|
| `implementer` | écriture, git interdit | `sandbox_mode = "workspace-write"` + règles `sdlc.rules` |
| `reviewer` | lecture seule | `sandbox_mode = "read-only"` |
| `doc-writer` | écriture limitée à `docs/`, `README*`, `CHANGELOG*` | `sandbox_mode = "workspace-write"` + consigne de périmètre |
| `spec-challenger` | lecture seule | `sandbox_mode = "read-only"` |

## Points de vigilance

- La restriction d'écriture de `doc-writer` repose sur une consigne de périmètre : le bac à sable
  Codex raisonne par portée d'écriture, pas par liste de fichiers.
- `rules/sdlc.rules` est écrit en Starlark : chaque `prefix_rule` porte une `justification` en
  français. Les motifs de secrets ne sont pas exprimables de façon fiable par préfixe de
  commande ; ils restent une interdiction d'instruction.
- Lancer les exécutants en non interactif : `codex exec -s <sandbox> -m <modèle>`.
