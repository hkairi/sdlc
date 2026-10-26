# Rapport qualité & complétude — Workflow SDLC

> Audit du framework **AI-DRIVEN-SDLC** (v0.1.0) au regard de sa spécification de référence `.sdlc/workflow-sdlc.md`. Ce document recense les propositions de correctifs et d'améliorations, priorisées, avec une estimation d'effort en taille de t-shirt et les fichiers concernés.

## 1. Synthèse et verdict

| Dimension | Évaluation | Constat |
|---|---|---|
| Qualité de conception | Élevée | Spec exhaustive, principes solides, format homogène des 18 skills. |
| Couverture fonctionnelle | ≈ 90 % | Templates, adaptateurs, CI, déploiement et installateur sont présents. |
| Cohérence spec ↔ code | À corriger | Drift du schéma de config, suivi désynchronisé (section 11). |
| Maturité exploitation | Partielle | Journal, métriques, incidents et CI du framework absents. |

Le framework est de **très bonne facture pour un état v0.1.0** et presque complet fonctionnellement. Les défauts sont des **écarts de cohérence** (configuration, suivi, « foyer unique » des contrôles) et une **section inachevée** (plugin OpenCode `ai-sdlc-tracker`). Les correctifs sont peu coûteux et localisés ; les améliorations visent surtout à verrouiller la cohérence dans le temps.

## 2. Points forts (à préserver)

- **Spécification de référence** complète et cohérente (13 étapes + 3 voies transverses, 13 sections).
- **Principes de sécurité** robustes : git réservé à l'humain, secrets interdits en lecture, « rien n'est inventé », contenu externe = données.
- **18 skills homogènes**, portables entre les 3 outils (frontmatter minimal, sections normalisées, chemins via `paths.*`).
- **Contrainte par listes d'outils** (pas par skills) : le bon levier pour restreindre les agents.
- **Contrat de passation formel** (`input.md` + `report.schema.json` strict) et Definition of Done opposable.
- **CI générique** (`templates/scripts/ci.sh`) modulaire, seuils lus en config, statut `not_run` (jamais de faux succès).
- **Installateur non destructif**, idempotent, avec manifeste sha256 et `--dry-run`/`--upgrade`/`--uninstall`.
- **Dogfooding réel** : le framework se pilote lui-même (change `console-sdlc`, 6 ADR, analyse STRIDE, recette, runbook).

## 3. Correctifs proposés

Les tailles d'effort suivent la légende : **XS** (< 1 h), **S** (1 h – ½ j), **M** (½ j – 2 j), **L** (2 j – 1 sem), **XL** (> 1 sem).

### C1 — Réconcilier le schéma de configuration

**Sévérité** : Critique

**Effort** : M

**Problème** : `sdlc.config.yaml` (utilisé dans ce dépôt) contient 7 sections non documentées — `database`, `quality`, `review`, `process`, `team`, `retention`, `ui` — absentes du `§4` de la spec **et** de `sdlc.config.example.yaml`. Le schéma « figé » de la spec ne reflète plus la réalité.

**Proposition** : deux options, à trancher explicitement :

- Si ces clés appartiennent au framework : les documenter dans le `§4` et dans `sdlc.config.example.yaml`.
- Si elles sont propres à la Console SDLC : les extraire vers une config applicative séparée, et rétablir un `sdlc.config.yaml` strictement conforme au schéma du framework.

**Fichiers** : `.sdlc/workflow-sdlc.md` (§4), `sdlc.config.example.yaml`, `sdlc.config.yaml`.

### C2 — Corriger `paths.spec: "openspec"` et compléter `paths.*`

**Sévérité** : Critique

**Effort** : XS

**Problème** : dans `sdlc.config.yaml`, `paths.spec` vaut `"openspec"`, alors que le `§13.3` la définit comme « le chemin de la spécification de référence » (défaut `.sdlc/workflow-sdlc.md`). Plusieurs clés `paths.*` sont par ailleurs absentes.

