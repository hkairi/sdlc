# Cahier des charges — Console SDLC (application web locale)

> **Statut : brief et exigences NF validés le 2026-10-20 — prêt pour le change OpenSpec.**
> Ce document transforme la maquette validée
> [`docs/mockup-framework.html`](../mockup-framework.html) en spécification exécutable.
> Les cibles chiffrées sont des **objectifs proposés**, pas des mesures.
>
> Références : [`docs/conception/workflow-sdlc.md`](../conception/workflow-sdlc.md),
> [`docs/conception/tasks.md`](../conception/tasks.md),
> [`templates/docs/brief.md`](../../templates/docs/brief.md),
> [`templates/docs/exigences-nf.md`](../../templates/docs/exigences-nf.md),
> [`templates/docs/menaces.md`](../../templates/docs/menaces.md).

## 1. Objet et contexte

Le framework SDLC produit aujourd'hui des artefacts dispersés : `docs/suivi/state.json`,
`openspec/changes/`, `reports/` (JUnit, Cobertura, SARIF), `docs/journal/*.jsonl`,
`docs/architecture/adr/`, `docs/recette/`, `docs/ops/runbook.md`.

La **Console SDLC** est l'application web locale qui rassemble ces sources dans un tableau
de bord unique, calcule les gates, suit l'équipe et le processus, orchestre la revue
indépendante et conserve les décisions humaines. Un projet peut regrouper **plusieurs
dépôts** GitHub ou GitLab.

Elle est **locale** : elle tourne sur le poste de l'orchestrateur, écoute sur `127.0.0.2`
(boucle locale), stocke ses données dans **SQLite**, ne dépend d'aucun service tiers et
n'envoie aucune donnée à l'extérieur par défaut. Elle n'exige **aucune authentification**
dans cette version. Elle ne remplace ni Git, ni la CI, ni OpenSpec : elle les **lit** et
les **relie**.

## 2. Objectifs et critères de succès

| Objectif | Indicateur | Cible proposée |
|---|---|---|
| Remplacer la maquette par une application utilisable | 12 vues alimentées par des données réelles | 100 % des vues MVP |
| Rendre les gates opposables | verdict calculé depuis des preuves, pas depuis un avis | 0 gate `not_run` sur un langage présent |
| Éclairer la décision humaine | fiche de décision par revue | 1 fiche par tâche revue |
| Donner une vue équipe fiable | métriques reproductibles depuis Git/MR | écart ≤ 2 % avec un calcul manuel |
| Détecter le processus | profil + confiance + preuve | ≥ 80 % des dépôts de test correctement classés |
| Rester local et souverain | aucune requête sortante par défaut | 0 appel réseau hors ingestion explicitement configurée |
| Rester utilisable | temps de réponse | vue d'ensemble < 1,5 s sur 100 k commits |

## 3. Périmètre

### 3.1 Dans le périmètre (MVP local)

- Gestion de **un ou plusieurs projets**, chacun rattaché à **un ou plusieurs dépôts Git
  locaux** (multi-dépôts).
- **Ingestion** : Git, merge requests **GitHub et GitLab**, artefacts CI (JUnit, Cobertura,
  SARIF), `docs/suivi/state.json`, `openspec/`, journaux `runs.jsonl` / `deploys.jsonl`,
  documents.
- Les **12 vues** de la maquette : Vue d'ensemble, Features & tâches, Gates & qualité,
  Revue indépendante, Déploiements, Équipe, Processus, Sécurité, Performance & données,
  Agents IA, Documentation, Configuration.
- **Gates** : tests, couverture, sécurité, performance, données, i18n, support des langages,
  revue. Calcul, preuve, dérogation, historique.
- **Revue indépendante** : sélection d'un agent et d'un modèle différents, paquet aveugle,
  rapport structuré, fiche de décision, décision humaine, audit.
- **Exécution d'agents depuis l'interface** : préparation, lancement, suivi, annulation,
  budget et journal, via des modèles de commande configurés.
- **Multi-dépôts** : ajout/retrait de dépôts, dépôt principal, filtre par dépôt ou « tous »,
  agrégation des métriques sans double comptage.
- **Équipe** : commits, MR, revues, approbations, bus factor, propriété, activité.
- **Processus** : détection (GitHub Flow, Git Flow, trunk-based, GitLab Flow), confiance,
  preuves, surcharge manuelle, par dépôt puis agrégation projet.
- **Décisions et dérogations** : enregistrement, expiration, justification, audit.
- **Export** JSON/CSV et **sauvegarde/restauration** SQLite.
- **Mode démonstration** avec données fictives, pour la recette et les démos.

### 3.2 Hors périmètre (pour cette version)

- SaaS multi-tenant, comptes publics, facturation.
- SSO, RBAC avancé, collaboration temps réel, notifications push.
- Application mobile native, IDE intégré, extension navigateur.
- Remplacement de la CI, de Git, d'OpenSpec ou des agents.
- Exécution d'agents hors des adaptateurs configurés, ou sur des dépôts non déclarés.
- Base PostgreSQL, haute disponibilité, scalabilité horizontale. **Conception compatible**,
  implémentation hors périmètre.
- Ingestion de dépôts distants sans clone local (miroir Git accepté en entrée).
- Authentification, SSO, RBAC : aucune en MVP ; à concevoir avant toute exposition réseau.

### 3.3 Hypothèses

- Un utilisateur principal (orchestrateur) sur un poste de travail ; l'application écoute
  sur `127.0.0.2` et n'est **pas exposée au réseau**.
- Les dépôts (un ou plusieurs par projet) sont clonés localement ; l'application lit les
  dossiers, elle ne fait pas de Git en écriture.
- Les jetons GitHub/GitLab sont fournis par variable d'environnement ou trousseau OS,
  jamais stockés en base.
- Les agents sont lancés via des **modèles de commande configurés**, jamais par une commande
  libre saisie dans l'interface.
- Les artefacts CI sont disponibles dans `reports/` ou récupérés par l'API de la CI.
- Le volume cible est celui d'un projet de taille moyenne : ≤ 5 dépôts, ≤ 100 k commits,
  ≤ 50 k findings, ≤ 10 k runs d'agents.
- L'interface est en français ; les identifiants techniques restent en ASCII minuscule.

### 3.4 Statut du document et change OpenSpec

Le présent cahier des charges est un document de **cadrage**. Il alimente un change OpenSpec
`console-sdlc` (`proposal.md`, `design.md`, deltas de spec, `tasks.md`) qui sera soumis au
gate `spec_freeze`. Le cahier des charges n'est **pas** lui-même le change gelé ; toute
modification après gel passe par `change-request`.

## 4. Utilisateurs et rôles

| Rôle | Besoin principal | Contraintes |
|---|---|---|
| Orchestrateur / tech lead | Voir l'état, décider, arbitrer les gates et les revues | Ne doit jamais confondre un avis d'agent avec une preuve |
| Développeur / exécutant | Comprendre ce qui bloque, corriger, relancer | Lecture des preuves, pas d'écriture Git depuis l'app |
| Relecteur | Recevoir un paquet de revue clair, rendre un rapport | Lecture seule, autre modèle que l'auteur |
| QA / recette | Suivre la matrice et les scénarios | Export, historique, preuve |
| Ops | Voir les déploiements, le go/no-go, le rollback | Journal, sauvegarde, audit |
| Client / PO | Lire l'avancement et les décisions | Vue de synthèse, pas de données sensibles |
| Administrateur local | Installer, sauvegarder, restaurer, diagnostiquer | CLI, pas d'interface d'administration complexe |

## 5. Architecture fonctionnelle

```
┌──────────────────────────────────────────────────────────────┐
│  Console SDLC (localhost)                                    │
│                                                              │
│  Interface web (12 vues)                                     │
│        │ REST/JSON + SSE                                     │
│  API FastAPI ── Moteur de gates ── Moteur de revue           │
│        │              │                   │                  │
│  SQLite (WAL) ── Ingestion ── Collecteurs                    │
│        │              │                   │                  │
│  Sauvegarde      Git / MR API / CI     Agents CLI            │
└──────────────────────────────────────────────────────────────┘
         │                    │                    │
   docs/suivi/state.json  reports/*.xml|sarif  runs.jsonl
```

Principes :

1. **Le dépôt reste la source de vérité.** SQLite est un index de lecture, pas un substitut
   aux fichiers versionnés.
2. **Le CLI applique, l'interface montre.** Tout ce qui est obligatoire est vérifiable par
   `sdlc check` ; l'interface ne crée pas de règle propre.
3. **Preuve avant verdict.** Un gate ne peut pas être vert sans artefact lié.
4. **Aucun verrou d'outil.** Git, GitHub, GitLab, la CI et les agents sont des adaptateurs.
5. **Local d'abord.** Aucune donnée ne quitte le poste sans action explicite.

## 6. Exigences fonctionnelles

Priorités : **MUST** = MVP, **SHOULD** = v1, **COULD** = ultérieur.

### 6.1 Socle, projets et ingestion

