## Why

Le framework SDLC produit des artefacts dispersés : `docs/suivi/state.json`,
`openspec/changes/`, `reports/` (JUnit, Cobertura, SARIF), `docs/journal/*.jsonl`,
`docs/architecture/adr/`, `docs/recette/`, `docs/ops/runbook.md`.

L'orchestrateur doit aujourd'hui ouvrir une dizaine de fichiers, recouper des formats
différents et reconstruire mentalement l'état du projet. Les gates ne sont pas opposables,
la revue indépendante n'est pas traçable, l'équipe et le processus sont invisibles, et les
décisions ne sont pas conservées avec leur justification.

La Console SDLC est l'application web **locale** qui rassemble ces sources, calcule les
gates, prépare et suit la revue indépendante, et conserve les décisions humaines. Elle est
locale, utilise SQLite, écoute sur `127.0.0.2` sans authentification en MVP, et ne remplace
ni Git, ni la CI, ni OpenSpec.

## What Changes

- Nouvelle application web locale **Console SDLC** (backend Python/FastAPI, frontend React).
- Base **SQLite** en WAL, un seul écrivain, migrations Alembic.
- **Multi-dépôts** GitHub et GitLab par projet, avec identités canoniques et déduplication.
- **12 vues** : Vue d'ensemble, Features & tâches, Gates & qualité, Revue indépendante,
  Déploiements, Équipe, Processus, Sécurité, Performance & données, Agents IA,
  Documentation, Configuration.
- **Gates** calculés depuis des preuves : tests, couverture, sécurité, performance, données,
  i18n, support des langages, revue.
- **Revue indépendante** : autre agent, autre modèle, paquet aveugle, rapport structuré,
  fiche de décision, décision humaine auditée.
- **Runner d'agents** : préparation, lancement depuis l'interface, suivi, annulation, budget,
  environnement purgé, logs échappés.
- **Équipe et processus** : métriques par dépôt puis agrégées, bus factor, propriété,
  détection de flux avec confiance et surcharge.
- **Suivi** : fichier généré et ouvert automatiquement dès qu'il est prêt, synchronisé
  tâche par tâche à chaque changement de statut (`tasks.md`, `state.json`, HTML).
- **Rétention** 12 mois configurable, audit exclu de la purge automatique, sauvegarde globale.
- **Sécurité locale** : bind `127.0.0.2` uniquement, validation `Host`/`Origin`, jeton CSRF,
  aucune donnée sortante par défaut.

Décisions d'architecture : ADR-001 à ADR-006. Détail fonctionnel : cahier des charges
`docs/00-cadrage/cahier-des-charges-web.md`.

### Hors périmètre MVP

Les SHOULD/COULD suivants ne sont pas livrés dans ce change et sont explicitement reportés
en v1 : recherche globale (REQ-GEN-01), historique des runs de gate avec diff (REQ-GAT-10),
inclusion des bots (REQ-EQ-01), export JSON/CSV avancé (REQ-GEN-03, REQ-EQ-08), export de
configuration (REQ-CFG-04), carte d'activité détaillée (REQ-EQ-06), procédure de rollback
détaillée (REQ-DEP-05), activité récente et résumé équipe/processus (REQ-OV-05/06), liste des
branches et cycle time (REQ-PRO-04/05). Le reste des MUST est couvert par les deltas.

## Capabilities

### New Capabilities

- `console-core`: projets, dépôts multiples, ingestion Git/GitHub/GitLab, identités,
  features/tâches, suivi généré et ouvert automatiquement.
- `console-quality`: gates, preuves, seuils, dérogations, langages, i18n, sécurité,
  performance et données.
- `console-review`: revue indépendante, paquet aveugle, rapport, fiche de décision, décision
  humaine, runner d'agents.
- `console-team-process`: métriques d'équipe, bus factor, propriété, détection de processus,
  DORA.
- `console-ops`: déploiements, documentation, configuration, audit, rétention, sauvegarde,
  migration de schéma, diagnostic.

### Modified Capabilities

Aucune : le dépôt ne contient pas encore de specs OpenSpec.

## Impact

- **Nouveaux répertoires** : `apps/console/` (backend, frontend, migrations), `openspec/`,
  `docs/00-cadrage/`, `docs/architecture/`.
- **Dépendances** : Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, React 19,
  TypeScript, Vite ; Node 22+ au build uniquement.
- **Données** : SQLite `data/sdlc.sqlite3`, sauvegardes globales, exports JSON/CSV.
- **Sécurité** : bind loopback, `Host`/`Origin`, CSRF, redaction, audit chaîné, runner
  d'agents avec budget et groupe de processus.
- **Exploitation** : `sdlc-console` CLI, `doctor`, `backup`/`restore`, `purge`, `schema`.
- **Références** : `docs/00-cadrage/brief.md`, `exigences-nf.md`,
  `cahier-des-charges-web.md` ; ADR-001 à ADR-006 ; `docs/architecture/menaces.md`.