**Proposition** : rétablir `paths.spec: .sdlc/workflow-sdlc.md` et ajouter l'ensemble des clés `paths.*` prévues au `§13.3`. Si un autre besoin existe (référence au dossier OpenSpec), utiliser une clé dédiée distincte.

**Fichiers** : `sdlc.config.yaml` (section `paths`).

### C3 — Finaliser et resynchroniser la section 11 (plugin `ai-sdlc-tracker`)

**Sévérité** : Important

**Effort** : L

**Problème** : `docs/conception/tasks.md` marque les tâches `11.1` à `11.6` comme non faites, alors que `render_adapters.py` contient déjà les changements correspondants (entrée `("plugins", ".opencode/plugins")` dans `SUB_DIRS`, exclusion de `node_modules`/`tests`). Le suivi ne reflète pas le code.

**Proposition** : mettre `tasks.md` à jour pour refléter l'existant, puis traiter les tâches restantes : `11.4` (adapter le plugin au modèle `docs/suivi/state.json`) et `11.5` (faire du gabarit le foyer unique : tests autonomes + CI).

**Fichiers** : `docs/conception/tasks.md`, `templates/adapters/opencode/plugins/ai-sdlc-tracker/**`, `.agents/skills/sdlc-init/scripts/render_adapters.py`.

### C4 — Retirer `node_modules/` du gabarit du plugin

**Sévérité** : Important

**Effort** : XS

**Problème** : `templates/adapters/opencode/plugins/ai-sdlc-tracker/node_modules/` contient des milliers de fichiers, alors que la tâche 11.1 exige explicitement « sans `tests/` ni `node_modules/` ». Le `.gitignore` imbriqué le masque et `render_adapters.py` l'exclut de la distribution, mais sa présence physique est un risque de pollution du dépôt.

**Proposition** : supprimer `node_modules/` de l'arbre de travail, puis vérifier son statut git (`git ls-files …/node_modules`) pour s'assurer qu'aucun fichier n'est versionné.

**Fichiers** : `templates/adapters/opencode/plugins/ai-sdlc-tracker/node_modules/`.

### C5 — Trancher le « foyer unique » des contrôles (`scripts/ci.sh`)

**Sévérité** : Important

**Effort** : M

**Problème** : le principe `§10` (« `scripts/ci.sh` est la seule définition des contrôles ») est contredit en pratique : le dépôt utilise une version concrète dédiée à la Console (184 lignes) distincte du gabarit générique (605 lignes).

**Proposition** : deux options :

- Faire du gabarit le foyer unique et dériver le `ci.sh` du repo via les variables `SDLC_<CONTRÔLE>_CMD` (mécanisme déjà prévu au §13.4).
- Documenter explicitement la dérogation de dogfooding dans le README si le `ci.sh` spécifique est conservé.

**Fichiers** : `scripts/ci.sh`, `templates/scripts/ci.sh`.

### C6 — Aligner `scripts/ci.sh` sur le contrat de sortie du §10

**Sévérité** : Important

**Effort** : S

**Problème** : le `scripts/ci.sh` du dépôt écrit `reports/junit-unittest.txt` et `reports/junit-vitest.txt` (texte brut), alors que le `§10` exige des rapports JUnit en `reports/junit/*.xml`. Le gabarit, lui, respecte le contrat.

**Proposition** : produire les rapports de tests au format JUnit XML (`--junitxml`, `vitest --reporter=junit`) vers `reports/junit/`, pour que le tableau de bord consomme un format unique et conforme.

**Fichiers** : `scripts/ci.sh`.

### C7 — Ignorer `sdlc.config.yaml` dans le dépôt

**Sévérité** : Mineur

**Effort** : XS

**Problème** : `sdlc.config.yaml` est présent en untracked et n'est pas listé dans `.gitignore`. C'est une configuration locale, ce qui crée un risque de commit accidentel.

