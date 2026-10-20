---
name: sdlc-init
description: Installe le framework SDLC piloté par agents dans un projet (nouveau ou existant) — détection des CLI installées, questions par blocs (agents, confidentialité, stack, CI, déploiement, parallélisme, gates), récapitulatif puis écriture de sdlc.config.yaml et génération des adaptateurs des seuls outils retenus. Utiliser au premier lancement quand sdlc.config.yaml est absent, ou quand l'utilisateur demande d'« initialiser le projet pour les agents », « installer le framework SDLC », de reconfigurer (`sdlc-init --reconfigure`) ou de mettre à jour les adaptateurs (`sdlc-init --upgrade`).
---

# Initialisation du framework (`sdlc-init`)

> **Chemins.** Les emplacements viennent de la section `paths` de `sdlc.config.yaml`
> (§ 13.3 de `.sdlc/workflow-sdlc.md`) : gabarits sous `paths.templates` (défaut
> `.sdlc/templates`), spec sous `paths.spec`, livrables sous les dossiers `paths.*`
> (défauts indiqués dans cette fiche).

## Objectif

Installer le framework dans un projet en écrivant `sdlc.config.yaml` (source unique de vérité
des rôles et des choix) et en générant, depuis `.sdlc/templates/adapters/`, les **seuls adaptateurs
des outils retenus**. C'est l'étape 0 du workflow.

Dans un **projet cible**, l'installation des fichiers du framework (espace `.sdlc/`, skills)
passe d'abord par **`bin/sdlc-install --target <projet>`** (§ 13.2) ; `sdlc-init` est ensuite
déclenchée au premier lancement d'un agent, ou par `--reconfigure` / `--upgrade`.

## Quand l'utiliser

- **Premier lancement** : `sdlc.config.yaml` est absent à la racine (règle du § 3 de `AGENTS.md`).
- L'utilisateur demande d'« initialiser le projet », « installer le framework », « configurer les
  agents » sur un projet.
- `sdlc-init --reconfigure` : les rôles ou les choix changent ; on réécrit la config et on
  régénère les adaptateurs.
- `sdlc-init --upgrade` : `workflow_version` change ; on met à jour les adaptateurs des outils
  déjà retenus **sans toucher aux choix du projet** (sauf confirmation explicite).

## Entrées

1. `AGENTS.md` et `CLAUDE.md` (règles communes et spécificités Claude Code) — déjà en place dans
   le projet.
2. `.sdlc/workflow-sdlc.md` (spec de référence, § 4 et § 6 en particulier).
3. `sdlc.config.example.yaml` : gabarit commenté de la configuration à produire.
4. `.sdlc/templates/adapters/<outil>/` : gabarits des adaptateurs ; leurs `README.md` donnent la table
   des destinations et des marqueurs.
