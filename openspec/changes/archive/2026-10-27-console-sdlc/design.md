## Context

La Console SDLC est une application locale qui agrège les artefacts du framework
(`docs/suivi/state.json`, `openspec/`, `reports/`, `runs.jsonl`, `deploys.jsonl`, documents)
et les rend exploitables par un orchestrateur humain.

Contraintes : local d'abord, SQLite, pas de lock-in IDE ni d'agent, pas de SaaS, aucune
authentification en MVP, écoute `127.0.0.2`, 12 mois de rétention configurable. Le cahier
des charges `docs/00-cadrage/cahier-des-charges-web.md` est la référence fonctionnelle
détaillée ; les ADR-001 à ADR-006 tranchent les décisions structurantes.

## Goals / Non-Goals

**Goals:**

- Une vue unique et fiable de l'état du projet, des gates, de l'équipe et du processus.
- Des gates calculés depuis des preuves, avec dérogations datées et audit.
- Une revue indépendante (autre agent, autre modèle) avec une fiche de décision lisible.
- Un runner d'agents contrôlé : préflight, budget, timeout, annulation, environnement purgé.
- Un fichier de suivi généré et ouvert dès qu'il est prêt.
- Une application locale sûre par défaut, testable et documentée.

**Non-Goals:**

- SaaS multi-tenant, SSO, RBAC avancé, collaboration temps réel.
- Remplacement de Git, de la CI, d'OpenSpec ou des agents.
- PostgreSQL, haute disponibilité, scalabilité horizontale (conception compatible seulement).
- Authentification en MVP ; elle sera conçue avant toute exposition réseau.
- Bitbucket, Azure DevOps, application mobile native, extension IDE.

## Decisions

### Architecture

- **Frontend** React 19 + TypeScript + Vite, build embarqué, servi par FastAPI (ADR-001).
- **Backend** Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 (ADR-002).
- **SQLite** 3.45+, WAL, `foreign_keys=ON`, `busy_timeout=5000`, un seul écrivain.
- **Local** : écoute `127.0.0.2:8765`, aucune auth, validation `Host`/`Origin`, CSRF (ADR-003).

### Modèle multi-dépôts

- `projects` → N `repositories` (`provider` github/gitlab, `local_path`, `dedup_group`).
- `persons` canoniques + `person_identities` (email, provider, external_id).
- Unicité de l'email **par projet** ; `display_name` non unique avec fusion manuelle auditée.
- `commit_fingerprint = sha256(sha + "\n" + email_normalisé + "\n" + author_date_utc)`.
- Déduplication par empreinte et `dedup_group` ; badge « dédoublonnage appliqué ».
- `feature_repositories` et `task_repositories` ; gate de feature = conjonction des dépôts.

### Gates

- Un verdict par gate (`pass`, `warn`, `fail`, `waived`, `not_applicable`, `not_run`).
- `not_run` sur un contrôle attendu du tier = `fail` ; hors tier = `not_applicable`.
- Preuves : JUnit, Cobertura/lcov/JaCoCo, SARIF, `reports/perf/*.json`.
- Seuils dans `sdlc.config.yaml` ; `gates.config_fingerprint` invalide le cache.
- Tests, couverture (global, lignes modifiées, fichier), sécurité avec atteignabilité,
  performance observée vs statique, données (migration, PII, sauvegarde), i18n, langages.

### Revue et agents

- Relecteur éligible au niveau maximal disponible (agent, modèle, famille) ; dégradé =
  dérogation humaine auditée.
- Paquet aveugle (spec, diff, preuves, ADR), rapport JSON + fiche de décision.
- Runner : modèles de commande, préflight, groupe de processus, budget échantillonné,
  timeout, concurrence, env purgé, logs échappés, audit (ADR-005).

### Audit, rétention, sauvegarde

- Chaîne d'audit par projet : `hash = sha256(prev_hash + payload)`, `generation`.
- 12 mois par défaut ; audit exclu de la purge automatique ; purge d'audit explicite avec
  ancrage et sauvegarde vérifiée (ADR-006).
- Sauvegarde globale du fichier SQLite ; restauration testée ; âge affiché.
- Purge dans la même file que l'ingestion ; logs et rapports inclus.

### Interface

- 12 vues, sélecteur de dépôt, états chargement/vide/erreur/périmé/désactivé.
- SSE pour logs, ingestion, gates ; `aria-live`, focus stable, textes échappés.
- Suivi généré et ouvert automatiquement une seule fois (`ui.open_suivi_on_ready`).
- Suivi synchronisé tâche par tâche : `tasks.md`, `state.json` et HTML mis à jour dans la
  même opération logique, watcher sur les modifications externes, SSE `suivi.updated`.
- Listes paginées côté serveur (`limit`/`offset`/`total`, 50 par défaut).
- CSP restrictive, Markdown et logs en texte échappé, redaction des exports et `stats_json`.
- Chemins d'ingestion résolus en absolu, refus de `..` et de tout chemin hors périmètre.

## Risks / Trade-offs

- **SQLite** : un seul écrivain, verrous sur les longues ingestions → file unique, WAL,
  lots courts, `busy_timeout`.
- **Multi-dépôts** : identités et déduplication complexes → `persons`, empreinte, tests.
- **Runner d'agents** : injection, coût, orphelins, fuite de jetons → modèles de commande,
  budget, groupe de processus, env purgé, audit.
- **Sans auth** : tout processus local peut appeler l'API → loopback, `Host`/`Origin`,
  CSRF, limite documentée ; token avant LAN.
- **Détection de processus** : faux positifs → confiance, preuves, surcharge auditée, corpus.
- **Faux positifs sécurité/performance** : distinguer bloquant et alerte, dérogation datée.
- **Périmètre** : risque de dérive → MVP local, non-goals explicites, ADR.

## References

- Cahier des charges : `docs/00-cadrage/cahier-des-charges-web.md`
- Brief : `docs/00-cadrage/brief.md`
- Exigences NF : `docs/00-cadrage/exigences-nf.md`
- ADR : `docs/architecture/adr/README.md`
- Menaces : `docs/architecture/menaces.md`
- Revue 1 : `docs/00-cadrage/revue-cahier-des-charges-web.md`
- Revue 2 : `docs/00-cadrage/revue-cahier-des-charges-web-2.md`