**Proposition** : ajouter `/sdlc.config.yaml` au `.gitignore` racine (en conservant `sdlc.config.example.yaml` versionné).

**Fichiers** : `.gitignore`.

### C8 — Matérialiser les répertoires d'exploitation

**Sévérité** : Mineur

**Effort** : XS

**Problème** : l'arborescence `§3` prévoit `docs/journal/` (`runs.jsonl`, `deploys.jsonl`), `docs/metrics/history.jsonl`, `docs/incidents/`, `docs/retro/` et `docs/client/` : aucun n'existe encore. Les skills `metrics`, `retro`, `client-report` s'appuient dessus.

**Proposition** : créer les répertoires (avec un `.gitkeep`) et initialiser les journaux vides dès la première délégation/le premier déploiement réels de la Console.

**Fichiers** : `docs/journal/`, `docs/metrics/`, `docs/incidents/`, `docs/retro/`, `docs/client/`.

## 4. Améliorations proposées

### A1 — Ajouter une CI au framework lui-même

**Sévérité** : Amélioration

**Effort** : M

**Proposition** : créer `.github/workflows/ci.yml` exécutant les tests `tests/install/` et `tests/e2e/`, le `npm test` + `typecheck` du plugin, et un passage de `scripts/ci.sh`. Ce dépôt pilote les autres projets : il doit être le premier couvert.

**Bénéfice** : détection automatique des régressions de l'installateur et du plugin ; crédibilité du framework « sur lui-même ».

### A2 — Linter le schéma de config contre le §4

**Sévérité** : Amélioration

**Effort** : M

**Proposition** : ajouter un contrôle qui valide `sdlc.config.yaml` contre un JSON Schema dérivé du `§4`, et qui signale toute clé non documentée (évite la réapparition du drift constaté en C1).

**Bénéfice** : cohérence permanente entre la spec et la config réelle.

### A3 — Test de non-régression de la spec

**Sévérité** : Amélioration

**Effort** : M

**Proposition** : ajouter un script de vérification statique : chaque skill citée au `§7` a son `SKILL.md`, chaque gabarit cité existe, chaque profil de déploiement et chaque outil de CI référencés disposent de leurs fichiers. À intégrer à `scripts/ci.sh`.

**Bénéfice** : garantit que la spec et l'implémentation ne divergent pas silencieusement.

### A4 — Clarifier le foyer de vérité des rendus HTML

**Sévérité** : Amélioration

**Effort** : S

**Proposition** : réduire la multiplicité des maquettes/suivis (`mockup-*.html`, `suivi-console.html`, `suivi-framework.html`) : désigner un fichier généré par finalité et documenter la correspondance maquette ↔ rendu réel.

**Bénéfice** : évite la confusion entre `suivi-projet` et `suivi-console`.

### A5 — Documenter la dérogation de dogfooding

**Sévérité** : Amélioration

**Effort** : XS

**Proposition** : ajouter une note au README expliquant pourquoi le `scripts/ci.sh` du dépôt diffère du gabarit (cas d'usage de la Console) et comment les deux sont reliés.

**Bénéfice** : lève l'ambiguïté C5/C6 pour tout nouvel intervenant.

### A6 — Renforcer la couverture de tests du framework

**Sévérité** : Amélioration

**Effort** : L

**Proposition** : étendre `tests/install/` et `tests/e2e/` : cas limites de l'installateur (conflit de skills, fichiers modifiés par l'humain, `--force`), et mesurer la couverture des scripts Python (`render_adapters.py`, `sdlc_install_lib.py`).

**Bénéfice** : fiabilité de l'installation et de la génération d'adaptateurs.

### A7 — Versionner et migrer le schéma de config

**Sévérité** : Amélioration

**Effort** : M

**Proposition** : exploiter la clé `version` déjà présente : prévoir un chemin de migration de config dans `sdlc-init --upgrade` (renommage/ajout de clés) pour accompagner les évolutions futures du schéma.

