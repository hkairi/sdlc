# Brief — Console SDLC

## 1. Problème à résoudre

Le framework SDLC produit des artefacts utiles mais dispersés : `docs/suivi/state.json`,
`openspec/changes/`, `reports/` (JUnit, Cobertura, SARIF), `docs/journal/*.jsonl`,
`docs/architecture/adr/`, `docs/recette/`, `docs/ops/runbook.md`.

Pour décider, l'orchestrateur doit aujourd'hui ouvrir une dizaine de fichiers, recouper des
formats différents et reconstruire mentalement l'état du projet. Les conséquences sont :

- les **gates** ne sont pas opposables : un chiffre peut être vert dans un fichier et rouge
  dans un autre ;
- la **revue indépendante** n'est pas traçable : on ne sait pas quel agent, quel modèle et
  quelle preuve ont conduit à une décision ;
- l'**équipe** et le **processus** ne sont pas visibles : la répartition réelle, le bus factor
  et le flux de branches restent implicites ;
- les **décisions et dérogations** ne sont pas conservées avec leur justification ;
- les **risques** (vulnérabilité, performance, perte ou fuite de données) sont découverts
  trop tard, souvent en production.

La Console SDLC est l'application web **locale** qui rassemble ces sources, calcule les gates,
prépare et suit la revue indépendante, et conserve les décisions humaines. Elle ne remplace
ni Git, ni la CI, ni OpenSpec : elle les lit et les relie.

## 2. Objectifs mesurables

| Objectif | Indicateur | Cible | Échéance |
|---|---|---|---|
| Remplacer la maquette par une application utilisable | Vues alimentées par des données réelles | 12 / 12 vues MVP | Fin du MVP |
| Rendre les gates opposables | Gates `not_run` sur un langage présent | 0 | Fin du lot L3 |
| Éclairer la décision humaine | Fiches de décision par tâche revue | 1 par revue | Fin du lot L5 |
| Donner une vue équipe fiable | Écart avec un calcul manuel de référence | ≤ 2 % | Fin du lot L4 |
| Détecter le processus | Dépôts correctement classés sur un corpus étiqueté | ≥ 80 % | Fin du lot L4 |
| Rester local et souverain | Requêtes sortantes par défaut | 0 | MVP |
| Rester utilisable | Temps de réponse de la vue d'ensemble | < 1,5 s sur 100 k commits | Fin du lot L1 |

## 3. Périmètre

### 3.1 Dans le périmètre

- Un ou plusieurs projets, chacun rattaché à **un ou plusieurs dépôts Git locaux**
  (GitHub et GitLab).
- Ingestion : Git, MR/PR, revues, approbations, artefacts CI, `state.json`, `openspec/`,
  journaux, documents.
- Les 12 vues de la maquette validée : Vue d'ensemble, Features & tâches, Gates & qualité,
  Revue indépendante, Déploiements, Équipe, Processus, Sécurité, Performance & données,
  Agents IA, Documentation, Configuration.
- Gates : tests, couverture, sécurité, performance, données, i18n, support des langages,
  revue. Preuves, dérogations, historique.
- Revue indépendante : autre agent, autre modèle, paquet aveugle, rapport, fiche de décision,
  décision humaine, audit.
- Runner d'agents : préparation, lancement depuis l'interface, suivi, annulation, budget,
  timeout, journal.
- Équipe et processus : métriques par dépôt puis agrégées, bus factor, propriété, détection
  du flux, confiance, surcharge.
- Décisions, dérogations, audit, export, sauvegarde/restauration, purge 12 mois configurable.
- Mode démonstration avec données fictives.

### 3.2 Hors périmètre