5. Le résultat de `scripts/detect.sh` (détection de l'environnement).

## Étapes

1. **Détection.** Lancer :
   ```sh
   bash .agents/skills/sdlc-init/scripts/detect.sh .
   ```
   Le script renvoie sur stdout un objet JSON : CLI installées (`claude`, `codex`, `opencode` via
   `command -v`), type de projet (`new` ou `existing`), stack détectée, outil de CI existant,
   signaux de déploiement, et les **commandes existantes** de test, de lint et de couverture
   (`commands.test` / `commands.lint` / `commands.coverage`, à proposer en `SDLC_<CONTRÔLE>_CMD`).
   Ne proposer que des agents réellement installés.

2. **Projet existant (`kind: existing`).** Lancer **d'abord la skill `etat-des-lieux`** (étape 0b)
   avant les questions : son rapport pré-remplit les réponses (stack, commandes de test/lint/
   couverture détectées, CI et déploiement en place, organisation documentaire → `paths`). Ne pas
   redemander à l'humain ce que l'état des lieux a déjà établi.

3. **Questions, par blocs.** Utiliser l'outil de question natif s'il existe, sinon poser le texte
   à choix numérotés. Ne jamais regrouper les blocs.
   - **a. Agents** — choix multiple parmi les CLI détectées (`claude`, `codex`, `opencode`).
     Si plusieurs : orchestrateur (choix unique) et exécutants (choix multiple). L'orchestrateur
     est un agent activé ; les exécutants sont un sous-ensemble non vide des agents activés.
   - **b. Confidentialité et fournisseurs** — `public | client | restreint`, puis fournisseurs
     autorisés. `restreint` impose des modèles locaux uniquement et exclut les agents qui
     appellent un fournisseur distant. La liste des fournisseurs autorisés exclut les agents
     non couverts.
   - **c. Projet et stack** — `new | existing` (proposé d'après la détection), puis stack
     technique (liste libre ; préremplie avec la stack détectée si `existing`).
   - **d. CI et chemins** — outil `github-actions | gitlab-ci | forgejo-actions | jenkins | none`
     (prérempli avec l'outil détecté s'il existe) et **`ci.mode`** : `integrate` (défaut si une CI
     existe : ajout d'un job/étape appelant `scripts/ci.sh`, sans retirer l'existant), `replace`
     (sur décision explicite) ou `none`. Pour un projet `existing`, confirmer aussi la section
     `paths` proposée par `etat-des-lieux` (défauts du § 13.3).
   - **e. Déploiement** — cible par composant, avec une recommandation déduite de la stack, ou
     « à décider en conception » (`deploy.decided_at: conception`). Profils autorisés :
     `vps-compose`, `kubernetes`, `paas`, `static`, `serverless`, `mobile`, `package`, `on-prem`.
   - **f. Organisation** — parallélisme (`sequential | isolated`), rythme des commits
     (`task | feature`), responsables des gates (`gates.default`, `spec_freeze`, `recette`,
     `go_no_go`).

4. **Cas d'un seul agent.** S'il n'y a qu'un agent activé : il est à la fois orchestrateur et
   exécutant. Le rappeler dans le récapitulatif et dans `sdlc.config.yaml`
   (`orchestrator` = agent unique, `executors` = `[agent unique]`). La revue croisée devient une
   revue par un sous-agent en **lecture seule** utilisant un autre modèle que l'auteur (voir la
   config des agents dans `.sdlc/templates/adapters/`).

5. **Récapitulatif avant écriture.** Afficher la configuration complète telle qu'elle sera
   écrite (agents, rôles, confidentialité, fournisseurs, stack, CI, cibles de déploiement,
   organisation, gates) et **attendre la confirmation** de l'humain. Ne rien écrire avant.

6. **Écriture de `sdlc.config.yaml`.** Copier `sdlc.config.example.yaml` en `sdlc.config.yaml`
   et remplacer les valeurs par les réponses, commentaires de consigne supprimés — y compris la
   section **`paths`** (§ 13.3 : défauts du framework, ou valeurs proposées par `etat-des-lieux`
   pour un projet existant) et **`ci.mode`**. Si le fichier existe déjà : ne l'écraser qu'après
   confirmation explicite (cas `--reconfigure` / `--upgrade`).

7. **OpenSpec.** Si `openspec/` est absent à la racine, **proposer `openspec init`** (commande
   exécutée par l'humain) : sans OpenSpec, l'étape 3 (specs) ne peut pas produire de change. Ne
   pas l'initialiser d'office.

8. **Génération des adaptateurs.**
   ```sh
   python3 .agents/skills/sdlc-init/scripts/render_adapters.py . --dry-run   # vérifier
   python3 .agents/skills/sdlc-init/scripts/render_adapters.py .             # écrire
   ```
   Le script lit `sdlc.config.yaml` (PyYAML s'il est présent, sinon un analyseur du
   sous-ensemble de `sdlc.config.example.yaml`), copie depuis `.sdlc/templates/adapters/<outil>/` les
   fichiers des seuls outils activés, remplace les marqueurs `{{…}}`, retire les commentaires de
   génération, **n'écrase jamais un fichier existant sans `--force`** et affiche chaque action.
   Les fichiers `.claude/settings.json` et `opencode.json` sont **fusionnés** avec l'existant.
   Pour un `CLAUDE.md` existant, les consignes propres à Claude Code sont insérées (ou remplacées)
   dans un **bloc délimité** `<!-- sdlc-claude:begin vX.Y.Z -->` … `<!-- sdlc-claude:end -->`
   placé juste après `@AGENTS.md` ; le contenu de l'humain est conservé et un second passage sans
   changement n'écrit rien. `CLAUDE.md` absent est créé avec `@AGENTS.md` puis le même bloc. Le
   script inscrit les adaptateurs dans `.sdlc/manifest.json` (section `adapters` : fichiers créés
   avec leur empreinte, entrées ajoutées aux fichiers fusionnés) pour que `bin/sdlc-install
   --uninstall` puisse les retirer ; il écrit ce manifeste de façon atomique et sans casser le
   format lu par l'installateur.

9. **Rappel « trusted » pour Codex.** Si Codex est retenu, **signaler explicitement à l'humain**
   que la configuration et les règles de `.codex/` ne se chargent que si le projet est marqué
   « trusted » par Codex. Tant qu'il ne l'est pas, `config.toml`, `agents/*.toml` et
   `rules/sdlc.rules` sont ignorés et le git en écriture n'est pas bloqué par les règles.

10. **Sortie.** Lister les fichiers écrits, l'agent orchestrateur, les exécutants, la cible de CI
   et les cibles de déploiement. Signaler les marqueurs non résolus et les avertissements du
   script.

## Livrables et chemins exacts

- `sdlc.config.yaml` (racine) — configuration du projet (§ 4 de la spec), avec la section
  **`paths`** (§ 13.3) et **`ci.mode`** (§ 13.4).
- Pour un projet `existing` : `docs/00-cadrage/etat-des-lieux.md` (produit par `etat-des-lieux`,
  étape 0b) et la proposition de `openspec init` si `openspec/` est absent.
- Adaptateurs des outils retenus, aux emplacements indiqués par les `README.md` de
  `.sdlc/templates/adapters/` :
  - Claude Code : `CLAUDE.md`, `.claude/settings.json`, `.claude/agents/*.md`,
    `.claude/commands/*.md`.
  - Codex : `.codex/config.toml`, `.codex/agents/*.toml`, `.codex/rules/sdlc.rules`.
  - OpenCode : `opencode.json`, `.opencode/agent/*.md`, `.opencode/command/*.md`.
- Arborescence de travail attendue par le framework (créée à la demande par la première skill
  qui écrit dedans) : `docs/00-cadrage/`, `docs/architecture/adr/`, `docs/ops/`, `docs/recette/`,
  `docs/incidents/`, `docs/retro/`, `docs/client/`, `docs/journal/`, `docs/suivi/`,
  `docs/metrics/`, `openspec/`, `reports/` (non versionné).

## Critères de fin

- [ ] `sdlc.config.yaml` existe, est complet (§ 4) et a été confirmé par l'humain.
- [ ] La section `paths` (§ 13.3) et `ci.mode` (§ 13.4) sont écrites.
- [ ] Pour `kind: existing`, `etat-des-lieux` a été lancée et `openspec init` a été proposé si
      `openspec/` est absent.
- [ ] Les adaptateurs des seuls outils activés sont présents à leur emplacement.
- [ ] Aucun marqueur `{{…}}` connu ne subsiste dans les fichiers générés.
- [ ] Le cas d'un seul agent est reflété dans `orchestrator` / `executors`.
- [ ] Si Codex est retenu, l'humain a été averti du statut « trusted » à obtenir.

## Gate et responsable

- Gate : **confirmation du récapitulatif** (§ 5, étape 0).
- Responsable : `gates.default` dans `sdlc.config.yaml` (par défaut `toi`) — c'est l'humain qui
  confirme ; l'agent n'écrit rien avant.

## Correspondance des outils

| Besoin | Claude Code | Codex | OpenCode |
|---|---|---|---|
| Poser les questions | outil de question natif | texte à choix numérotés (non interactif) | outil de question natif |
| Règles lues nativement | `CLAUDE.md` (`@AGENTS.md`) | `AGENTS.md` | `AGENTS.md` |
| Lancement non interactif | `claude -p` | `codex exec -s <sandbox> -m <modèle>` | `opencode run` |
| Config à charger « trusted » | sans objet | oui (`.codex/`) | sans objet |
| Fichiers fusionnés, jamais écrasés | `.claude/settings.json` | aucune (fichiers ordinaires) | `opencode.json` |

## Pièges

- **Ne pas écrire avant confirmation.** Le récapitulatif est un gate humain.
- **Ne proposer que les CLI détectées** : une CLI absente rend l'outil inutilisable.
- **`restreint`** : ne retenir que des modèles locaux ; un agent distant est alors incohérent.
- **Marqueurs non résolus** : un `{{cli-<outil>}}` sans `agents.<outil>.cli` dans la config
  laisse le fichier invalide ; le script l'affiche en avertissement, corriger la config.
- **`--force` est destructeur** pour les fichiers ordinaires ; les deux fichiers JSON de config
  sont toujours fusionnés, jamais écrasés.
- **Codex non « trusted »** : ne pas lancer d'exécutant Codex avant l'approbation du projet.
- **Git réservé à l'humain** : `sdlc-init` n'exécute aucune commande git en écriture.
- **`CLAUDE.md` existant** : ne jamais le réécrire en entier ; seules les consignes du bloc
  `sdlc-claude` sont (re)posées, juste après `@AGENTS.md`.
- **Manifeste** : la section `adapters` de `.sdlc/manifest.json` est la seule source de la
  désinstallation des adaptateurs ; ne pas l'éditer à la main.
- **Secrets** : ne jamais lire `.env*` (sauf `.env.example`), `*.pem`, `*.key`, `secrets/`.
