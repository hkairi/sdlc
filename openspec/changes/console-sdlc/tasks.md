# Tasks — console-sdlc

## 1. Socle

- [x] 1.1 Initialiser `apps/console/` (backend FastAPI, frontend React/Vite, `pyproject.toml`, `package.json`) et la commande `sdlc-console`
- [x] 1.2 Écrire le schéma JSON de `sdlc.config.yaml` et la validation au démarrage
- [x] 1.3 Créer la base SQLite, les réglages WAL/foreign_keys/busy_timeout et les migrations Alembic
- [x] 1.4 Implémenter `init`, `serve`, `doctor` et `schema status|migrate` ; écoute `127.0.0.2` uniquement
- [x] 1.5 Implémenter la validation `Host`/`Origin`/`Referer`, le refus de tout bind hors `127.0.0.0/8`, le jeton CSRF (`GET /api/csrf`, `X-SDLC-CSRF`), CORS désactivé et `Content-Type: application/json` obligatoire
- [x] 1.6 Ajouter les tests de sécurité locale (bind, Host, Origin, Referer, CSRF, secrets), la matrice CI macOS/Linux/Windows-WSL et le test de joignabilité WSL2
- [x] 1.7 **[1.2]** Confiner les chemins d'ingestion : résolution absolue, refus de `..` et de tout chemin hors périmètre, test de path traversal

## 2. Projets, dépôts et ingestion

- [x] 2.1 **[1.3]** Implémenter `projects` et `repositories` (multi-dépôts, dépôt principal, `retired_at`, `dedup_group`)
- [x] 2.2 **[2.1]** Implémenter `persons` et `person_identities` (emails, comptes GitHub/GitLab, bots, fusion auditée)
- [x] 2.3 **[2.2]** Implémenter l'ingestion Git incrémentale et idempotente (`git log --numstat`, trailers IA, `commit_fingerprint`)
- [x] 2.4 **[2.1]** Implémenter les collecteurs GitHub et GitLab (PR/MR, revues, approbations, ETag, pagination, backoff, mode fichier)
- [x] 2.5 **[2.3, 2.4]** Ajouter les fixtures hors réseau GitHub/GitLab/CI et les tests d'échec (quota, jeton, réseau)
- [x] 2.6 **[2.2, 2.3]** Implémenter la déduplication multi-dépôts, le badge « dédoublonnage appliqué » et l'agrégation sans double comptage
- [x] 2.7 **[2.1]** Implémenter l'archivage/suppression d'un dépôt et la réélection du dépôt principal
- [x] 2.8 **[1.3]** Ingérer `runs.jsonl` et `deploys.jsonl` (agents, déploiements, versions, statuts, rollbacks)

## 3. Features, tâches et suivi

- [x] 3.1 **[1.3]** Implémenter `features`, `tasks`, `feature_repositories` et `task_repositories`
- [x] 3.2 **[3.1]** Ingérer `docs/suivi/state.json` et `openspec/changes/*/tasks.md` ; signaler les incohérences
- [x] 3.3 **[3.1]** Implémenter la matrice de traçabilité exigence → scénario → test → tâche
- [x] 3.4 **[3.2]** Générer le fichier de suivi (HTML/JSON) et les routes `/api/projects/{id}/suivi` et `/suivi/status`
- [x] 3.5 **[3.4]** Ouvrir automatiquement la vue Suivi dès qu'elle est prête, une seule fois, avec lien persistant (`ui.open_suivi_on_ready`)
- [x] 3.6 **[3.5]** Ajouter le scénario de bout en bout « le suivi s'ouvre dès qu'il est prêt » et le test d'accessibilité
- [x] 3.7 **[3.1]** Vue d'ensemble : KPI avec source et « non mesuré », décisions en attente, pipeline, risques par catégorie
- [x] 3.8 **[3.1, 3.2]** Liste et détail des features/tâches : filtres, rapport de tâche, incohérences `tasks.md` ↔ `state.json`
- [x] 3.9 **[3.1, 3.4]** API `PATCH /tasks/{task_id}` et CLI `task set` : mise à jour atomique de `tasks.md`, `state.json` et HTML en < 2 s
- [x] 3.10 **[3.9]** Watcher sur `tasks.md` et `state.json` : resynchronisation des modifications externes, détection de conflit, SSE `suivi.updated`
- [x] 3.11 **[3.9, 3.10]** Tests de non-régression : `done` ⇔ case cochée, pas de mode lot, échec d'écriture sans incohérence