| ID | Exigence | Priorité | Critère d'acceptation |
|---|---|---|---|
| REQ-SOC-01 | Créer un projet avec nom, un ou plusieurs dépôts locaux, branche par défaut et fuseau horaire | MUST | Le projet apparaît dans la barre latérale et la vue d'ensemble |
| REQ-SOC-02 | Valider que chaque chemin de dépôt existe et est un dépôt Git | MUST | Un chemin invalide est refusé avec un message explicite |
| REQ-SOC-03 | Ingérer les commits de chaque dépôt (sha, auteur, date, ajouts/suppressions, fichiers, merge, bot, trailer IA) | MUST | Le nombre de commits ingérés est affiché et rejouable |
| REQ-SOC-04 | Ingérer les MR GitHub et GitLab de chaque dépôt (auteur, état, dates, cible, stratégie de merge) | MUST | Les MR apparaissent dans Équipe et Processus |
| REQ-SOC-05 | Ingérer les revues et approbations (humain/agent, modèle, date) | SHOULD | La chaîne de validation est calculée |
| REQ-SOC-06 | Ingérer JUnit, Cobertura/lcov/JaCoCo, SARIF | MUST | Les gates tests/couverture/sécurité affichent les chiffres |
| REQ-SOC-07 | Ingérer `docs/suivi/state.json` et `openspec/changes/*/tasks.md` | MUST | Features et tâches correspondent aux fichiers |
| REQ-SOC-08 | Ingérer `runs.jsonl` et `deploys.jsonl` | SHOULD | Agents et Déploiements sont alimentés |
| REQ-SOC-09 | Ingestion incrémentale idempotente, par dépôt et par source | MUST | Deux passages ne créent pas de doublons |
| REQ-SOC-10 | Afficher la fraîcheur (dernière ingestion, source, dépôt, statut, erreur) | MUST | Un badge « à jour / en retard / échec » est visible par source |
| REQ-SOC-11 | Mode démonstration avec jeu de données fictif multi-dépôts | SHOULD | `--demo` remplit la base sans dépôt réel |
| REQ-SOC-12 | Gérer plusieurs dépôts par projet : ajout, retrait, dépôt principal, branche par défaut | MUST | Un projet peut contenir 2 dépôts et les vues les distinguent |
| REQ-SOC-13 | Filtrer toutes les vues par dépôt ou par « tous les dépôts » | MUST | Le filtre est conservé dans l'URL |
| REQ-SOC-14 | Agréger les métriques multi-dépôts sans double comptage | MUST | Un commit n'est compté qu'une fois par dépôt |
| REQ-SOC-15 | Canonicaliser l'identité des contributeurs : une personne, plusieurs emails et comptes GitHub/GitLab | MUST | Un contributeur avec 2 emails et 2 comptes est compté une fois |
| REQ-SOC-16 | Dédupliquer les contributions entre dépôts miroirs/forks déclarés | MUST | Un commit présent dans 2 dépôts est compté une fois dans « tous » |
| REQ-SOC-17 | Gérer les échecs d'ingestion : jeton expiré, quota, réseau coupé, reprise | MUST | Un échec partiel laisse un badge « échec » par source et ne marque rien « à jour » |
| REQ-SOC-18 | Ingérer `docs/incidents/*.md` et `docs/metrics/history.jsonl` | SHOULD | Le MTTR et les métriques disposent d'une source nommée |
| REQ-SOC-19 | Vérifier et migrer le schéma au démarrage ; refuser un schéma plus récent | MUST | Une migration est proposée, une version inconnue est refusée |
| REQ-SOC-20 | Vérifier les jetons et quotas GitHub/GitLab dans `doctor --with-tokens` | SHOULD | Un jeton invalide ou un quota épuisé est signalé avant le premier run |
| REQ-SOC-21 | Fournir des fixtures GitHub/GitLab/CI pour tester l'ingestion hors réseau | MUST | Les tests d'ingestion passent sans réseau |

### 6.2 Vue d'ensemble

| ID | Exigence | Priorité | Critère d'acceptation |
|---|---|---|---|
| REQ-OV-01 | Afficher les KPI : avancement, gates, couverture, vulnérabilités, coût IA, délai spec→prod | MUST | Chaque KPI indique sa source et « non mesuré » si absente |
| REQ-OV-02 | Afficher les décisions en attente, triées par blocage | MUST | Chaque item ouvre sa preuve ou sa fiche |
| REQ-OV-03 | Afficher le pipeline SDLC avec l'état de chaque étape | MUST | Les étapes viennent de `state.json` et des gates |
| REQ-OV-04 | Afficher les risques ouverts par catégorie | MUST | Au moins données, sécurité, performance, tests |
| REQ-OV-05 | Afficher l'activité récente | SHOULD | Commit, MR, revue, déploiement, gate |
| REQ-OV-06 | Résumer l'équipe et le processus avec lien vers les vues | SHOULD | Le résumé est cohérent avec les vues détaillées |
| REQ-OV-07 | Ouvrir automatiquement le fichier de suivi dès qu'il est prêt | MUST | La vue Suivi s'ouvre une seule fois, sans bloquer l'interface ; un lien persistant reste disponible |
| REQ-OV-08 | Mettre à jour le fichier de suivi de façon synchrone à chaque changement de statut de tâche | MUST | `tasks.md`, `state.json` et le HTML sont cohérents en moins de 2 s ; `done` ⇔ case cochée |

### 6.3 Features et tâches

| ID | Exigence | Priorité | Critère d'acceptation |
|---|---|---|---|
| REQ-FEA-01 | Lister les features avec phase, tâches, couverture, gate, exécutant, relecteur | MUST | Filtres par phase et par gate |
| REQ-FEA-02 | Afficher les tâches en cours avec fichiers, critères, statut | MUST | Une tâche terminée renvoie à son rapport |
| REQ-FEA-03 | Matrice de traçabilité exigence → scénario → test → tâche | SHOULD | Une exigence sans test est signalée |
| REQ-FEA-04 | Ouvrir le détail d'une feature (spec, design, tâches, revue) | SHOULD | Lecture Markdown rendue, HTML brut désactivé |
| REQ-FEA-05 | Signaler les incohérences `tasks.md` ↔ `state.json` | MUST | Une case non synchronisée est listée |

### 6.4 Gates et qualité

| ID | Exigence | Priorité | Critère d'acceptation |
|---|---|---|---|
| REQ-GAT-01 | Calculer un verdict par gate : pass, warn, fail, waived, not_applicable | MUST | Le verdict est dérivé des preuves, jamais saisi |
| REQ-GAT-02 | Tests : échec, test ignoré sur le code modifié, test instable | MUST | Un échec bloque ; un instable est signalé avec ticket |
| REQ-GAT-03 | Couverture : global, lignes modifiées, fichier | MUST | Trois seuils distincts et affichés |
| REQ-GAT-04 | Sécurité : critique/haute atteignable, secret, image, IaC | MUST | Une haute atteignable bloque |
| REQ-GAT-05 | Performance : budget observé et signaux statiques | MUST | Une régression observée bloque ; un signal statique alerte |
| REQ-GAT-06 | Données : migration destructive, PII, sauvegarde non testée | MUST | Une migration destructive bloque sans dérogation |
| REQ-GAT-07 | i18n : clés manquantes, clés orphelines, chaînes en dur | SHOULD | Le taux de parité par locale est affiché |
| REQ-GAT-08 | Support des langages : détection, adaptateur, tier | MUST | Un langage détecté sans adaptateur fait échouer le gate |
| REQ-GAT-09 | Dérogation datée, motivée, avec expiration et approbateur | MUST | Une dérogation expirée repasse le gate en échec |
| REQ-GAT-10 | Historique des runs de gate avec diff | SHOULD | On peut comparer deux runs |
| REQ-GAT-11 | Lien vers l'artefact de preuve (JUnit, Cobertura, SARIF, JSON) | MUST | Chaque finding a un fichier et une ligne si applicable |
| REQ-GAT-12 | Définir et lire une preuve de performance observée | MUST | Un JSON `reports/perf/*.json` contient fenêtre, cas, p95/p99, budget |
| REQ-GAT-13 | Une seule source de vérité pour les seuils : `sdlc.config.yaml` | MUST | La base ne fait que cacher la config avec une empreinte de version |
| REQ-GAT-14 | Appliquer `not_run` par contrôle attendu du tier du langage | MUST | SQL/shell tier 2 sans couverture ne fait pas échouer le gate couverture |

### 6.5 Revue indépendante

| ID | Exigence | Priorité | Critère d'acceptation |
|---|---|---|---|
| REQ-REV-01 | Sélectionner le relecteur éligible au niveau d'indépendance maximal disponible | MUST | Le niveau est affiché : complète, partielle, dégradée |
| REQ-REV-02 | Construire un paquet aveugle : spec, diff, preuves, ADR ; sans le récit de l'auteur | MUST | Le paquet est téléchargeable et traçable |
| REQ-REV-03 | Rapport structuré : verdict, findings, sévérité, confiance, preuve, correctif | MUST | Le JSON valide le schéma `review.schema.json` |
| REQ-REV-04 | Fiche de décision : 3 bloquants max, risques, non-vérifié, options, recommandation | MUST | La fiche tient sur une page lisible |
| REQ-REV-05 | Décision humaine : approuver, approuver avec conditions, rejeter, demander une info | MUST | La décision est enregistrée avec acteur, date, motif |
| REQ-REV-06 | Escalade après `max_iterations` | MUST | La tâche passe en `blocked` et l'humain est notifié |
| REQ-REV-07 | Enregistrer auteur, relecteur, modèles, durée, coût, indépendance | MUST | Visible dans Agents IA et dans l'audit |
| REQ-REV-08 | Relecture en lecture seule, sans commande Git en écriture | MUST | Le rapport ne peut pas modifier le dépôt |
| REQ-REV-09 | Lancer la revue depuis l'interface, après confirmation, budget et choix du relecteur | MUST | Le lancement est tracé avec l'agent, le modèle et le budget |
| REQ-REV-10 | Suivre l'avancement, afficher les logs et permettre l'annulation d'une revue en cours | SHOULD | L'état passe de `queued` à `running`, `done` ou `cancelled` |
| REQ-REV-11 | Refuser un relecteur du même modèle que l'auteur, sauf dérogation humaine explicite et journalisée | MUST | L'interface explique le blocage et propose un autre modèle ; la dérogation est auditée |

### 6.6 Déploiements

| ID | Exigence | Priorité | Critère d'acceptation |
|---|---|---|---|
| REQ-DEP-01 | Afficher dev, préprod, prod : version, date, statut | MUST | La source est `deploys.jsonl` ou l'API CI |
| REQ-DEP-02 | Calculer les métriques DORA : lead time, fréquence, CFR, MTTR | SHOULD | Chaque métrique indique sa fenêtre et sa source |
| REQ-DEP-03 | Afficher l'historique avec succès, rollback, échec | MUST | Un rollback est visible et daté |
| REQ-DEP-04 | Checklist go/no-go avec preuves | MUST | Chaque case renvoie à un artefact |
| REQ-DEP-05 | Afficher la procédure de rollback | SHOULD | Lien vers `docs/ops/deploy-*.md` |

### 6.7 Équipe

| ID | Exigence | Priorité | Critère d'acceptation |
|---|---|---|---|
| REQ-EQ-01 | Lister les contributeurs : commits, MR, revues, approbations, lignes, dernière activité | MUST | Bots exclus par défaut, option pour les inclure |
| REQ-EQ-02 | Calculer la part des commits et la charge de revue | MUST | Les formules sont documentées et testées |
| REQ-EQ-03 | Calculer le bus factor par zone | MUST | Une zone à 1 est signalée comme risque |
| REQ-EQ-04 | Afficher la propriété par zone (CODEOWNERS + historique) | SHOULD | Principal, secondaire, bus factor |
| REQ-EQ-05 | Afficher la chaîne de validation auteur → relecteur agent → humain | SHOULD | Taux de revues agent et d'approbations humaines |
| REQ-EQ-06 | Afficher l'activité 12 semaines | SHOULD | Carte lisible, équivalent textuel |
| REQ-EQ-07 | Afficher la part assistée par IA, avec « non mesuré » si trailer absent | MUST | Aucune estimation inventée |
| REQ-EQ-08 | Exporter la vue en CSV/JSON | COULD | Export reproductible |