**Bénéfice** : évolutions du schéma sans rupture.

### A8 — Matrice de traçabilité étapes ↔ livrables

**Sévérité** : Amélioration

**Effort** : M

**Proposition** : ajouter au tableau de bord un onglet « workflow » qui matérialise les 13 étapes du `§5` avec, pour chacune, le livrable attendu, son chemin réel et son état (présent/absent), alimenté par le test de non-régression A3.

**Bénéfice** : visualisation instantanée de la complétude.

## 5. Tableau de complétude

| Composant | État | Observation |
|---|---|---|
| Spécification de référence | Complet | 13 sections cohérentes |
| Principes (§2) | Complet | Solides et bien articulés |
| Skills (18) | Complet | Format homogène, portables |
| Gabarits documentaires (14) | Complet | Tous présents |
| Adaptateurs (3 outils) | Complet | Agents + modes par listes d'outils |
| Contrat de passation | Complet | JSON Schema strict |
| CI générique (template) | Complet | Modulaire, seuils en config |
| Pipelines CI (5) / profils déploiement (8) | Complet | Un dossier complet par profil |
| Installateur | Complet | Testé (install/e2e) |
| Schéma de configuration | Drift | 7 sections non documentées (C1) |
| Plugin OpenCode | Inachevé | 11.1–11.6 non finalisées (C3) |
| Journal / métriques / incidents / retro / client | Absent | Étapes 9–10 non matérialisées (C8) |
| CI du framework lui-même | Absent | Pas de `.github/` (A1) |

## 6. Feuille de route priorisée

1. **Aligner la configuration sur la spec** — C1 (schéma), C2 (`paths.spec`), C7 (`.gitignore`).
2. **Assainir le plugin OpenCode** — C4 (`node_modules`) puis C3 (finaliser 11.4/11.5 et resynchroniser `tasks.md`).
3. **Restaurer le foyer unique des contrôles** — C5 (`ci.sh`), C6 (JUnit XML), A5 (documenter la dérogation).
4. **Verrouiller la cohérence** — A2 (lint de config), A3 (non-régression de la spec), A1 (CI du framework).
5. **Compléter l'exploitation et la traçabilité** — C8 (répertoires d'exploitation), A4 (foyer de vérité HTML), A6 (tests), A7 (migrations), A8 (matrice).

## 7. Récapitulatif des efforts

| Réf | Sévérité | Effort | Libellé |
|---|---|---|---|
| C1 | Critique | M | Réconcilier le schéma de configuration |
| C2 | Critique | XS | Corriger `paths.spec` et compléter `paths.*` |
| C3 | Important | L | Finaliser et resynchroniser la section 11 |
| C4 | Important | XS | Retirer `node_modules/` du gabarit |
| C5 | Important | M | Foyer unique des contrôles (`ci.sh`) |
| C6 | Important | S | Aligner `ci.sh` sur le contrat JUnit (§10) |
| C7 | Mineur | XS | Ignorer `sdlc.config.yaml` |
| C8 | Mineur | XS | Matérialiser les répertoires d'exploitation |
| A1 | Amélioration | M | CI du framework lui-même |
| A2 | Amélioration | M | Lint du schéma de config |
| A3 | Amélioration | M | Non-régression de la spec |
| A4 | Amélioration | S | Clarifier le foyer de vérité HTML |
| A5 | Amélioration | XS | Documenter la dérogation de dogfooding |
| A6 | Amélioration | L | Renforcer la couverture de tests |
| A7 | Amélioration | M | Versionner/migrer le schéma de config |
| A8 | Amélioration | M | Matrice de traçabilité étapes ↔ livrables |

**Total indicatif** : 5 × XS, 2 × S, 6 × M, 2 × L, 0 × XL — soit environ **7 à 10 jours-homme** cumulés, à affiner par l'humain.
