# Framework SDLC piloté par agents IA

Framework réutilisable pour piloter tout le cycle de vie logiciel — cadrage, conception, spécifications, code, documentation, déploiement, exploitation — avec des agents IA sous contrôle humain.

## Outils supportés

- Claude Code
- Codex
- OpenCode

Ils peuvent être utilisés seuls ou combinés.

## Installation dans un projet

L'installation se fait depuis ce dépôt avec l'installateur `bin/sdlc-install` (Python 3.9+ et bibliothèque standard uniquement). Il ne détruit rien : les fichiers du framework vivent sous `.sdlc/`, les skills sous `.agents/skills/`, et le contenu propre au projet (`README.md`, `docs/`, `templates/`, CI existante) n'est jamais touché. L'installateur n'exécute aucune commande git et refuse d'installer dans le dépôt du framework lui-même ou dans un chemin inexistant.

1. **Simuler d'abord** (« dry-run ») et relire les actions annoncées :

   ```
   bin/sdlc-install --target /chemin/vers/le/projet --dry-run
   ```

2. **Installer** :

   ```
   bin/sdlc-install --target /chemin/vers/le/projet
   ```

   L'installateur crée `.sdlc/` (`VERSION`, `manifest.json` avec les empreintes sha256, `workflow-sdlc.md`, `templates/`), copie les skills dans `.agents/skills/`, relie `.claude/skills`, insère un bloc délimité `<!-- sdlc:begin vX.Y.Z -->` … `<!-- sdlc:end -->` en tête de `AGENTS.md` (créé s'il est absent), ajoute `@AGENTS.md` en tête de `CLAUDE.md` (créé s'il est absent) et un bloc délimité dans `.gitignore`. Une skill du projet différente d'une skill du même nom est signalée en conflit et laissée intacte. L'installation est **idempotente** : un second passage n'écrit rien.

3. **Mettre à jour** après une nouvelle version du framework :

   ```
   bin/sdlc-install --target /chemin/vers/le/projet --upgrade
   ```

   Seuls les fichiers dont l'empreinte correspond au manifeste (c'est-à-dire non modifiés par l'humain) sont remplacés ; les blocs délimités sont mis à jour ; les fichiers modifiés sont signalés et conservés (`--force` pour les écraser).

4. **Désinstaller** :

   ```
   bin/sdlc-install --target /chemin/vers/le/projet --uninstall
   ```

   L'installateur retire les fichiers non modifiés et les blocs délimités, restaure `AGENTS.md` / `CLAUDE.md` / `.gitignore` à leur contenu d'origine, puis liste ce qui reste à retirer à la main.

5. Lancer la configuration initiale : au premier lancement d'un agent, l'absence de `sdlc.config.yaml` déclenche la skill `sdlc-init`. Valider le récapitulatif proposé.

## Premier lancement

Si `sdlc.config.yaml` est absent, l'agent actif exécute `sdlc-init`. Cette skill :

- détecte les CLI disponibles (`claude`, `codex`, `opencode`) ;
- demande les agents retenus, l'orchestrateur, les exécutants ;
- demande la confidentialité, les fournisseurs autorisés, la stack, l'outil de CI ;
- demande les cibles de déploiement par composant ;
- écrit `sdlc.config.yaml` ;
- génère, à partir de `templates/adapters/`, les configurations des seuls outils retenus (`.claude/`, `.opencode/`, `.codex/`…).

## Arborescence du framework

```
AGENTS.md                         # règles communes
CLAUDE.md                         # spécificités Claude Code
README.md                         # ce fichier
sdlc.config.example.yaml          # configuration commentée
.agents/skills/<skill>/SKILL.md   # source unique des skills
.claude/skills -> ../.agents/skills   # lien symbolique
templates/
  docs/                           # gabarits documentaires
  ci/<outil>/                     # pipelines par outil de CI
  scripts/ci.sh                   # contrôles uniques
  deploy/<profil>/                # procédures de déploiement
  adapters/<outil>/               # configurations des outils retenus
  handoff/                        # contrat de passation
```

## Documentation

- Spécification : [`docs/conception/workflow-sdlc.md`](docs/conception/workflow-sdlc.md)
- Découpage en lots : [`docs/conception/tasks.md`](docs/conception/tasks.md)
- Schéma du workflow : [`docs/workflow-sdlc.html`](docs/workflow-sdlc.html)
- Maquette du tableau de bord : [`docs/mockup-suivi-projet.html`](docs/mockup-suivi-projet.html)