### 6.8 Processus

| ID | Exigence | Priorité | Critère d'acceptation |
|---|---|---|---|
| REQ-PRO-01 | Détecter GitHub Flow, Git Flow, trunk-based, GitLab Flow | SHOULD | Profil, confiance, preuves affichés |
| REQ-PRO-02 | Lister les signaux : branches, merges, tags, protection, CI, CODEOWNERS | MUST | Chaque signal a une valeur observée et une interprétation |
| REQ-PRO-03 | Afficher le flux avec les gates | MUST | Feature, release, hotfix, gates |
| REQ-PRO-04 | Lister les branches actives : type, âge, avance/retard, propriétaire | SHOULD | Les branches fusionnées sont exclues |
| REQ-PRO-05 | Calculer lead time, cycle time, taille de MR, taux de hotfix | SHOULD | Fenêtre et source affichées |
| REQ-PRO-06 | Permettre une surcharge manuelle du profil | MUST | La surcharge est datée, motivée et auditée |
| REQ-PRO-07 | Afficher « non identifiable » avec les raisons | MUST | Aucun profil inventé |

### 6.9 Sécurité

| ID | Exigence | Priorité | Critère d'acceptation |
|---|---|---|---|
| REQ-SEC-01 | Lister les findings par sévérité, atteignabilité, composant, correctif, SLA | MUST | Une haute atteignable est bloquante |
| REQ-SEC-02 | Afficher le SBOM et les licences à risque | SHOULD | Format CycloneDX/SPDX |
| REQ-SEC-03 | Gérer les dérogations avec expiration | MUST | Une dérogation expirée est refusée |
| REQ-SEC-04 | Afficher la surface agentique (OWASP ASI/AST10) | SHOULD | Contrôles et statut par risque |
| REQ-SEC-05 | Ne jamais afficher un secret ; masquer les valeurs sensibles | MUST | Test avec faux jeton dans un log |

### 6.10 Performance et données

| ID | Exigence | Priorité | Critère d'acceptation |
|---|---|---|---|
| REQ-PER-01 | Afficher les budgets : p95, p99, bundle, requêtes, mémoire | MUST | Actuel, budget, tendance, état |
| REQ-PER-02 | Afficher les signaux statiques : N+1, requête non bornée, I/O sync, regex, image | SHOULD | Confiance et emplacement |
| REQ-PER-03 | Afficher les risques données : migration, PII, rétention, chiffrement, sauvegarde | MUST | Chaque risque a une preuve |
| REQ-PER-04 | Tester la restauration de sauvegarde et afficher la date | MUST | Une sauvegarde non testée est signalée |
| REQ-PER-05 | Alerter sur une régression par rapport à une baseline | SHOULD | Seuil de régression configurable |

### 6.11 Agents IA

| ID | Exigence | Priorité | Critère d'acceptation |
|---|---|---|---|
| REQ-AGT-01 | Lister les runs : agent, rôle, modèle, tâche, statut, durée, coût, tokens | MUST | Source `runs.jsonl` ou API |
| REQ-AGT-02 | Calculer le taux de réussite, les escalades, le coût par feature | SHOULD | Formules documentées |
| REQ-AGT-03 | Afficher l'indépendance des revues (agent, modèle, famille) | MUST | Le taux est affiché ; au-delà d'un seuil configuré (défaut 10 %), la décision humaine est exigée |
| REQ-AGT-04 | Afficher le journal des runs filtrable | SHOULD | Filtres agent, rôle, statut, période, dépôt |
| REQ-AGT-05 | Ne jamais exposer un prompt ou un secret dans le journal | MUST | Redaction et test |
| REQ-AGT-06 | Lancer un exécutant ou un relecteur depuis l'interface, via un modèle de commande configuré | MUST | La commande exacte, le dépôt, la durée max et le budget sont affichés avant confirmation |
| REQ-AGT-07 | Suivre l'état, diffuser les logs, limiter durée et coût, permettre l'annulation | MUST | Un run peut être annulé et son coût est plafonné |
| REQ-AGT-08 | Refuser toute commande libre, tout dépôt hors périmètre et toute écriture Git | MUST | Une tentative est bloquée et auditée |
| REQ-AGT-09 | Appliquer une limite de concurrence par agent et par projet | SHOULD | Un troisième run simultané est mis en file |
| REQ-AGT-10 | Vérifier avant lancement la CLI, le modèle, le dépôt, le budget et la durée | MUST | Un préflight bloquant affiche la cause avant confirmation |
| REQ-AGT-11 | Purger l'environnement du run des jetons et secrets du serveur | MUST | Un test vérifie qu'aucun jeton n'est hérité |
| REQ-AGT-12 | Lancer le run dans un groupe de processus et annuler tout l'arbre | MUST | Aucun processus fils ne survit à l'annulation |
| REQ-AGT-13 | Estimer le coût cumulé, arrêter au plafond et afficher le coût réel | MUST | Le dépassement éventuel est signalé, jamais masqué |
| REQ-AGT-14 | Afficher les logs en texte échappé, jamais en HTML interprété | MUST | Test XSS sur un log d'agent |

### 6.12 Documentation

| ID | Exigence | Priorité | Critère d'acceptation |
|---|---|---|---|
| REQ-DOC-01 | Lister les documents attendus et leur fraîcheur | MUST | Brief, exigences, ADR, specs, recette, runbook, incidents, release notes |
| REQ-DOC-02 | Lecteur Markdown avec HTML brut désactivé | MUST | Test XSS |
| REQ-DOC-03 | Signaler un document manquant ou périmé | SHOULD | Échéance configurable |
| REQ-DOC-04 | Marquer les documents générés « ne pas modifier » | MUST | Mention visible |

### 6.13 Configuration

| ID | Exigence | Priorité | Critère d'acceptation |
|---|---|---|---|
| REQ-CFG-01 | Afficher la configuration effective du projet | MUST | Lecture seule, source `sdlc.config.yaml` |
| REQ-CFG-02 | Indiquer l'origine de chaque donnée : déclarée, détectée, mesurée | MUST | Tableau de traçabilité |
| REQ-CFG-03 | Valider la configuration contre un JSON Schema | MUST | Erreur explicite, pas de démarrage silencieux |
| REQ-CFG-04 | Exporter la configuration | COULD | JSON/YAML |

### 6.14 Recherche, export, audit

| ID | Exigence | Priorité | Critère d'acceptation |
|---|---|---|---|
| REQ-GEN-01 | Recherche globale (feature, tâche, finding, commit, document) | SHOULD | Résultats classés, lien direct |
| REQ-GEN-02 | Filtres persistants dans l'URL | SHOULD | Partage d'un lien |
| REQ-GEN-03 | Export JSON/CSV des tableaux | COULD | Colonnes documentées |
| REQ-GEN-04 | Journal d'audit inviolable (chaîne de hachage) | MUST | Toute décision et dérogation est traçable |
| REQ-GEN-05 | Pagination serveur sur les grandes listes | MUST | 50 lignes par défaut |
| REQ-GEN-06 | Purge confirmée, précédée d'une sauvegarde vérifiée, journalisée | MUST | Une purge sans sauvegarde récente est refusée |
| REQ-GEN-07 | Afficher l'âge de la dernière sauvegarde et de la dernière ingestion | MUST | Un dépassement de cadence est signalé |
| REQ-GEN-08 | Exposer les actions MUST dans l'API ou déclarer explicitement « CLI uniquement » | MUST | Dérogation, purge, export et dépôt principal ont un chemin UI ou CLI documenté |
| REQ-GEN-09 | Ancrer la chaîne d'audit avant toute purge d'audit explicite | MUST | Un événement d'ancrage clôt la génération et une nouvelle chaîne démarre |

### 6.15 Précisions issues de la revue itération 2

Ces exigences complètent les domaines précédents ; elles sont normatives et testables.

| ID | Exigence | Priorité | Critère d'acceptation |
|---|---|---|---|
| REQ-PRE-01 | Apparier les identités d'une même personne : email exact, puis compte fournisseur ; conflit de nom → revue manuelle, jamais d'appariement silencieux | MUST | Un contributeur avec 2 emails et 2 comptes est une seule personne ; un conflit est signalé |
| REQ-PRE-02 | Marquer les bots fournisseur (`dependabot[bot]`, `github-actions[bot]`, etc.) et ne jamais les compter dans l'équipe | MUST | Les bots sont exclus des métriques et listés à part |
| REQ-PRE-03 | Interdire la suppression d'une personne référencée ; une fusion utilise `superseded_by_person_id` et est auditée | MUST | Une fusion est réversible et traçable |
| REQ-PRE-04 | Calculer `commit_fingerprint` de façon normative (voir §7.2) | MUST | Deux implémentations produisent la même empreinte |
| REQ-PRE-05 | Afficher un badge « dédoublonnage appliqué » et le dépôt d'origine pour un commit dédupliqué | SHOULD | Un cherry-pick ou un fork non déclaré est signalé |
| REQ-PRE-06 | Exécuter la purge dans la même file que l'ingestion ; si une ingestion est en cours, attendre ou refuser avec `purge_busy` | MUST | Une purge pendant une ingestion ne corrompt rien |
| REQ-PRE-07 | Étendre la purge aux fichiers de logs et rapports datés au-delà de la rétention | MUST | Aucun log de plus de 12 mois ne subsiste |
| REQ-PRE-08 | Énumérer les statuts de `task_runs` : `queued`, `running`, `done`, `failed`, `timeout`, `cancelled` | MUST | Les filtres et métriques n'acceptent que ces valeurs |
| REQ-PRE-09 | Permettre l'annulation d'un run `queued` sans l'exécuter | MUST | Le run passe à `cancelled` sans processus lancé |
| REQ-PRE-10 | Archiver un dépôt retiré (`retired_at`) par défaut ; la suppression définitive est explicite et cascadée | MUST | Un dépôt retiré n'apparaît plus dans les agrégats, son historique est conservé ou supprimé selon le choix |
| REQ-PRE-11 | Réélire le dépôt principal ou refuser le retrait du dépôt principal | MUST | Le projet garde toujours un dépôt principal |
| REQ-PRE-12 | Calculer le gate d'une feature comme la conjonction des gates de ses dépôts | MUST | Une feature n'est verte que si tous ses dépôts sont verts |
| REQ-PRE-13 | Stocker `config_fingerprint` dans `gates` ; tout changement de config marque les gates « recalcul requis » | MUST | Un changement de seuil invalide le cache |
| REQ-PRE-14 | La sauvegarde est **globale** (fichier SQLite complet) ; `backup_runs.project_id` est un simple filtre d'affichage | MUST | Une restauration ramène tous les projets |
| REQ-PRE-15 | Refuser une purge si la sauvegarde vérifiée a plus de 24 h (seuil configurable) | MUST | Erreur `backup_too_old` documentée |
| REQ-PRE-16 | Fournir un jeton CSRF via `GET /api/csrf`, exigé dans l'en-tête `X-SDLC-CSRF` pour les écritures | MUST | Une écriture sans jeton reçoit 403 |
| REQ-PRE-17 | Échantillonner la consommation d'un agent à cadence configurable et arrêter au plafond estimé | MUST | Un dépassement d'estimation est signalé, jamais masqué |
| REQ-PRE-18 | Contrôler l'intégrité de la chaîne d'audit au démarrage et après purge ; un échec bloque et alerte | MUST | Une chaîne altérée empêche le démarrage |
| REQ-PRE-19 | Étendre la redaction aux exports JSON/CSV, `stats_json` et journaux de runs | MUST | Un faux jeton n'apparaît dans aucun export |
| REQ-PRE-20 | Respecter proactivement le quota GitHub/GitLab : ETag, backoff, cache, pagination, mode fichier | SHOULD | Un test sans réseau et un test de quota passent |
| REQ-PRE-21 | Documenter et tester l'accès WSL2 : `127.0.0.2` n'est pas garanti depuis l'hôte Windows en NAT | MUST | Le guide d'installation donne la solution (mode miroir ou navigateur dans WSL) |
| REQ-PRE-22 | Fournir `sdlc-console process corpus <chemin>` et un rapport de précision | SHOULD | Le rapport contient le taux et la liste des échecs de classification |

