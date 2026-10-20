# Analyse des menaces — Console SDLC

> Analyse STRIDE légère, alignée sur le cahier des charges et les ADR 001–006.
> Elle couvre l'application locale, son API, l'ingestion, le runner d'agents et SQLite.
> Les menaces propres aux modèles (prompt injection, détournement d'objectif) sont
> rattachées aux composants concernés.

## 1. Composants concernés

- **UI React** servie par le backend, sur `127.0.0.2`.
- **API FastAPI** locale, sans authentification, avec actions d'écriture.
- **Ingestion** : Git local, API GitHub/GitLab, artefacts CI, fichiers `reports/`.
- **Runner d'agents** : lancement de CLI, processus fils, logs, budget.
- **SQLite** : fichier local, WAL, un seul écrivain.
- **Audit** : journal chaîné, décisions et dérogations.
- **Fichiers** : `reports/`, `docs/suivi/state.json`, `openspec/`, `docs/journal/`.
- **Dépendances** : packages Python/Node, CLI d'agents, outils de sécurité.

## 2. Tableau des menaces

| Composant | Catégorie STRIDE | Menace | Risque | Mitigation | Responsable |
|---|---|---|---|---|---|
| API locale | S (Spoofing) | Un site distant vise `127.0.0.2` par DNS rebinding et POSTe une action | Élevé | Validation stricte de `Host`, refus des `Origin`/`Referer` externes, CORS désactivé | Équipe Console |
| API locale | S (Spoofing) | Tout processus local se fait passer pour l'utilisateur | Moyen | Boucle locale, acteur déclaré, audit ; token avant exposition LAN | Équipe Console |
| API locale | T (Tampering) | Modification d'une décision ou d'une dérogation | Moyen | Audit chaîné, contrôle d'intégrité, sauvegarde | Équipe Console |
| API locale | R (Repudiation) | L'acteur nie une décision (pas d'auth) | Moyen | Mention explicite « poste local non authentifié » ; token prévu | Équipe Console |
| API locale | D (Denial of service) | Boucle de requêtes ou ingestion massive | Moyen | Limite de concurrence, file, timeout, pagination | Équipe Console |
| API locale | E (Elevation of privilege) | Bind sur une IP LAN ou `0.0.0.0` | Élevé | Refus de tout bind hors `127.0.0.0/8`, message explicite, test paramétré | Équipe Console |
| UI React | I (Information disclosure) | XSS via Markdown, logs d'agent ou contenu de dépôt | Élevé | HTML brut désactivé, logs en texte échappé, CSP, tests XSS | Équipe Console |
| UI React | T (Tampering) | Injection de contenu dans un tableau ou un graphique | Moyen | Échappement, composants typés, revue | Équipe Console |
| Ingestion | T (Tampering) | Path traversal via un chemin de dépôt ou un fichier de rapport | Élevé | Chemins allowlistés, résolution réelle, refus `..` | Équipe Console |
| Ingestion | I (Information disclosure) | Lecture d'un fichier hors périmètre (secret, `.env`) | Élevé | Allowlist de chemins, refus des secrets, aucun accès hors projet | Équipe Console |
| Ingestion | I (Information disclosure) | Jeton GitHub/GitLab copié dans un log ou la base | Élevé | Jetons hors base, redaction, test au faux jeton | Équipe Console |
| Ingestion | D (Denial of service) | Quota API atteint, pagination infinie, réseau coupé | Moyen | ETag, backoff, pagination bornée, mode fichier, reprise | Équipe Console |
| Runner d'agents | E (Elevation of privilege) | Injection de commande via un paramètre ou un nom de tâche | Élevé | Modèles de commande, paramètres validés, jamais de shell libre | Équipe Console |
| Runner d'agents | I (Information disclosure) | L'agent hérite des jetons du serveur et les exfiltre | Élevé | Environnement purgé, variables minimales, pas de réseau par défaut | Équipe Console |
| Runner d'agents | T (Tampering) | L'agent écrit dans Git ou modifie des fichiers hors périmètre | Élevé | Lecture seule pour la revue, allowlist, contrôle du diff, audit | Équipe Console |
| Runner d'agents | D (Denial of service) | Coût ou durée non bornés, processus orphelins | Moyen | Budget, timeout, groupe de processus, kill-tree, limite de concurrence | Équipe Console |
| Runner d'agents | S (Spoofing) | Un relecteur du même modèle que l'auteur est présenté comme indépendant | Moyen | Vérification agent/modèle, affichage du niveau, dérogation humaine | Équipe Console |
| SQLite | T (Tampering) | Corruption ou modification directe du fichier | Moyen | WAL, contrôle d'intégrité, sauvegarde, permissions du fichier | Équipe Console |
| SQLite | I (Information disclosure) | Données en clair sur le poste | Moyen | Limite assumée ; chiffrement disque OS recommandé | Utilisateur / OS |
| Audit | T (Tampering) | Suppression ou réécriture d'événements | Moyen | Chaîne `sha256(prev_hash + payload)`, exclusion de la purge auto, ancrage explicite | Équipe Console |
| Dépendances | T (Tampering) | Package compromis ou vulnérable | Moyen | SBOM, Trivy/OSV, Renovate, versions épinglées | Équipe Console |
| Contenu externe | I (Information disclosure) | Prompt injection via spec, README ou issue | Élevé | Contenu = données, aucun outil piloté par le contenu, revue lecture seule | Équipe Console |