## 4. Gates et qualité

- [x] 4.1 **[1.2, 1.3]** Implémenter le moteur de gates, les verdicts et `reports/gates/*.json`
- [x] 4.2 **[4.1]** Implémenter le gate tests (JUnit, échecs, ignorés, instables, quarantaine)
- [x] 4.3 **[4.1]** Implémenter le gate couverture (global, lignes modifiées, fichier) et les preuves Cobertura/lcov/JaCoCo
- [x] 4.4 **[4.1]** Implémenter le gate sécurité (SARIF, atteignabilité, secrets, conteneurs, IaC) et le SBOM
- [x] 4.5 **[4.1]** Implémenter le gate performance (budgets, `reports/perf/*.json`, signaux statiques)
- [x] 4.6 **[4.1]** Implémenter le gate données (migration destructive, PII, sauvegarde/restauration, rétention)
- [x] 4.7 **[4.1]** Implémenter les gates i18n et support des langages par tier, avec `not_run` par contrôle attendu
- [x] 4.8 **[4.1]** Implémenter les dérogations (finding ou gate run, expiration, approbateur, audit)
- [x] 4.9 **[4.1]** Relier les seuils à `sdlc.config.yaml`, stocker `config_fingerprint` et invalider le cache

## 5. Équipe et processus

- [x] 5.1 **[2.2, 2.6]** Implémenter les métriques d'équipe par personne et par dépôt (commits, MR, revues, approbations, IA)
- [ ] 5.2 **[5.1]** Implémenter le bus factor, la propriété par zone (CODEOWNERS) et les alertes
- [ ] 5.3 **[5.1]** Implémenter la chaîne de validation auteur → relecteur agent → humain
- [ ] 5.4 **[2.1, 2.4]** Implémenter la détection de processus (branches, merges, tags, protections, CI) et la confiance
- [ ] 5.5 **[5.4]** Implémenter le profil par dépôt, l'agrégation projet et la surcharge auditée
- [ ] 5.6 **[5.1, 5.4]** Implémenter les métriques DORA (lead time, fréquence, CFR, MTTR) avec sources et « non mesuré »
- [ ] 5.7 **[5.4]** Ajouter le corpus étiqueté, la commande `process corpus` et le rapport de précision ≥ 80 %
- [ ] 5.8 **[5.4]** Afficher le flux de processus avec ses gates (feature, release, hotfix, recette, go/no-go)

## 6. Revue, décisions et agents

- [ ] 6.1 **[3.3]** Implémenter la sélection du relecteur (agent, modèle, famille) et l'affichage de l'indépendance
- [ ] 6.2 **[6.1]** Construire le paquet aveugle (spec, diff, preuves, ADR) et son empreinte
- [ ] 6.3 **[6.2]** Implémenter le schéma `review.schema.json`, le rapport structuré et la fiche de décision
- [ ] 6.4 **[6.3]** Implémenter la décision humaine (approuver, conditions, rejeter, info) et l'audit
- [ ] 6.5 **[1.3]** Implémenter le runner d'agents : modèles de commande, préflight, concurrence, file
- [ ] 6.6 **[6.5]** Implémenter le groupe de processus, l'annulation, le crash/timeout et la conservation des logs
- [ ] 6.7 **[6.5]** Implémenter le budget (échantillonnage, arrêt au plafond, coût réel, dépassement signalé)
- [ ] 6.8 **[6.5]** Purger l'environnement des jetons, appliquer la lecture seule et refuser Git en écriture
- [ ] 6.9 **[6.3, 6.5]** Diffuser les logs en SSE, en texte échappé, avec `aria-live` et sans déplacement du focus
- [ ] 6.10 **[6.4]** Escalade après `max_iterations` : tâche `blocked`, notification humaine, itérations conservées
- [ ] 6.11 **[6.1, 6.5]** Journal des runs (agent, rôle, modèle, statut, durée, coût, tokens) et taux d'indépendance avec seuil 10 %
- [ ] 6.12 **[6.3, 6.9]** Redaction étendue (exports, `stats_json`, journaux) et CSP vérifiée en revue