## 7. Règles de calcul

Les formules sont **normatives** : elles doivent être implémentées à l'identique et testées.

| Indicateur | Définition |
|---|---|
| **Bus factor d'une zone** | Trier les **personnes canoniques** par commits sur 90 jours ; cumuler jusqu'à ≥ 50 % ; le nombre de personnes nécessaires est le bus factor. 1 si la première atteint 50 %. |
| **Part des commits** | Commits d'une personne / commits totaux de la fenêtre, merge commits et bots exclus, doublons de dépôts miroirs dédupliqués. |
| **Charge de revue** | Nombre de revues soumises par personne sur la fenêtre. |
| **Revue médiane** | Médiane de `première revue - MR prête` ; si la date de disponibilité manque, `première revue - création MR` avec mention. |
| **Lead time** | `déploiement prod - gel de spec` ; « non mesuré » si l'une des dates manque. |
| **Cycle time** | `merge - création MR`. |
| **Change failure rate** | Déploiements prod en rollback ou échec / déploiements prod totaux. |
| **MTTR** | Durée entre incident et retour à la normale, depuis `deploys.jsonl` et `docs/incidents/*.md`. |
| **Part assistée IA** | Commits avec trailer `Assisted-by:` ou `Co-authored-by:` d'un agent / commits totaux ; « non mesuré » si aucun trailer. |
| **Confiance processus** | Score heuristique 0–1 pondérant les signaux observés. Ce n'est **pas** une probabilité statistique ; l'interface l'indique. |
| **Verdict de gate** | `fail` si un contrôle **attendu pour le tier du langage** échoue ; `warn` si seul un avertissement ; `waived` si dérogation valide ; `not_applicable` si le contrôle est hors périmètre du tier ; `not_run` sur un contrôle attendu = `fail`. |
| **Tiers de support** | Tier 1 : tests, couverture, SCA/SAST, performance, données. Tier 2 : tests + SCA, sans couverture. Tier 3 : non supporté ; langage détecté sans adaptateur = `fail`. |
| **Indépendance de revue** | `complète` si agent ≠, modèle ≠ et famille ≠ ; `partielle` si agent ≠ et modèle ≠ ; `dégradée` sinon. Une revue dégradée exige une dérogation humaine explicite et auditée. |
| **Périmètre multi-dépôts** | Un projet regroupe N dépôts. Les métriques sont calculées **par dépôt**, puis agrégées. Le filtre « dépôt » restreint le calcul ; « tous » agrège en dédupliquant les commits par empreinte (`sha + auteur + date`) et par `dedup_group` pour les miroirs/forks déclarés. Une **personne canonique** regroupe plusieurs emails et identités fournisseur. |
| **Processus multi-dépôts** | Un profil par dépôt. La vue projet affiche le profil dominant et signale les divergences ; aucune moyenne pondérée n'est inventée. |
| **Rétention** | 12 mois par défaut pour commits, MR, runs, findings, déploiements et documents ; configurable par projet et par table. **L'audit est exclu de la purge automatique** ; sa purge est explicite, précédée d'un ancrage et d'une sauvegarde vérifiée. |
| **Budget agent** | Plafond en euros et en tokens, arrêt sur estimation cumulée ; coût réel affiché à la fin, dépassement éventuel signalé. |
| **Preuve de performance** | JSON `reports/perf/*.json` : fenêtre, cas, p50/p95/p99, budget, commit, outil. Sans ce fichier, le gate performance est `not_run` (donc `fail` si attendu). |

### 7.2 Définitions normatives issues de la revue 2

- **Identité d'une personne.** L'appariement se fait d'abord par **email exact** (normalisé en
  minuscules), puis par **compte fournisseur** (`provider` + `external_id`). Un conflit de nom
  n'entraîne **jamais** un appariement automatique : il produit un constat de revue manuelle.
  Une personne référencée ne peut pas être supprimée ; une fusion renseigne
  `superseded_by_person_id` et écrit un événement d'audit. Les comptes bots sont identifiés par
  leur motif fournisseur (`[bot]`, `bot@`, `github-actions`, `dependabot`) et exclus des
  métriques d'équipe.
- **Empreinte de commit.** `commit_fingerprint = sha256(sha + "\n" + email_auteur_normalisé +
  "\n" + author_date_utc_iso8601)`. L'email est celui de l'auteur du commit, pas l'identifiant
  de la personne (stable même après fusion) ; la date est la date d'auteur, pas la date de
  commit. La même formule est utilisée dans l'ADR-004.
- **Statuts de run.** `queued` → `running` → `done` | `failed` | `timeout` ; `queued` →
  `cancelled` ; `running` → `cancelled`. Aucun autre statut n'est accepté.
- **Chaîne d'audit.** Une chaîne **par projet** : `prev_hash` et `generation` sont adossés au
  couple `(project_id, generation)`. Un contrôle d'intégrité est exécuté au démarrage, après
  toute purge d'audit et à la demande (`doctor`).
- **Budget agent.** L'adaptateur expose la consommation à chaque appel ou périodiquement ;
  la Console échantillonne à cadence configurable (défaut 5 s), estime le cumul et arrête le
  groupe de processus au plafond. Le coût réel est affiché à la fin ; un dépassement est
  signalé, jamais masqué.
- **Sauvegarde récente.** Une sauvegarde est « récente » si elle a moins de **24 h** par
  défaut (seuil configurable). Une purge sans sauvegarde récente échoue avec
  `backup_too_old`.
- **Purge et ingestion.** La purge s'exécute dans la même file que l'ingestion ; si une
  ingestion est en cours, elle attend ou est refusée avec `purge_busy`. Les fichiers de logs
  et de rapports sont purgés avec la même règle de rétention.
- **Retrait d'un dépôt.** Par défaut, le dépôt est **archivé** (`retired_at`) : il disparaît
  des agrégats, son historique reste consultable. La suppression définitive est explicite,
  cascadée et auditée. Le dépôt principal est réélu automatiquement, ou le retrait est refusé
  s'il est le dernier.
- **Gate de feature.** Le gate d'une feature est la **conjonction** des gates de ses dépôts
  (`feature_repositories`) et des tâches (`task_repositories`) ; chaque `gate_run` porte son
  `repository_id`. Une feature n'est verte que si tous les dépôts concernés sont verts.
- **Accès WSL2.** `127.0.0.2` n'est pas garanti depuis le navigateur de l'hôte Windows en mode
  NAT. Le guide d'installation documente le mode réseau miroir ou l'usage d'un navigateur dans
  WSL ; un test de matrice vérifie la joignabilité.

## 8. Modèle de données SQLite

Fichier : `data/sdlc.sqlite3` (emplacement configurable). Réglages obligatoires :
`journal_mode=WAL`, `foreign_keys=ON`, `synchronous=NORMAL`, `busy_timeout=5000`.
Un seul écrivain ; les ingestions passent par une file locale.