- SaaS multi-tenant, comptes publics, facturation.
- SSO, RBAC avancé, collaboration temps réel, notifications push.
- Application mobile native, extension IDE, navigation intégrée à un IDE.
- Remplacement de Git, de la CI, d'OpenSpec ou des agents.
- PostgreSQL, haute disponibilité, scalabilité horizontale (conception compatible, pas
  d'implémentation).
- Authentification en MVP : aucune ; à concevoir avant toute exposition réseau.
- Bitbucket, Azure DevOps.

## 4. Utilisateurs et parties prenantes

| Rôle | Besoin principal | Contraintes |
|---|---|---|
| Orchestrateur / tech lead | Voir l'état, décider, arbitrer gates et revues | Ne pas confondre avis d'agent et preuve |
| Développeur / exécutant | Comprendre ce qui bloque, corriger, relancer | Lecture des preuves, pas d'écriture Git depuis l'app |
| Relecteur | Recevoir un paquet clair, rendre un rapport | Lecture seule, autre modèle que l'auteur |
| QA / recette | Suivre la matrice et les scénarios | Export, historique, preuve |
| Ops | Voir les déploiements, le go/no-go, le rollback | Journal, sauvegarde, audit |
| Client / PO | Lire l'avancement et les décisions | Vue de synthèse, pas de données sensibles |
| Administrateur local | Installer, sauvegarder, restaurer, diagnostiquer | CLI, pas d'administration complexe |

## 5. Risques

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| SQLite verrouillé par une ingestion longue | Moyenne | Moyen | File d'ingestion unique, WAL, lots courts, `busy_timeout` |
| Métriques multi-dépôts erronées | Moyenne | Moyen | Identité canonique `persons`, déduplication, tests |
| Agent lancé depuis l'interface : injection, coût, Git | Moyenne | Élevé | Modèles de commande, validation, budget, timeout, lecture seule, audit |
| Absence d'authentification et DNS rebinding | Moyenne | Élevé | Écoute loopback, validation `Host`/`Origin`, refus de tout bind non loopback |
| Purge vs audit chaîné | Faible | Élevé | Audit exclu de la purge automatique, ancrage explicite |
| Faux positif de détection de processus | Élevée | Faible | Confiance, preuves, surcharge auditée |
| Prompt injection via dépôt/spec | Moyenne | Élevé | Contenu = données, aucun outil piloté par le contenu |
| Fuite de données par télémétrie | Faible | Élevé | Aucune télémétrie par défaut, revue réseau |
| Dérive de périmètre | Élevée | Moyen | MVP local, hors périmètre explicite, ADR |

## 6. Contraintes et hypothèses

### Contraintes

- Application **locale**, SQLite, aucune dépendance obligatoire à un service tiers.
- Écoute `127.0.0.2` (boucle locale), **aucune authentification** en MVP.
- Frontend **React 19 + TypeScript + Vite**.
- Backend **Python 3.12+ / FastAPI / SQLAlchemy 2 / Alembic / SQLite 3.45+**.
- Fournisseurs Git : **GitHub et GitLab**.
- **Multi-dépôts** par projet.
- Agents : préparation, suivi **et lancement depuis l'interface**, via des modèles de commande.
- Rétention **12 mois par défaut**, configurable.
- Interface en français, identifiants techniques en ASCII minuscule.

### Hypothèses

- Un utilisateur principal sur un poste de travail ; pas d'exposition réseau.
- Les dépôts sont clonés localement ; l'application ne fait pas de Git en écriture.
- Les jetons GitHub/GitLab viennent de l'environnement ou du trousseau OS, jamais de la base.
- Les agents sont lancés via des modèles configurés, jamais par une commande libre.
- Le volume cible est ≤ 5 dépôts, ≤ 100 k commits, ≤ 50 k findings, ≤ 10 k runs.
- Les artefacts CI sont disponibles dans `reports/` ou via l'API de la CI.

## 7. Références

- Cahier des charges : [`cahier-des-charges-web.md`](cahier-des-charges-web.md)
- Revue contradictoire : [`revue-cahier-des-charges-web.md`](revue-cahier-des-charges-web.md)
- Maquette validée : [`../mockup-framework.html`](../mockup-framework.html)
- Workflow : [`../conception/workflow-sdlc.md`](../conception/workflow-sdlc.md)
- Exigences NF : [`exigences-nf.md`](exigences-nf.md)

---

*Brief proposé par : orchestrateur — Date : 2026-10-20 — Validé par : l'utilisateur (responsable humain) — Date de validation : 2026-10-20.*