## 3. Hypothèses et limites

- L'application n'est **pas exposée au réseau** : elle écoute sur `127.0.0.2` et refuse tout
  bind hors boucle locale. L'absence d'authentification est acceptable dans cette limite.
- La Console ne peut pas garantir elle-même le sandbox d'un agent : la lecture seule, l'absence
  de Git en écriture et l'absence de réseau sont déléguées aux adaptateurs et vérifiées par
  configuration.
- SQLite stocke les données en clair ; le chiffrement du disque relève de l'OS.
- Les jetons GitHub/GitLab viennent de l'environnement ou du trousseau OS ; ils ne sont jamais
  stockés en base ni transmis aux agents.
- Le rapport de revue est un contenu externe : il est affiché comme données, jamais exécuté.
- L'analyse ne couvre pas les menaces propres aux modèles (biais, hallucinations) au-delà de
  la revue humaine et de l'indépendance des relecteurs.

## 4. Plan de traitement

| Menace | Action | Échéance | Statut |
|---|---|---|---|
| DNS rebinding | Validation `Host`/`Origin`, refus des POST cross-origin | Lot L0 | à faire |
| Bind hors loopback | Refus de tout bind hors `127.0.0.0/8`, test paramétré | Lot L0 | à faire |
| Injection de commande agent | Modèles de commande + validation + audit | Lot L5 | à faire |
| Jetons hérités par l'agent | Environnement purgé, variables minimales | Lot L5 | à faire |
| Écriture Git par un agent | Lecture seule, contrôle du diff, refus auditée | Lot L5 | à faire |
| Coût/durée agent | Budget, timeout, kill-tree, limite de concurrence | Lot L5 | à faire |
| Purge vs audit | Audit exclu de la purge auto, ancrage explicite | Lot L0/L7 | à faire |
| XSS logs SSE | Texte échappé, CSP, test | Lot L5 | à faire |
| Path traversal | Allowlist, résolution réelle, refus `..` | Lot L1 | à faire |
| Secrets en log | Redaction, test au faux jeton | Lot L1 | à faire |
| Corruption SQLite | WAL, intégrité, sauvegarde, restauration testée | Lot L0/L7 | à faire |
| Dépendances vulnérables | SBOM, Trivy/OSV, Renovate | Lot L0 | à faire |
| Prompt injection | Contenu = données, pas d'outil piloté | Lot L5 | à faire |

## 5. Références

- Cahier des charges §11 : [`../00-cadrage/cahier-des-charges-web.md`](../00-cadrage/cahier-des-charges-web.md)
- Revue contradictoire : [`../00-cadrage/revue-cahier-des-charges-web.md`](../00-cadrage/revue-cahier-des-charges-web.md)
- ADR-003 (local, sans auth) : [`adr/ADR-003-local-sans-auth.md`](adr/ADR-003-local-sans-auth.md)
- ADR-005 (runner) : [`adr/ADR-005-runner-agents.md`](adr/ADR-005-runner-agents.md)
- ADR-006 (rétention/audit) : [`adr/ADR-006-retention-audit.md`](adr/ADR-006-retention-audit.md)
- OWASP Top 10 Agentic 2026, OWASP AST10, NIST AI RMF.

---

*Date de l'analyse : 2026-10-20 — Rédigé par : orchestrateur — Statut : à valider.*