| Table | Rôle | Champs principaux | Index |
|---|---|---|---|
| `projects` | Projet suivi | `id`, `name`, `slug`, `timezone`, `created_at` | `slug` unique |
| `repositories` | Dépôts du projet (multi-dépôts) | `id`, `project_id`, `name`, `provider`, `url`, `local_path`, `default_branch`, `is_primary`, `dedup_group`, `is_mirror`, `is_fork`, `retired_at` | `(project_id, name)` unique, `(project_id, local_path)` |
| `persons` | Personnes canoniques | `id`, `project_id`, `display_name`, `role`, `is_bot`, `superseded_by_person_id` (nullable) | `(project_id, display_name)` non unique |
| `person_identities` | Emails et comptes fournisseur d'une personne | `id`, `project_id`, `person_id`, `provider`, `external_id`, `email`, `kind` | `(project_id, provider, external_id)` unique, `(project_id, email)` unique |
| `commits` | Commits | `id`, `repository_id`, `sha`, `person_id`, `committed_at`, `additions`, `deletions`, `files_changed`, `is_merge`, `is_bot`, `ai_assisted`, `commit_fingerprint`, `message` | `(repository_id, sha)` unique, `(repository_id, committed_at)`, `(commit_fingerprint)` |
| `merge_requests` | MR | `id`, `repository_id`, `number`, `title`, `author_person_id`, `state`, `created_at`, `merged_at`, `target_branch`, `source_branch`, `merge_strategy`, `additions`, `deletions` | `(repository_id, number)` unique, `(repository_id, state)`, `(repository_id, merged_at)` |
| `reviews` | Revues | `id`, `mr_id`, `reviewer_person_id`, `reviewer_agent_id`, `model`, `state`, `submitted_at`, `is_agent`, `independence` | `(mr_id)`, `(submitted_at)` |
| `approvals` | Approbations | `id`, `mr_id`, `actor_person_id`, `actor_type`, `approved_at` | `(mr_id)` |
| `features` | Features | `id`, `project_id`, `primary_repository_id` (nullable), `key`, `name`, `status`, `owner_person_id`, `spec_path` | `(project_id, status)` |
| `feature_repositories` | Dépôts couverts par une feature | `feature_id`, `repository_id` | clé primaire composite |
| `tasks` | Tâches | `id`, `feature_id`, `primary_repository_id` (nullable), `key`, `title`, `status`, `owner_person_id`, `reviewer_person_id`, `files_json`, `acceptance`, `updated_at` | `(feature_id, status)` |
| `task_repositories` | Dépôts touchés par une tâche | `task_id`, `repository_id`, `is_primary` | clé primaire composite |
| `agents` | Agents | `id`, `name`, `kind`, `cli`, `models_json`, `role`, `enabled`, `max_concurrency` | `name` |
| `task_runs` | Runs | `id`, `task_id`, `agent_id`, `primary_repository_id` (nullable), `model`, `role`, `started_at`, `ended_at`, `status`, `cost_eur`, `estimated_cost_eur`, `budget_eur`, `tokens_in`, `tokens_out`, `pid`, `process_group`, `exit_code`, `log_path`, `cancel_requested`, `report_path` | `(task_id)`, `(started_at)`, `(status)` |
| `gates` | Définition des gates | `id`, `project_id`, `key`, `name`, `blocking`, `config_json`, `config_fingerprint` | `(project_id, key)` |
| `gate_runs` | Exécutions | `id`, `project_id`, `repository_id` (nullable), `gate_key`, `status`, `threshold`, `actual`, `evidence_path`, `commit_sha`, `started_at`, `finished_at` | `(project_id, gate_key, started_at)` |
| `findings` | Constats | `id`, `gate_run_id`, `category`, `severity`, `reachable`, `file`, `line`, `evidence`, `fix`, `status`, `owner_person_id`, `waiver_id` | `(gate_run_id, severity)` |
| `waivers` | Dérogations | `id`, `finding_id` (nullable), `gate_run_id` (nullable), `reason`, `owner_person_id`, `created_at`, `expires_at`, `approved_by_person_id` | `(expires_at)` |
| `deployments` | Déploiements | `id`, `project_id`, `repository_id` (nullable), `env`, `version`, `status`, `started_at`, `finished_at`, `by_person_id` (nullable), `by_label`, `note`, `feature_id` | `(project_id, env, started_at)` |
| `documents` | Documents | `id`, `project_id`, `repository_id` (nullable), `path`, `kind`, `last_reviewed_at`, `status`, `hash` | `(project_id, path)` |
| `process_signals` | Signaux processus | `id`, `repository_id`, `signal`, `observed`, `interpretation`, `confidence`, `detected_at` | `(repository_id, signal)` |
| `process_profile` | Profil par dépôt | `repository_id`, `project_id`, `detected`, `confidence`, `override`, `cadence_days`, `updated_at` | clé primaire dépôt |
| `decisions` | Décisions | `id`, `project_id`, `subject_type`, `subject_id`, `decision`, `actor_person_id` (nullable), `actor_label`, `reason`, `created_at`, `expires_at` | `(project_id, created_at)` |
| `audit_events` | Audit | `id`, `project_id`, `actor_person_id` (nullable), `actor_label`, `action`, `object_type`, `object_id`, `payload_json`, `created_at`, `generation`, `prev_hash`, `hash` | `(project_id, created_at)`, `(generation)` |
| `ingestion_runs` | Ingestion | `id`, `project_id`, `repository_id` (nullable), `source`, `started_at`, `finished_at`, `status`, `stats_json` | `(project_id, started_at)` |
| `backup_runs` | Sauvegardes (globales) | `id`, `path`, `size_bytes`, `started_at`, `finished_at`, `status`, `verified_at` | `(started_at)` |

Contraintes :

- Clés étrangères `ON DELETE CASCADE` sauf `audit_events` (conservation) et `backup_runs`.
- `audit_events` : chaîne `hash = sha256(prev_hash + payload)` ; `generation` permet un
  ancrage explicite. Toute rupture est signalée.
- Rétention par défaut : **12 mois** pour commits, MR, runs, findings, déploiements et
  documents ; configurable par projet et par table. **L'audit est exclu de la purge
  automatique** : sa purge est explicite, précédée d'une sauvegarde vérifiée et d'un
  événement d'ancrage. Une purge est journalisée.
- Un commit n'est compté qu'une fois par dépôt ; l'agrégation « tous » déduplique par
  `commit_fingerprint` et par `dedup_group`.
- Un dépôt retiré est archivé (`retired_at`) par défaut ; la suppression définitive est
  explicite et cascadée.
- `task_runs.status` ∈ `queued` | `running` | `done` | `failed` | `timeout` | `cancelled`.
- La chaîne d'audit est **par projet** : `prev_hash` et `generation` sont adossés au couple
  `(project_id, generation)`.
- La sauvegarde est **globale** (fichier SQLite complet) ; `backup_runs` n'est pas rattachée
  à un projet.
- Aucun jeton, mot de passe ou secret en base.

## 9. Interfaces

### 9.1 Interface web

- Routes : `/`, `/features`, `/gates`, `/review`, `/deploys`, `/team`, `/process`,
  `/security`, `/perf`, `/agents`, `/docs`, `/config`.
- Sélecteur de **dépôt** dans l'en-tête : « tous les dépôts » ou un dépôt ; le choix est
  conservé dans l'URL et s'applique aux vues qui agrègent.
- Navigation latérale, thème clair/sombre, responsive, clavier.
- États : chargement, vide, erreur, données périmées, **projet ou dépôt désactivé**.
- Chaque chiffre a une infobulle « source » et un lien vers la preuve.
- Aucune couleur seule ne porte l'information (badge + texte).
- Les mises à jour SSE (logs, ingestion, gates) sont annoncées dans une région `aria-live`
  et ne déplacent pas le focus.
- **Ouverture du suivi** : à la fin de la génération, la vue `/suivi` s'ouvre
  automatiquement dans un nouvel onglet si `ui.open_suivi_on_ready` est vrai (défaut) ;
  sinon un bandeau avec un lien persistant s'affiche. L'ouverture a lieu **une seule fois
  par génération**, ne bloque pas l'interface et n'ouvre pas d'onglet si l'utilisateur a
  déjà la vue Suivi active. Réglages : `ui.open_suivi_on_ready`, `ui.suivi_path`.
- **Synchronisation du suivi** : tout changement de statut de tâche met à jour `tasks.md`
  (case cochée/décochée), `state.json` (statut, note, date) et le fichier de suivi HTML dans
  la même opération logique, en moins de 2 s. Un watcher resynchronise les modifications
  externes de `tasks.md` ou `state.json`. L'événement SSE `suivi.updated` est émis après
  chaque mise à jour. Aucun mode « lot » ne remplace la mise à jour tâche par tâche.