## 7. Vues restantes

- [ ] 7.1 **[4.4]** Vue Sécurité : findings, SBOM, licences, dérogations, surface agentique
- [ ] 7.2 **[4.5, 4.6]** Vue Performance & données : budgets, signaux, PII, migrations, sauvegardes
- [ ] 7.3 **[6.5]** Vue Agents IA : runs, coûts, escalades, indépendance, journal
- [ ] 7.4 **[3.3]** Vue Documentation : fraîcheur, lecteur Markdown, mention « fichier généré, ne pas modifier », régénération, suivi
- [ ] 7.5 **[1.2]** Vue Configuration : config effective, origine des données, validation
- [ ] 7.6 **[3.8]** Pagination serveur (`limit`/`offset`/`total`, 50 par défaut) et dégradation gracieuse au-delà des volumes cibles
- [ ] 7.7 **[2.8]** Vue Déploiements : dev/préprod/prod, historique, DORA, checklist go/no-go, rollback

## 8. Finition et recette

- [ ] 8.1 **[toutes]** Audit d'accessibilité RGAA 4.1 AA / WCAG 2.2 AA sur les 12 vues (clavier, contraste, équivalents textuels, `caption`, `prefers-reduced-motion`)
- [ ] 8.2 **[toutes]** Tests de performance : vue d'ensemble < 1,5 s, multi-dépôts < 2 s, listes < 500 ms, ingestion 10 k commits < 60 s, démarrage < 2 s, mémoire < 512 Mo
- [ ] 8.3 **[1.4]** Packaging `uv`/`pipx`, build frontend embarqué, commande unique `sdlc-console`
- [ ] 8.4 **[1.3]** Sauvegarde/restauration globale vérifiée, âge affiché, procédure testée
- [ ] 8.5 **[1.3, 2.3, 8.4]** Purge 12 mois (audit exclu, logs inclus), ancrage et contrôle d'intégrité
- [ ] 8.6 **[toutes]** Jeu de démonstration `--demo`, documentation, runbook, ADR, guide d'installation et solution WSL2 (mode miroir ou navigateur dans WSL)
- [ ] 8.7 **[toutes]** Recette complète, matrice de scénarios et rapport de recette
- [ ] 8.8 **[1.6]** Câbler `scripts/ci.sh` pour `apps/console` : lint, typecheck, tests, couverture ≥ 80 %, SAST, dépendances, secrets, build

### Critères d'acceptation par lot

Une tâche est acceptée lorsque les scénarios des exigences associées passent, que
`scripts/ci.sh` est vert et que la revue croisée (relecteur ≠ auteur) est faite.

| Lot | Critères d'acceptation |
|---|---|
| 1. Socle | `sdlc-console doctor` vert ; base SQLite migrée ; bind `127.0.0.2` ; Host/Origin/CSRF testés ; path traversal refusé ; CI matrice verte |
| 2. Projets et ingestion | Deux dépôts ingérés sans doublon ; identités multi-emails fusionnées ; fixtures GitHub/GitLab/CI ; déduplication vérifiée ; retrait de dépôt audité |
| 3. Features et suivi | `state.json` et `tasks.md` cohérents ; traçabilité affichée ; features/tâches listées et détaillées ; suivi généré et ouvert une seule fois ; **suivi synchronisé < 2 s, watcher et `done` ⇔ case cochée** ; Vue d'ensemble alimentée |
| 4. Gates | Chaque gate produit `reports/gates/*.json` ; un échec bloque ; `not_run` par tier ; dérogation expirée refusée ; config fingerprint |
| 5. Équipe et processus | Métriques par dépôt et agrégées ; bus factor ; profil + confiance ; flux avec gates ; corpus ≥ 80 % |
| 6. Revue et agents | Indépendance affichée ; paquet aveugle ; rapport valide ; fiche de décision ; décision auditée ; runner annulable et borné |
| 7. Vues restantes | Sécurité, performance/données, agents, docs et configuration alimentées ; **Déploiements alimentés par `deploys.jsonl`** ; pagination et dégradation gracieuse ; mention « fichier généré » |
| 8. Finition | Accessibilité AA ; cibles de performance ; packaging ; sauvegarde/restauration ; purge ; CI ; recette |
