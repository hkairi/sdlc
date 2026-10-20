@AGENTS.md

# Spécificités Claude Code — {{nom-du-projet}}

<!-- Gabarit généré par `sdlc-init` depuis `.sdlc/templates/adapters/claude/`.
     Remplacer les marqueurs {{…}} puis supprimer les commentaires de consigne.
     Ce fichier est copié à la racine du projet sous le nom `CLAUDE.md`. -->

Les règles communes vivent dans `AGENTS.md`, importé ci-dessus par la directive `@AGENTS.md`.
Ce fichier n'ajoute que ce qui est propre à Claude Code.

## 1. Les listes d'outils sont le levier fiable

Dans Claude Code, le `permissionMode` d'un sous-agent est ignoré si la session est en mode
`auto`, `acceptEdits` ou `bypassPermissions`. La seule contrainte qui tient est la liste
d'outils déclarée dans le frontmatter de l'agent (`tools`) ou sa liste d'exclusion
(`disallowedTools`). Ne jamais compter sur `permissionMode` seul pour imposer une lecture seule.

## 2. Git est réservé à l'humain

Aucune commande git qui modifie le dépôt. Les commandes en écriture (`add`, `commit`, `push`,
`merge`, `rebase`, `reset`, `checkout`, `switch`, `stash`, `branch -d`, `worktree`…) sont
refusées par `permissions.deny` dans `.claude/settings.json`. La lecture seule (`status`,
`diff`, `log`, `show`) reste autorisée. Les agents **proposent** un message de commit dans le
rapport de passation ; l'humain commite.

## 3. Secrets interdits en lecture

La lecture de `.env*` (sauf `.env.example`), `*.pem`, `*.key` et `secrets/` est refusée par
`permissions.deny` (règles `Read(...)`) dans `.claude/settings.json`. Les identifiants de
déploiement vivent dans la CI ou chez l'humain, jamais dans le contexte d'un agent.

## 4. Agents

Les sous-agents sont générés dans `.claude/agents/` :

| Agent | Mode | Rôle |
|---|---|---|
| `implementer` | écriture, tests | exécutant d'une tâche, git interdit |
| `reviewer` | lecture seule | relecteur, jamais auteur de la tâche relue |
| `doc-writer` | écriture restreinte | documentation (`docs/`, `README*`, `CHANGELOG*`) |
| `spec-challenger` | lecture seule | contestation d'un change OpenSpec |

## 5. Commandes

Les commandes sont générées dans `.claude/commands/` : `implement-task`, `review`, `update-suivi`.

## 6. Lancement non interactif

Le lancement non interactif d'un exécutant utilise la CLI configurée pour ce projet :
`{{cli-claude}}` (Claude), `{{cli-codex}}` (Codex), `{{cli-opencode}}` (OpenCode). Ces CLI sont
autorisées par `permissions.allow` dans `.claude/settings.json` afin que l'orchestrateur puisse
lancer les exécutants sans intervention manuelle.

## 7. Rappels

- `sdlc.config.yaml` est la source de vérité des rôles et des modèles ; le lire avant d'agir.
- Aucun rapport de tâche n'est accepté s'il n'est pas conforme à
  `.sdlc/templates/handoff/report.schema.json`.
- Une seule tâche à la fois, jusqu'à la Definition of Done (`AGENTS.md`, § 5).
