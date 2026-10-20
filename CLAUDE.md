@AGENTS.md

# Spécificités Claude Code

## 1. Listes d'outils comme levier fiable

Dans Claude Code, le `permissionMode` d'un sous-agent est ignoré si la session est en mode `auto/acceptEdits/bypass`. Les listes d'outils (`tools` / `disallowedTools`) sont le seul levier sûr pour restreindre un agent.

## 2. Git en écriture interdit

Aucune commande git qui modifie le dépôt. Utiliser `permissions.deny` dans `.claude/settings.json` pour bloquer les outils git en écriture. Les agents proposent le message de commit ; l'humain exécute le commit.

## 3. Lecture de secrets interdite

Bloquer la lecture de `.env*`, `*.pem`, `*.key`, `secrets/` par `permissions.deny` (Read) dans `.claude/settings.json`.

## 4. Agents par défaut

Quand `sdlc-init` génère les adaptateurs Claude, il crée les agents suivants dans `.claude/agents/` :

- `implementer.md` : écriture de code et de tests, git interdit.
- `reviewer.md` : lecture seule, jamais auteur de la tâche relue.
- `doc-writer.md` : écriture limitée à `docs/`, `README*` et `CHANGELOG*`.
- `spec-challenger.md` : lecture seule, conteste la cohérence d'un change OpenSpec.

## 5. Commandes personnalisées

`sdlc-init` génère des commandes dans `.claude/commands/` (`/implement-task`, `/review`, `/update-suivi`). Pour déléguer à Claude Code en non interactif, l'orchestrateur utilise `claude -p`.