- Les logs d'agent sont affichés en **texte échappé**, jamais en HTML interprété.
- L'âge de la dernière sauvegarde et de la dernière ingestion est visible.
- Actions sensibles (décision, dérogation, lancement d'agent, purge) : confirmation, motif et
  affichage de la commande exacte avant exécution.

### 9.2 API REST

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/health` | Santé, version, schéma |
| GET | `/api/csrf` | Jeton CSRF pour les écritures |
| GET | `/api/projects` | Liste des projets |
| GET | `/api/projects/{id}/repositories` | Dépôts du projet |
| POST | `/api/projects/{id}/repositories` | Ajouter un dépôt |
| PUT | `/api/projects/{id}/repositories/{repo_id}/primary` | Désigner le dépôt principal |
| DELETE | `/api/projects/{id}/repositories/{repo_id}` | Retirer un dépôt (règle de conservation explicite) |
| GET | `/api/projects/{id}/overview` | KPI et décisions |
| GET | `/api/projects/{id}/suivi` | Fichier de suivi généré (HTML/JSON) |
| GET | `/api/projects/{id}/suivi/status` | Prêt/non prêt, date de génération, chemin |
| PATCH | `/api/projects/{id}/tasks/{task_id}` | Changer le statut d'une tâche et resynchroniser `tasks.md`, `state.json` et le HTML |
| GET | `/api/projects/{id}/features` | Features, filtres, pagination |
| GET | `/api/projects/{id}/tasks` | Tâches |
| GET | `/api/projects/{id}/gates` | Dernier verdict par gate |
| GET | `/api/projects/{id}/gates/{key}/runs` | Historique |
| GET | `/api/projects/{id}/findings` | Findings, filtres |
| POST | `/api/projects/{id}/waivers` | Créer une dérogation motivée |
| GET | `/api/projects/{id}/reviews` | Revues |
| POST | `/api/projects/{id}/reviews` | Préparer une revue |
| POST | `/api/reviews/{id}/launch` | Lancer la revue |
| POST | `/api/reviews/{id}/decision` | Décision humaine |
| GET | `/api/projects/{id}/team` | Métriques équipe |
| GET | `/api/projects/{id}/process` | Profil et signaux |
| PUT | `/api/projects/{id}/process/override` | Surcharge motivée |
| GET | `/api/projects/{id}/deployments` | Déploiements |
| GET | `/api/projects/{id}/agents` | Runs |
| POST | `/api/projects/{id}/runs` | Lancer un exécutant ou un relecteur |
| GET | `/api/runs/{id}` | État, logs, coût |
| POST | `/api/runs/{id}/cancel` | Annuler un run |
| GET | `/api/runs/{id}/events` | SSE : logs et état |
| GET | `/api/projects/{id}/documents` | Documents |
| POST | `/api/projects/{id}/ingest` | Lancer une ingestion |
| GET | `/api/projects/{id}/ingestions` | Historique |
| POST | `/api/backup` | Sauvegarde globale du fichier SQLite |
| GET | `/api/backups` | Historique et âge des sauvegardes |
| POST | `/api/backups/{backup_id}/verify` | Vérifier une sauvegarde |
| POST | `/api/projects/{id}/purge` | Purger les données de plus de 12 mois (hors audit) |
| GET | `/api/projects/{id}/export` | Export JSON/CSV |
| GET | `/api/events` | SSE : ingestion, gate, revue |

Toutes les réponses sont paginées (`limit`, `offset`, `total`) et filtrables. Les routes
qui agrègent acceptent `repository_id` (ou `all`). Les erreurs suivent un format unique
`{code, message, details}`. La sauvegarde et la restauration sont **globales** ; la vue
projet n'affiche que l'âge de la dernière sauvegarde.

### 9.3 CLI

| Commande | Rôle |
|---|---|
| `sdlc-console init` | Créer la base, appliquer les migrations |
| `sdlc-console serve` | Lancer le serveur local (`127.0.0.2:8765` par défaut, sans authentification) |
| `sdlc-console serve --open-suivi` | Ouvrir le navigateur sur la vue Suivi dès qu'elle est prête |
| `sdlc-console suivi open` | Ouvrir le fichier de suivi généré (navigateur ou chemin) |
| `sdlc-console task set <id> <statut> --note "<note>"` | Changer le statut d'une tâche et resynchroniser les trois supports |
| `sdlc-console project add` | Ajouter un projet |
| `sdlc-console project repo add` | Ajouter un dépôt GitHub/GitLab à un projet |
| `sdlc-console project repo remove` | Retirer un dépôt (règle de conservation explicite) |
| `sdlc-console collect` | Ingérer Git, MR, CI, state, runs, docs (par dépôt ou tous) |
| `sdlc-console check` | Lancer les gates (délègue à `scripts/ci.sh`) |
| `sdlc-console review` | Préparer une revue indépendante |
| `sdlc-console review launch` | Lancer la revue avec un agent et un modèle choisis |
| `sdlc-console run` | Lancer un exécutant ou un relecteur via un modèle de commande |
| `sdlc-console run cancel` | Annuler un run en cours (groupe de processus) |
| `sdlc-console run logs` | Suivre les logs d'un run |
| `sdlc-console backup --verify` | Sauvegarde SQLite globale vérifiée |
| `sdlc-console restore` | Restauration testée |
| `sdlc-console purge` | Appliquer la rétention (12 mois par défaut, hors audit ; logs inclus) |
| `sdlc-console purge --audit` | Purger l'audit explicitement, avec ancrage et sauvegarde |
| `sdlc-console process corpus <chemin>` | Mesurer la détection de processus sur un corpus étiqueté |
| `sdlc-console export` | Export JSON/CSV |
| `sdlc-console doctor` | Diagnostic : versions, chemins, permissions, schéma, port |
| `sdlc-console doctor --with-tokens` | Vérifier les jetons et quotas GitHub/GitLab |
| `sdlc-console schema status` | Version du schéma et migrations en attente |
| `sdlc-console schema migrate` | Appliquer les migrations (sauvegarde préalable) |
| `sdlc-console demo` | Charger le jeu de démonstration |

Toute commande retourne `0` en succès, `1` en échec fonctionnel, `2` en erreur d'usage.

### 9.4 Formats de fichiers

- Entrées : `.git`, `reports/junit/*.xml`, `reports/coverage/*`, `reports/security/*.sarif`,
  `reports/perf/*.json`, `docs/suivi/state.json`, `openspec/changes/*/tasks.md`,
  `docs/journal/*.jsonl`, `docs/incidents/*.md`, `docs/metrics/history.jsonl`,
  `sdlc.config.yaml`.
- Fixtures hors réseau : réponses GitHub/GitLab/CI simulées (ETag, pagination, erreurs) pour
  les tests d'ingestion et la recette.
- Sorties : `reports/gates/*.json`, `reports/reviews/*.json`, `reports/reviews/*.md`,
  `data/sdlc.sqlite3`, sauvegardes `.sqlite3.zst` (ou `.sqlite3` + somme).
- Preuve de performance : `reports/perf/*.json` avec au minimum
  `{"commit":"…","window":"…","case":"…","p50_ms":0,"p95_ms":0,"p99_ms":0,"budget_ms":0,"tool":"…"}`.
- Aucun format propriétaire : tout est lisible sans l'application.

## 10. Exigences non fonctionnelles

| Domaine | Exigence | Vérification |
|---|---|---|
| Performance | Vue d'ensemble < 1,5 s sur 100 k commits / 1 M lignes | Test de charge sur jeu de démonstration |
| Performance | Vue projet multi-dépôts < 2 s sur 5 dépôts / 100 k commits | Test de charge |
| Performance | Liste paginée < 500 ms | Mesure API |
| Ingestion | 10 k commits incrémentaux < 60 s par dépôt | Benchmark reproductible |
| Démarrage | < 2 s à froid | Mesure |
| Mémoire | < 512 Mo pour 100 k commits | Mesure |
| Disponibilité | Fonctionne hors ligne, sans service tiers | Test réseau coupé |
| Sécurité | Écoute `127.0.0.2` par défaut ; tout bind hors `127.0.0.0/8` refusé | Test paramétré (`0.0.0.0`, IP LAN, `::`, hostname) |
| Sécurité | Validation stricte de `Host` et refus des `Origin`/`Referer` externes | Test DNS rebinding |
| Authentification | Aucune en MVP ; boucle locale uniquement ; acteur non authentifié mentionné | Revue de configuration + test d'écoute |
| Sécurité | CSRF, XSS, injection SQL, path traversal couverts | Tests + revue |
| Sécurité | Logs d'agent en texte échappé, CSP | Test XSS |
| Sécurité | Environnement des agents purgé des jetons | Test d'environnement |
| Secrets | Aucun secret en base ni en log | Test avec faux jeton |
| Suivi | Ouverture automatique < 2 s après la fin de génération, une seule fois | Test de bout en bout |
| Suivi | Synchronisation < 2 s à chaque changement de statut, atomique, watcher | Test de bout en bout et test de concurrence |
| Accessibilité | RGAA 4.1 AA / WCAG 2.2 AA ; SSE annoncé en `aria-live` | Audit + tests clavier |
| Confidentialité | Aucune télémétrie ; données locales ; minimisation | Revue réseau + revue RGPD |
| Confidentialité | Base légale et durées par catégorie à confirmer dans `exigences-nf.md` | Revue |
| Sauvegarde | Sauvegarde et restauration testées ; âge affiché | Scénario automatisé |
| Rétention | 12 mois par défaut, configurable ; audit exclu de la purge auto | Test de purge + ancrage |
| Migration | Sauvegarde avant migration ; schéma plus récent refusé | Test de migration |
| Trousseau OS | Keychain macOS, libsecret Linux, Credential Manager Windows/WSL | Test par OS |
| Portabilité | macOS, Linux, Windows (WSL accepté en MVP) | CI matrice |
| Maintenance | Couverture ≥ 80 %, lint et typecheck verts | `scripts/ci.sh` |
| Observabilité | Logs structurés, audit, métriques locales | Revue + tests |
| Documentation | README, guide d'installation, runbook, ADR | Revue |

## 11. Sécurité et menaces

Analyse STRIDE légère ; à compléter dans `docs/architecture/menaces.md` à l'étape 2.

| Composant | Menace | Risque | Mitigation |
|---|---|---|---|
| API locale | Accès depuis le réseau | Élevé | Bind `127.0.0.2`, jamais `0.0.0.0` ; reverse proxy TLS hors MVP |
| API locale | Accès non authentifié depuis le poste | Moyen | Boucle locale uniquement, CORS désactivé, CSRF, audit ; token prévu avant toute exposition LAN |
| API | CSRF | Moyen | Token CSRF, SameSite, vérification d'origine |
| API | Injection SQL | Élevé | ORM/requêtes paramétrées, tests |
| Interface | XSS via Markdown/HTML | Élevé | HTML brut désactivé, sanitization, CSP |
| Interface | XSS via logs SSE d'agent | Élevé | Logs en texte échappé, jamais de HTML, CSP |
| Ingestion | Path traversal | Élevé | Chemins allowlistés, résolution réelle, refus `..` |
| Ingestion | Secret dans un log | Élevé | Redaction, détection de motifs, jamais en base |
| Revue | Prompt injection via dépôt/spec | Élevé | Contenu traité comme données, pas d'outil piloté par le contenu |
| Agents | Écriture Git ou exfiltration | Élevé | Lecture seule pour la revue, allowlist de commandes, pas de réseau par défaut |
| Agents | Jetons du serveur hérités par le processus | Élevé | Environnement purgé, variables minimales, test dédié |
| Agents | Injection de commande depuis l'interface | Élevé | Modèles de commande configurés, paramètres validés, jamais de shell libre |
| Agents | Coût ou durée non bornés | Moyen | Budget, timeout, limite de concurrence, kill switch |
| Agents | Processus fils orphelins à l'annulation | Moyen | Groupe de processus, signal au groupe, vérification de terminaison |
| Agents | Lancement sur un dépôt non déclaré | Élevé | Vérification du `repository_id` et du chemin réel |
| Décisions | Acteur non authentifié, non-répudiation impossible | Moyen | Mention explicite dans l'UI et l'audit ; token avant LAN |
| Audit | Modification de l'historique | Moyen | Chaîne de hachage, contrôle d'intégrité, ancrage avant purge |
| Audit | Chaîne globale mélangeant les projets | Faible | Chaîne par projet, `prev_hash` adossé à `(project_id, generation)` |
| SQLite | Corruption / sauvegarde non testée | Moyen | WAL, `VACUUM INTO`, restauration testée, sauvegarde globale |
| SQLite | Lecture en clair sur le poste | Moyen | Limite assumée ; chiffrement disque OS recommandé |
| Trousseau | Jeton stocké dans un fichier ou un log | Moyen | Keychain/libsecret/Credential Manager, fallback env documenté |
| Dépendances | Vulnérabilité transitive | Moyen | SBOM, Trivy/OSV, Renovate |
| Processus | Faux profil | Moyen | Confiance + preuves + surcharge auditée |

## 12. Contraintes techniques

- **Local d'abord** : SQLite, aucun service externe obligatoire, aucune télémétrie.
- **Écoute `127.0.0.2`** (boucle locale), **aucune authentification** en MVP ; `0.0.0.0`
  refusé. Toute exposition réseau exige une décision et un token.
- **Multi-dépôts** : un projet regroupe N dépôts GitHub/GitLab ; les métriques sont calculées
  par dépôt puis agrégées.
- **Rétention 12 mois par défaut**, configurable par projet et par table.
- **Agents** : préparation et suivi, **et lancement depuis l'interface**, via des modèles de
  commande configurés ; jamais de commande libre.
- **Pas de lock-in IDE** : aucune dépendance à Kiro, Cursor, Copilot ou à un plugin d'IDE.
- **Pas de lock-in agent** : les agents sont des adaptateurs CLI ; le cœur ne dépend d'aucun.
- **Pas de lock-in spec** : le format Markdown reste lisible sans OpenSpec ; OpenSpec est un
  adaptateur optionnel.
- **Python 3.12+** pour le backend et les collecteurs ; **Node 22+** uniquement pour le build
  frontend, pas au runtime.
- **SQLite 3.45+**, WAL, un seul écrivain.
- **Frontend** : React 19 + TypeScript + Vite (décision du 2026-10-20).
- **Backend** : FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 (proposition).
- **Tests** : pytest, Playwright, ruff, mypy ; `scripts/ci.sh` comme point d'entrée.
- **Packaging** : `uv`/`pipx`, commande unique `sdlc-console` ; build frontend embarqué.
- **Langue** : interface en français ; identifiants et code en anglais/ASCII.

## 13. Livrables

1. Code backend, frontend, migrations, CLI.
2. Schéma JSON : `review.schema.json`, `gate.schema.json`, `team.schema.json`,
   `process.schema.json`, `run.schema.json`, `perf.schema.json`.
3. Change OpenSpec `console-sdlc` : `proposal.md`, `design.md`, deltas de spec, `tasks.md`.
4. Brief, exigences NF, ADR 001–006, analyse de menaces.
5. Tests unitaires, d'intégration, de bout en bout, fixtures de démonstration multi-dépôts.
6. Fixtures GitHub/GitLab/CI hors réseau (ETag, pagination, erreurs) pour la recette.
7. Corpus de dépôts étiquetés pour mesurer la détection de processus (≥ 80 %).
8. Script de référence pour recalculer les métriques d'équipe (écart ≤ 2 %).
9. `scripts/ci.sh` vert (lint, tests, couverture, SAST, dépendances, secrets, build).
10. Documentation : README, guide d'installation, guide utilisateur, runbook, ADR.
11. Procédure de sauvegarde/restauration testée et procédure de purge (12 mois, audit ancré).
12. Runner d'agents : lancement, suivi, annulation, budget, journal.
13. Jeu de démonstration (`--demo`) sans données réelles.
14. Générateur de suivi et ouverture automatique dès qu'il est prêt.
15. Rapport de recette et matrice de scénarios.

## 14. Critères d'acceptation

```gherkin
Fonctionnalité: Ingestion et vue d'ensemble
  Scénario: Un projet Git local alimente le tableau de bord
    Étant donné un dépôt Git local avec au moins 10 commits
    Quand je crée le projet puis lance l'ingestion
    Alors la vue d'ensemble affiche le nombre de commits et la dernière ingestion
    Et la vue Équipe affiche les auteurs avec leurs commits
    Et une deuxième ingestion ne crée pas de doublons

  Scénario: Un projet multi-dépôts agrège sans double comptage
    Étant donné un projet avec deux dépôts GitHub et GitLab
    Quand j'ingère les deux dépôts
    Alors la vue Équipe affiche les deux dépôts et le total agrégé
    Et le filtre « dépôt A » ne montre que les commits du dépôt A
    Et un commit n'est compté qu'une fois dans le total

Fonctionnalité: Lancement d'agent depuis l'interface
  Scénario: Un run est lancé avec un budget et annulable
    Étant donné un projet avec un dépôt déclaré et un agent configuré
    Quand je lance un relecteur avec un budget de 2 € et une durée max de 20 min
    Alors la commande exacte est affichée avant confirmation
    Et le run passe en "running" puis "done" ou "cancelled"
    Et si le plafond est atteint, le run est arrêté
    Et le coût réel est affiché et tout dépassement est signalé
    Et toute tentative d'écriture Git est refusée et auditée

Fonctionnalité: Gate de couverture
  Scénario: Une couverture insuffisante bloque
    Étant donné un rapport Cobertura à 72 %
    Et un seuil global de 80 %
    Quand je lance les gates
    Alors le gate couverture est "fail"
    Et la preuve pointe vers le fichier Cobertura
    Et la vue d'ensemble affiche une décision en attente

Fonctionnalité: Support des langages
  Scénario: Un langage sans adaptateur bloque
    Étant donné un dépôt contenant des fichiers Kotlin
    Et aucun adaptateur Kotlin déclaré
    Quand je lance les gates
    Alors le gate langages est "fail" avec "unsupported_language"
    Et aucun gate n'est affiché comme "not_run" silencieux

Fonctionnalité: Revue indépendante
  Scénario: Un relecteur différent est exigé
    Étant donné une tâche réalisée par l'agent A avec le modèle M1
    Et un relecteur disponible avec l'agent B et le modèle M2
    Quand je prépare la revue
    Alors le paquet est aveugle
    Et l'indépendance est "complète"
    Et la fiche de décision contient les trois bloquants maximum

Fonctionnalité: Décision humaine
  Scénario: Une dérogation est tracée
    Étant donné un finding bloquant
    Quand j'approuve une dérogation avec un motif et une date d'expiration
    Alors le gate passe à "waived"
    Et l'audit enregistre l'acteur, la date et le motif
    Et la dérogation expire automatiquement

Fonctionnalité: Processus
  Scénario: Un profil est détecté avec ses preuves
    Étant donné un dépôt sans branche develop, avec des tags semver et 80 % de squash
    Quand j'ouvre la vue Processus
    Alors le profil "GitHub Flow + releases" est proposé
    Et la confiance et les six signaux sont affichés
    Et je peux surcharger le profil avec un motif

Fonctionnalité: Sauvegarde
  Scénario: Une sauvegarde se restaure
    Étant donné une base avec un projet
    Quand je lance la sauvegarde puis la restauration dans un fichier neuf
    Alors le projet et ses commits sont présents
    Et le contrôle d'intégrité de l'audit est valide

Fonctionnalité: Fichier de suivi
  Scénario: Le suivi s'ouvre dès qu'il est prêt
    Étant donné une génération de suivi en cours
    Quand le fichier est prêt
    Alors la vue Suivi s'ouvre une seule fois dans un nouvel onglet
    Et un lien persistant reste disponible
    Et l'interface n'est pas bloquée
    Et aucune ouverture supplémentaire n'a lieu si la vue est déjà active

  Scénario: Un changement de statut resynchronise les trois supports
    Étant donné une tâche à "todo"
    Quand je passe la tâche à "done" avec une note
    Alors tasks.md est coché
    Et state.json contient "done" et la note
    Et le fichier de suivi HTML est régénéré
    Et l'événement "suivi.updated" est émis en moins de 2 s

  Scénario: Une modification externe est resynchronisée
    Étant donné tasks.md modifié hors de l'interface
    Quand le watcher détecte le changement
    Alors state.json et le HTML sont resynchronisés
    Et un conflit est signalé si state.json diverge

Fonctionnalité: Rétention et intégrité
  Scénario: La purge respecte 12 mois et exclut l'audit
    Étant donné une base avec un commit de 13 mois et un audit de 13 mois
    Et une sauvegarde vérifiée récente
    Quand je lance `sdlc-console purge`
    Alors le commit est supprimé
    Et l'audit est conservé
    Et le nombre de lignes supprimées est journalisé

  Scénario: La purge d'audit exige un ancrage
    Étant donné une base avec un audit de 13 mois
    Quand je lance `sdlc-console purge --audit`
    Alors la commande demande confirmation et un motif
    Et une sauvegarde récente est vérifiée
    Et un événement d'ancrage clôt la génération
    Et le contrôle d'intégrité de la nouvelle chaîne est valide

Fonctionnalité: Multi-dépôts
  Scénario: Le retrait d'un dépôt est explicite
    Étant donné un projet avec deux dépôts ingérés
    Quand je retire le dépôt B
    Alors le dépôt B est archivé par défaut et disparaît des agrégats
    Et son historique reste consultable
    Et le dépôt principal est réélu si nécessaire
    Et une suppression définitive demande une confirmation et est auditée

  Scénario: Un contributeur multi-identités est compté une fois
    Étant donné un contributeur avec deux emails et deux comptes fournisseur
    Quand j'ingère les deux dépôts
    Alors la vue Équipe affiche une seule personne
    Et son bus factor n'est pas doublé

  Scénario: Un cherry-pick est signalé comme dédoublonné
    Étant donné le même changement présent dans deux dépôts non déclarés miroirs
    Quand j'ingère les deux dépôts
    Alors l'interface affiche un badge « dédoublonnage appliqué »
    Et le dépôt d'origine est affiché
    Et le total ne masque pas le doublon

Fonctionnalité: Ingestion
  Scénario: Un quota GitHub interrompt proprement
    Étant donné un jeton valide et un quota épuisé
    Quand je lance l'ingestion
    Alors le badge de la source passe à "échec"
    Et aucune donnée partielle n'est marquée "à jour"
    Et une relance reprend sans doublon

Fonctionnalité: Collecteurs
  Scénario: Une PR GitHub et une MR GitLab sont normalisées
    Étant donné une PR GitHub et une MR GitLab avec des états différents
    Quand je lance l'ingestion
    Alors les deux apparaissent avec le même modèle de données
    Et les valeurs absentes sont affichées "non mesuré"

Fonctionnalité: Runner d'agents
  Scénario: Un run qui dépasse le budget est arrêté
    Étant donné un run avec un budget de 2 € et une durée max de 20 min
    Quand le coût estimé atteint 2 €
    Alors le processus et ses enfants sont arrêtés
    Et le statut passe à "failed"
    Et le coût réel est affiché
    Et aucun processus fils ne survit

  Scénario: Un run qui plante ou expire est tracé
    Étant donné un run avec une durée max de 20 min
    Quand le processus plante ou que le timeout expire
    Alors le statut passe à "failed" ou "timeout" avec la cause
    Et les logs sont conservés
    Et le coût réel est affiché
    Et les processus fils sont terminés

  Scénario: Le préflight bloque un lancement impossible
    Étant donné une CLI absente ou un budget supérieur au plafond du projet
    Quand je confirme le lancement
    Alors le lancement est refusé avant exécution
    Et la cause est affichée
    Et aucune ligne de run n'est créée

Fonctionnalité: Revue
  Scénario: Un relecteur du même modèle est refusé
    Étant donné un auteur et un seul relecteur disponible avec le même modèle
    Quand je prépare la revue
    Alors l'interface explique le blocage et propose un autre modèle
    Et aucune revue n'est lancée sans dérogation humaine

  Scénario: Une dérogation d'indépendance est auditée
    Étant donné un relecteur du même modèle et une dérogation humaine motivée
    Quand la revue se termine
    Alors l'indépendance est affichée "dégradée"
    Et la dérogation est enregistrée dans l'audit

Fonctionnalité: Migration
  Scénario: Un schéma plus récent est refusé
    Étant donné une base dont le schéma est plus récent que l'application
    Quand je démarre la Console
    Alors le démarrage est refusé avec un message explicite
    Et aucune migration destructive n'est tentée

Fonctionnalité: Purge
  Scénario: Une purge pendant une ingestion attend ou est refusée
    Étant donné une ingestion en cours
    Quand je lance une purge
    Alors la purge attend la fin ou est refusée avec le code "purge_busy"
    Et aucune donnée n'est corrompue

Fonctionnalité: Processus
  Scénario: Un dépôt sans signal donne "non identifiable"
    Étant donné un dépôt sans tags, sans branches de flux et avec un historique squashé
    Quand j'ouvre la vue Processus
    Alors le profil est "non identifiable"
    Et les raisons sont affichées
    Et aucune heuristique n'est inventée

Fonctionnalité: Revue
  Scénario: Trois rejets escaladent
    Étant donné une tâche rejetée trois fois
    Quand la troisième revue se termine
    Alors la tâche passe en "blocked"
    Et l'humain est notifié
    Et l'itération est conservée dans l'audit

Fonctionnalité: Accessibilité
  Scénario: Les 12 vues sont navigables au clavier
    Étant donné un utilisateur au clavier
    Quand il parcourt les 12 vues
    Alors chaque action est atteignable
    Et le focus reste visible
    Et les mises à jour SSE sont annoncées sans déplacer le focus

Fonctionnalité: Sécurité locale
  Scénario: L'application n'écoute pas sur le réseau par défaut
    Étant donné un démarrage sans option
    Quand j'inspecte l'adresse d'écoute
    Alors elle est 127.0.0.2
    Et aucune authentification n'est demandée
    Et aucune requête sortante n'est émise sans configuration explicite
```

## 15. Découpage en lots

| Lot | Contenu | Critère de sortie |
|---|---|---|
| **L0 — Socle** | Dépôt, CI, ADR de stack, schéma SQLite, migrations, CLI `init/serve/doctor`, écoute `127.0.0.2` sans auth, validation `Host` | `sdlc-console doctor` vert, tests de base |
| **L1 — Projets multi-dépôts et ingestion Git** | Projets, dépôts, personnes, commits, identités, activité, sélecteur de dépôt, vue d'ensemble, fixtures Git | Ingestion idempotente sur deux dépôts, identité canonique testée |
| **L2 — Features et tâches** | `state.json`, `openspec/`, traçabilité, filtres, tâches multi-dépôts, génération et ouverture du suivi | Une feature réelle s'affiche avec ses tâches ; le suivi s'ouvre à la fin |
| **L3 — Gates** | Tests, couverture, sécurité, performance, données, i18n, langages, preuves, dérogations, `not_run` par tier | Un gate bloquant empêche le vert |
| **L4 — Équipe et processus** | Métriques, bus factor, propriété, déduplication, détection par dépôt, corpus étiqueté, script de référence | Les deux menus sont réels, écart ≤ 2 %, ≥ 80 % de classification |
| **L5 — Revue, décisions et agents** | Sélection d'agent/modèle, paquet aveugle, rapport, fiche, lancement, annulation, budget, environnement purgé, SSE échappé, audit | Une revue complète est traçable de bout en bout |
| **L6 — Vues restantes** | Sécurité, performance/données, agents, docs, config | Les 12 vues sont alimentées |
| **L7 — Finition** | Accessibilité, performance, packaging, sauvegarde, purge 12 mois avec audit ancré, démo, documentation, recette | Recette passée, `scripts/ci.sh` vert |

## 16. Risques

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| SQLite verrouillé par une ingestion longue | Moyenne | Moyen | File d'ingestion, WAL, lots courts, `busy_timeout` |
| Historique Git volumineux | Moyenne | Moyen | Ingestion incrémentale, index, pagination |
| Métriques multi-dépôts erronées | Moyenne | Moyen | Personnes canoniques, empreinte de commit, `dedup_group`, tests de non-double-comptage |
| Identités multiples d'un contributeur | Élevée | Moyen | `persons` + `person_identities`, fusion auditée, test multi-emails |
| API GitHub/GitLab limitée | Moyenne | Moyen | Cache, ETag, backoff, mode fichier, fixtures hors réseau |
| Faux positif de détection de processus | Élevée | Faible | Confiance, preuves, surcharge auditée, corpus étiqueté |
| Faux positif sécurité/performance | Élevée | Moyen | Distinguer bloquant et alerte, dérogation |
| Prompt injection via dépôt/spec | Moyenne | Élevé | Contenu = données, pas d'outil piloté par le contenu |
| Agent lancé depuis l'UI : injection, coût, Git | Moyenne | Élevé | Modèles de commande, validation, budget, timeout, lecture seule, audit |
| Jetons hérités par un agent | Moyenne | Élevé | Environnement purgé, test dédié |
| Processus fils orphelins | Moyenne | Moyen | Groupe de processus, kill-tree, test de fuite |
| Coût des modèles | Moyenne | Moyen | Budgets, dry-run, modèles légers pour les tâches simples |
| Fuite de données par télémétrie | Faible | Élevé | Aucune télémétrie par défaut, revue réseau |
| Dérive de périmètre | Élevée | Moyen | MVP local, hors périmètre explicite, ADR |
| Dépendance à un agent | Moyenne | Moyen | Adaptateurs CLI, tests sans agent |
| Purge de rétention trop agressive | Faible | Élevé | 12 mois par défaut, configuration, journalisation, sauvegarde vérifiée, audit exclu |
| Audit tronqué par la purge | Faible | Élevé | Audit exclu de la purge auto, ancrage explicite, contrôle d'intégrité |

## 17. Décisions tranchées

| Décision | Choix | Date | Conséquence |
|---|---|---|---|
| Frontend | **React 19 + TypeScript + Vite** | 2026-10-20 | SPA servie par le backend, build embarqué |
| Authentification | **Aucune**, écoute `127.0.0.2` | 2026-10-20 | Boucle locale uniquement ; token à concevoir avant toute exposition réseau |
| Fournisseurs Git | **GitHub + GitLab** | 2026-10-20 | Deux collecteurs, deux modèles d'identité, pas de Bitbucket en MVP |
| Dépôts | **Multi-dépôts par projet** | 2026-10-20 | Table `repositories`, métriques par dépôt puis agrégées |
| Agents | **Préparation/suivi + lancement depuis l'interface** | 2026-10-20 | Runner avec modèles de commande, budget, timeout, annulation, audit |
| Rétention | **12 mois par défaut, configurable** | 2026-10-20 | Purge journalisée, audit conservable plus longtemps sur décision |

### 17.1 Points restant à préciser

| Sujet | Pourquoi | Échéance proposée |
|---|---|---|
| Change OpenSpec `console-sdlc` | Le cahier des charges doit alimenter un change gelable (proposal, deltas, tasks) | Avant le gate `spec_freeze` |
| ~~Validation humaine du brief et des exigences NF~~ | **Fait le 2026-10-20** — voir §17.2 | — |
| Token local et politique d'exposition LAN | L'absence d'auth est acceptable en boucle locale seulement | Avant toute utilisation réseau |
| Fixtures GitHub/GitLab/CI | La recette ne doit pas dépendre du réseau | Lot L1 |
| Corpus de dépôts étiquetés | Mesurer les ≥ 80 % de détection de processus | Lot L4 |
| Script de référence des métriques d'équipe | Rendre l'écart ≤ 2 % opposable | Lot L4 |
| Politique d'ancrage de l'audit | 12 mois par défaut, purge d'audit explicite | Lot L0/L7 |
| Trousseau OS (Windows/WSL) | La matrice de compatibilité doit être testée | Lot L0 |
| PostgreSQL | SQLite est le choix MVP ; la conception doit rester portable | Après validation du MVP |
| Bitbucket / Azure DevOps | Non retenus en v1 | Sur demande |
| Signature des skills et provenance | Sécurité de la chaîne d'approvisionnement agentique | Lot ultérieur |
| Export comptable / facturation | Hors périmètre | Plus tard |

### 17.2 Validation

| Élément | Validé par | Date | Preuve |
|---|---|---|---|
| Brief | Utilisateur (responsable humain) | 2026-10-20 | Pied de `brief.md` |
| Exigences NF | Utilisateur (responsable humain) | 2026-10-20 | Pied de `exigences-nf.md` |
| Revue contradictoire 1 | GLM-5.3-Flash Free | 2026-10-20 | `revue-cahier-des-charges-web.md` |
| Revue contradictoire 2 | GLM-5.3-Flash Free | 2026-10-20 | `revue-cahier-des-charges-web-2.md` |
| N-20 (validation humaine) | Résolu par la validation ci-dessus | 2026-10-20 | Cette table |
| N-22 (coût vs budget) | Corrigé | 2026-10-20 | §14, scénario « Lancement d'agent » |

## 18. Références

- Maquette validée : [`docs/mockup-framework.html`](../mockup-framework.html)
- Brief : [`docs/00-cadrage/brief.md`](brief.md)
- Exigences NF : [`docs/00-cadrage/exigences-nf.md`](exigences-nf.md)
- Workflow de référence : [`docs/conception/workflow-sdlc.md`](../conception/workflow-sdlc.md)
- Tâches du framework : [`docs/conception/tasks.md`](../conception/tasks.md)
- ADR : [`docs/architecture/adr/README.md`](../architecture/adr/README.md)
- Analyse de menaces : [`docs/architecture/menaces.md`](../architecture/menaces.md)
- Gabarit brief : [`templates/docs/brief.md`](../../templates/docs/brief.md)
- Gabarit exigences NF : [`templates/docs/exigences-nf.md`](../../templates/docs/exigences-nf.md)
- Gabarit menaces : [`templates/docs/menaces.md`](../../templates/docs/menaces.md)
- Contrat de passation : [`templates/handoff/report.schema.json`](../../templates/handoff/report.schema.json)
- Revue contradictoire itération 1 : [`revue-cahier-des-charges-web.md`](revue-cahier-des-charges-web.md)
- Revue contradictoire itération 2 : [`revue-cahier-des-charges-web-2.md`](revue-cahier-des-charges-web-2.md)

---

*Cahier des charges proposé par : orchestrateur — Date : 2026-10-20 — Brief et exigences NF validés par l'utilisateur — Prêt pour le change OpenSpec.*
