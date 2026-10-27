# Architecture du framework AI-DRIVEN-SDLC

> Vue d'ensemble de la structure et des flux. Spécification de référence :
> [`../conception/workflow-sdlc.md`](../conception/workflow-sdlc.md).

## 1. Vue d'ensemble

Le dépôt est un **framework réutilisable** qui s'installe dans un projet (nouveau ou existant)
pour piloter le SDLC avec des agents IA (Claude Code, Codex, OpenCode), sous contrôle humain.

```
.
├── AGENTS.md                    # règles communes (lues par Codex/OpenCode)
├── CLAUDE.md                    # @AGENTS.md + spécificités Claude Code
├── sdlc.config.yaml             # configuration du projet (générée par sdlc-init)
├── sdlc.config.example.yaml     # modèle commenté
├── .sdlc/                       # espace de noms du framework (liens vers templates/spec dans ce dépôt)
│   ├── templates/ → ../templates
│   └── workflow-sdlc.md → ../docs/conception/workflow-sdlc.md
├── .agents/skills/<skill>/      # SOURCE UNIQUE des 18 skills
│   └── SKILL.md (+ scripts/, assets/, references/, tests/)
├── .claude/skills → ../.agents/skills
├── templates/
│   ├── docs/                    # 14 gabarits documentaires
│   ├── ci/<outil>/              # pipelines (github-actions, gitlab-ci, forgejo-actions, jenkins, none)
│   ├── scripts/ci.sh            # contrôles uniques (local + CI)
│   ├── deploy/<profil>/         # 8 profils (deploy.md, runbook-sections.md, README.md)
│   ├── adapters/<outil>/        # configs des 3 outils (+ plugin OpenCode)
│   └── handoff/                 # contrat de passation (input.md, report.schema.json)
├── bin/
│   ├── sdlc-install             # installateur (Python 3.9+, stdlib)
│   ├── sdlc_install_lib.py
│   └── plugin-sync-check        # contrôle de dérive gabarit → installation
├── scripts/
│   ├── ci.sh                    # CI du dépôt (Console) — contrat de sortie reports/
│   ├── check_sync.py            # contrôle state.json ↔ tasks.md
│   ├── check_config.py          # lint de sdlc.config.yaml
│   ├── check_completeness.py    # non-régression spec ↔ fichiers
│   ├── handoff_check.py, learnings.py, junit_unittest.py
│   └── tests/                   # tests shell
├── apps/console/                # Console SDLC (dogfooding : FastAPI + React/Vitest + SQLite)
├── openspec/                    # changes (actifs/archivés) + specs de référence
├── docs/                        # livrables documentaires (cadrage, ADR, ops, recette, retro…)
└── reports/                     # sorties de scripts/ci.sh (non versionné)
```

## 2. Modèle d'installation

- **Espace de noms** : tout ce qui appartient au framework vit sous `.sdlc/` (hors skills et
  adaptateurs), pour ne pas polluer le projet cible.
- **Installateur** (`bin/sdlc-install`) : copie `.sdlc/` et `.agents/skills/`, fusionne
  `AGENTS.md`/`CLAUDE.md`/`.gitignore` par blocs délimités, ne touche jamais `README.md`,
  `docs/`, `templates/` ni la CI existante. Manifeste `.sdlc/manifest.json` (sha256) pour
  `--upgrade`/`--uninstall`.
- **Chemins configurables** : toutes les skills lisent `paths.*` de `sdlc.config.yaml`
  (`templates`, `spec`, `docs`, `adr`, `ops`, `suivi`…).

## 3. Configuration (`sdlc.config.yaml`)

Seule source de vérité des rôles et choix du projet : version, `project`, `agents`,
`orchestrator`, `executors`, `confidentiality`, `providers_allowed`, `ci`, `deploy`,
`organisation`, `gates`, `dashboard`, `paths`. Schéma extensible (la Console ajoute ses
propres clés, validées par `apps/console/src/sdlc_console/config.schema.json`).

## 4. Skills

Chaque skill est un dossier `.agents/skills/<nom>/` avec un `SKILL.md` (frontmatter `name` +
`description`, corps : objectif, entrées, étapes, livrables, critères de fin). Les scripts
(`scripts/`), gabarits (`assets/`) et références (`references/`) sont colocalisés. Les modes
(lecture seule, écriture restreinte) sont contraints par les **agents** des adaptateurs, pas
par les skills.

## 5. Adaptateurs

`templates/adapters/<outil>/` est généré par `sdlc-init` (`render_adapters.py`) pour les outils
retenus. Il fournit les agents (`implementer`, `reviewer`, `doc-writer`, `spec-challenger`),
les permissions (git en écriture et secrets refusés) et les commandes. Le plugin OpenCode
`ai-sdlc-tracker` (foyer : `templates/adapters/opencode/plugins/ai-sdlc-tracker/`) est distribué
vers `.opencode/plugins/` ; `bin/plugin-sync-check` contrôle la non-dérive.

## 6. Suivi d'avancement

```
tasks.md ──generate/track──▶ docs/suivi/state.json ──render──▶ docs/suivi-<id>.html
                                   ▲                                   │
                                   └──────── track/phase (drafts) ─────┘
```

- `docs/suivi/state.json` (schéma 1) = **source de vérité** : features, lots, tâches, phases,
  rôles, historique.
- `docs/suivi-<id>.html` = **rendu généré** (mono/multi), charte commune, thème clair/sombre,
  lecteur Markdown, lien vers le rapport de clôture.
- `scripts/check_sync.py` vérifie la synchronisation `state.json` ↔ `tasks.md`.
- Le plugin OpenCode applique la règle « relecteur ≠ auteur » et les gates en session.

## 7. CI et déploiement

`scripts/ci.sh` est la **seule définition** des contrôles ; le pipeline de l'outil de CI ne fait
que l'appeler. Sorties normalisées dans `reports/` (`junit/`, `coverage/`, `security/`, `lint/`,
`summary.json`). Les profils de déploiement fournissent `deploy.md` (étapes, rollback, sauvegarde)
et `runbook-sections.md`.

## 8. Console SDLC

Application locale de démonstration (dogfooding) : `apps/console/` (backend FastAPI + SQLite via
Alembic, frontend React/Vitest). Elle consomme `sdlc.config.yaml`, lit `openspec/`, `reports/`,
`docs/`, et produit son propre tableau de bord. Elle illustre l'usage réel du framework.

## 9. Choix structurants

- **Git réservé à l'humain** : aucun agent n'écrit dans le dépôt via git ; les agents proposent
  les messages de commit.
- **Markdown = source, HTML = rendu** : specs, ADR, procédures en Markdown ; HTML généré et
  marqué « ne pas modifier ».
- **Modes par agents, pas par skills** : les listes d'outils et permissions des adaptateurs sont
  le levier fiable.
- **Rien n'est inventé** : une donnée non mesurée s'affiche « non mesuré » (journaux vides).
