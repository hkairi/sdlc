# Tâches — construction du framework

Référence : [workflow-sdlc.md](workflow-sdlc.md). Exécutant : OpenCode. Orchestrateur et relecteur : Claude Code.

## 1. Socle et configuration
- [x] 1.1 `AGENTS.md` : principes du § 2, règle de premier lancement (`sdlc-init` si `sdlc.config.yaml` absent), rôles, conventions de rédaction, Definition of Done, liste des skills
- [x] 1.2 `CLAUDE.md` : `@AGENTS.md` + spécificités Claude Code (listes d'outils comme levier fiable, pas de git en écriture)
- [x] 1.3 `README.md` : objet, installation dans un projet, premier lancement, arborescence, liens vers la spec et les schémas
- [x] 1.4 `sdlc.config.example.yaml` : toutes les clés du § 4, commentées, valeurs autorisées indiquées
- [x] 1.5 Lien symbolique `.claude/skills -> ../.agents/skills` et arborescence `templates/` vide prête

## 2. Gabarits documentaires (`templates/docs/`)
- [x] 2.1 `brief.md`, `exigences-nf.md`, `etat-des-lieux.md`
- [x] 2.2 `adr.md` (format avec statut, contexte, décision, conséquences, alternatives) et `adr-index.md`
- [x] 2.3 `menaces.md` (analyse STRIDE légère)
- [x] 2.4 `runbook.md` et `runbook-fiche.md`
- [x] 2.5 `recette.md` (matrice scénario → test → résultat)
- [x] 2.6 `change-request.md`, `incident-post-mortem.md`, `retro.md`, `client-report.md`, `release-notes.md`

## 3. CI et déploiement
- [x] 3.1 `templates/scripts/ci.sh` : contrat de sortie du § 10, sections par stack, seuils lus dans la config
- [x] 3.2 `templates/ci/{github-actions,gitlab-ci,forgejo-actions,jenkins,none}/`
- [x] 3.3 `templates/deploy/<profil>/` pour les 8 profils : `README.md`, `deploy.md`, `runbook-sections.md`

## 4. Adaptateurs et passation
- [x] 4.1 `templates/adapters/claude/` : `CLAUDE.md`, `settings.json`, agents `implementer`, `reviewer`, `doc-writer`, `spec-challenger`, commandes
- [x] 4.2 `templates/adapters/opencode/` : `opencode.json`, agents, commandes
- [x] 4.3 `templates/adapters/codex/` : `config.toml`, agents `.toml`, `rules/sdlc.rules`
- [x] 4.4 `templates/handoff/input.md` et `report.schema.json`

## 5. Skills de cadrage et de conception
- [x] 5.1 `sdlc-init`
- [x] 5.2 `etat-des-lieux`, `cadrage`, `adr`, `spec-review`, `tdd`

## 6. Skills de construction et d'exploitation
- [x] 6.1 `ci-setup`, `recette`, `deploy-procedure`, `runbook`, `changelog`
- [x] 6.2 `change-request`, `hotfix`, `retro`, `metrics`, `client-report`

## 7. Tableau de bord `suivi-projet`
- [x] 7.1 `collect.py` : normalisation des sources du § 11, avec jeux d'essai dans `tests/fixtures/`
- [x] 7.2 `generate.py` + gabarit dérivé de la maquette
- [x] 7.3 Tests automatisés (collecte et génération) et `SKILL.md`

## 8. Évolution de la skill `suivi-taches` (copie du dépôt)
- [x] 8.1 État de référence dans `docs/suivi/state.json` (format partagé avec `suivi-projet`) ; le HTML devient un rendu généré
- [x] 8.2 Scripts `track*.py` qui écrivent l'état JSON puis régénèrent le HTML ; migration depuis un suivi HTML existant
- [x] 8.3 Rôles par tâche : exécutant, relecteur (≠ auteur), itération de revue, escalade, « prêt à commiter » avec message proposé
- [x] 8.4 Lecteur Markdown dans le suivi (proposal, design, tasks, deltas de spec)
- [x] 8.5 Portabilité : chemins `.agents/skills/`, vérifications lues dans `sdlc.config.yaml` et `scripts/ci.sh`, plus de commandes propres à un projet

## 9. Installation dans un projet existant
- [x] 9.1 Installateur `bin/sdlc-install` : espace `.sdlc/`, manifeste sha256, `--dry-run`, idempotence, conflits de skills signalés
- [x] 9.2 Fusion non destructive : blocs délimités dans `AGENTS.md` et `.gitignore`, `@AGENTS.md` dans `CLAUDE.md`, liens `.claude/skills`
- [x] 9.3 `--upgrade` (fichiers non modifiés seulement) et `--uninstall`
- [x] 9.4 Section `paths` et liens `.sdlc/` dans le dépôt du framework ; plus aucune référence en dur à `templates/` ni `docs/conception/`
- [x] 9.5 `sdlc-init` et `etat-des-lieux` : parcours projet existant (pré-remplissage, `openspec init`, specs de référence de l'existant)
- [x] 9.6 `ci-setup` : `ci.mode` integrate | replace | none et réutilisation des commandes existantes
- [x] 9.7 Tests de bout en bout sur projets existants simulés (Django avec `templates/`, Node avec GitHub Actions et OpenSpec)

## 10. Écarts du § 13 révélés par les tests de bout en bout
- [x] 10.1 `CLAUDE.md` existant : bloc délimité `sdlc-claude` avec les consignes propres à Claude Code, inséré après `@AGENTS.md`, idempotent
- [x] 10.2 Adaptateurs générés inscrits dans `.sdlc/manifest.json` (fichiers créés et entrées ajoutées aux fichiers fusionnés)
- [x] 10.3 `--uninstall` retire aussi les adaptateurs non modifiés, les entrées ajoutées, le bloc Claude et les dossiers vides ; tests d'installation et de bout en bout étendus

## 11. Plugin OpenCode `ai-sdlc-tracker` (copie distribuée)
- [x] 11.1 Copier le plugin dans l'adaptateur OpenCode
  - Technique : copie depuis le dépôt `engagements` (`.opencode/plugins/ai-sdlc-tracker/`) vers `templates/adapters/opencode/plugins/ai-sdlc-tracker/` : `index.ts`, `core.ts`, `types.ts`, `tools/`, `hooks/`, `package.json`, `.gitignore`, et un `GUIDE.md` qui documente la limite du modèle d'état. Les tests restent dans le dépôt d'origine (ils s'appuient sur ses fixtures) et `node_modules/` n'est jamais copié.
  - Fichiers : `templates/adapters/opencode/plugins/ai-sdlc-tracker/**`
  - Acceptation :
    - le dossier contient les 19 fichiers attendus, sans `tests/` ni `node_modules/`
    - `GUIDE.md` dit explicitement que le plugin attend `openspec/` + `docs/suivi-*.html` et reste inerte dans un projet du framework tant que l'adaptation à `state.json` n'est pas faite
  - Tests : `find templates/adapters/opencode/plugins/ai-sdlc-tracker -type f | wc -l` (19)

- [x] 11.2 Distribuer le plugin : copie récursive des sous-dossiers d'adaptateur
  - Technique : ajout de `("plugins", ".opencode/plugins")` à `SUB_DIRS["opencode"]` et passage de `iterdir()` à `rglob("*")` avec conservation du chemin relatif et exclusion de `node_modules` ; les dossiers plats (`agent`, `command`) se comportent comme avant.
  - Fichiers : `.agents/skills/sdlc-init/scripts/render_adapters.py`
  - Acceptation :
    - dans un projet vide, `render_adapters.py` avec `opencode.enabled: true` crée `.opencode/plugins/ai-sdlc-tracker/index.ts`, et le fichier figure dans `.sdlc/manifest.json`
    - un second passage n'écrit rien (idempotence)
    - `--uninstall` retire le plugin et les dossiers vides
    - les tests d'installation passent (28 tests)
  - Tests : `python3 -m unittest tests.install.test_sdlc_install -v`

- [x] 11.3 Documenter l'adaptateur et la limite du plugin
  - Technique : ligne de destination dans le tableau du README de l'adaptateur et encadré « limite connue » renvoyant au `GUIDE.md` ; mention explicite de ne pas activer le plugin sans l'avoir vérifié dans le projet cible.
  - Fichiers : `templates/adapters/opencode/README.md`
  - Acceptation :
    - le tableau liste `plugins/ai-sdlc-tracker/**` → `.opencode/plugins/ai-sdlc-tracker/**`
    - la limite du modèle `state.json` est écrite sans laisser croire à une intégration
  - Tests : relecture (pas de test automatisé pour un README)

- [x] 11.4 Adapter le plugin au modèle d'état du framework (`docs/suivi/state.json`)
  - Technique : remplacer la lecture/écriture HTML par les scripts `track.py` / `track_phase.py` du framework et le format `state.json` (schéma 1) ; typer les rôles (exécutant, relecteur ≠ auteur, itérations de revue) ; porter les tests dans le framework.
  - Fichiers : `templates/adapters/opencode/plugins/ai-sdlc-tracker/**`, `tests/`
  - Acceptation :
    - le plugin agit sur `docs/suivi/state.json` et le HTML n'est plus la source de vérité
    - la règle « relecteur ≠ auteur » du framework est appliquée
    - les tests du plugin passent dans un projet du framework
  - Tests : `node --test` dans le dossier du plugin + scénario dans un projet jetable

- [x] 11.5 Faire du gabarit le foyer unique (tests, CI, fixtures autonomes)
  - Technique : tests déplacés dans le gabarit avec des fixtures locales (`tests/fixtures/repo/` : `check_sync.py`, `scripts/suivi/`, change `add-x`, suivis mono et multi, baseline) pour ne dépendre d'aucun dépôt hôte ; `sdlc_doctor` lit son propre `package.json` ; workflow CI (Node 22/24/26) déplacé dans le framework ; `render_adapters.py` exclut `tests/`.
  - Fichiers : `templates/adapters/opencode/plugins/ai-sdlc-tracker/{tests,tsconfig.json,package.json,README.md}`, `.github/workflows/ai-sdlc-tracker.yml`, `.agents/skills/sdlc-init/scripts/render_adapters.py`
  - Acceptation :
    - `npm test` dans le gabarit : 77 tests, 0 échec, sans accès au dépôt `engagements`
    - `npm run typecheck` : exit 0
    - une installation ne reçoit ni `tests/` ni `node_modules/`
    - le workflow CI pointe sur le dossier du gabarit
  - Tests : `npm test`, `npm run typecheck`, `render_adapters.py` dans un projet vide

- [x] 11.6 Contrôler la dérive gabarit → installation
  - Technique : `bin/plugin-sync-check` compare les empreintes en ignorant `node_modules/`, `tests/`, `README.md` et `GUIDE.md` ; l'installation d'`engagements` est resynchronisée ; le contrôle a détecté une divergence réelle (`tools/doctor.ts`) avant correction.
  - Fichiers : `bin/plugin-sync-check`, installation `engagements/.opencode/plugins/ai-sdlc-tracker/`
  - Acceptation :
    - le contrôle renvoie 0 sur une installation synchronisée (24 fichiers)
    - il renvoie 1 en nommant le fichier divergent (constaté sur `doctor.ts`)
    - l'installation ne contient ni `tests/` ni workflow CI
  - Tests : `bin/plugin-sync-check --target …`
