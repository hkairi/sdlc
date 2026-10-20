# Revue contradictoire — Change OpenSpec `console-sdlc`

> Avis de contestation établi selon `.agents/skills/spec-review/SKILL.md` et
> `.agents/skills/spec-review/references/grille-contestation.md`, avant le gate `spec_freeze`.
> Documents de contrôle lus : `proposal.md`, `design.md`, `tasks.md`, les cinq deltas de spec
> (`console-core`, `console-quality`, `console-review`, `console-team-process`, `console-ops`),
> `docs/00-cadrage/cahier-des-charges-web.md`, `brief.md`, `exigences-nf.md`,
> `docs/architecture/adr/README.md` et ADR-001 à ADR-006, `docs/architecture/menaces.md`,
> `revue-cahier-des-charges-web.md`, `revue-cahier-des-charges-web-2.md`,
> `docs/conception/workflow-sdlc.md`, `AGENTS.md`, grille de contestation.
> Vérification exécutée : `openspec validate console-sdlc --strict` → « Change 'console-sdlc' is valid ».

## 0. Identification

| Champ | Valeur |
|---|---|
| Change | `console-sdlc` |
| Auteur | Orchestrateur (session pilote du dépôt) |
| Contradicteur (≠ auteur) | GLM-5.3-Flash Free (agent OpenCode, lecture seule) |
| Date | 2026-10-20 |

Conventions de cette revue : `B-N` = bloquante, `M-N` = majeure, `m-N` = mineure.

## A. Complétude du change

| Vérification | Constat |
|---|---|
| `openspec validate console-sdlc --strict` | **Conforme** — passe (exécuté le 2026-10-20). |
| Structure des deltas | **Conforme** — les cinq deltas portent tous `## ADDED Requirements`, `### Requirement:` (45 exigences au total : 9 console-core, 10 console-quality, 10 console-review, 7 console-team-process, 9 console-ops) et `#### Scenario:` WHEN/THEN (+ AND) (71 scénarios au total). |
| Décision « React » | **Conforme** — proposal (`What Changes`), design § Architecture, alignés sur ADR-001. |
| Décision « aucune auth + `127.0.0.2` » | **Conforme** — scénarios « Bind non loopback » et « Requête CSRF absente » (`console-ops`), scénario « Acteur non authentifié » (`console-review`), alignés sur ADR-003. |
| Décision « GitHub + GitLab » | **Conforme** — exigence « Collecteurs GitHub et GitLab » (`console-core`) avec scénarios de normalisation et de quota, alignée sur ADR-004. |
| Décision « multi-dépôts » | **Conforme** — « Projet multi-dépôts », « Agrégation multi-dépôts sans double comptage », « Features et tâches multi-dépôts » ; la formule de `commit_fingerprint` dans design.md (sha256 de sha + email auteur normalisé + date d'auteur UTC) est identique à ADR-004 et à la règle §7.2 du CdC — le residu N-09 de la revue 2 est résolu. |
| Décision « agents préparés/suivis **et lancés depuis l'interface** » | **Conforme** — « Préflight et lancement d'agent », « Cycle de vie et annulation d'un run », « Budget et coût d'un run », « Environnement et lecture seule », « Logs d'agent échappés » (`console-review`), alignées sur ADR-005. |
| Décision « rétention 12 mois configurable » | **Conforme** — « Rétention et purge » (`console-ops`) : audit exclu, ancrage, `purge_busy`, `backup_too_old`, alignée sur ADR-006. |
| Nouvelle exigence « le fichier de suivi s'ouvre dès qu'il est prêt » | **Conforme** — exigence « Fichier de suivi ouvert dès qu'il est prêt » (`console-core`) avec deux scénarios (ouverture automatique ; ouverture désactivée), tâches 3.4 à 3.6, design (`ui.open_suivi_on_ready`). |
| Traçabilité CdC → deltas/tâches | **Partielle** — comptage CdC vérifié : 141 exigences (119 domaines Socle…GEN + 22 REQ-PRE). La majorité des MUST est couverte avec scénarios (voir section 8), mais plusieurs MUST n'ont ni exigence de delta ni tâche : Vue d'ensemble (B-1), features/tâches (M-1), escalade (M-2), vue Agents IA (M-3), path traversal (M-4), redaction étendue (M-5), pagination (M-6), flux avec gates (M-7). |

## 1. Scénarios manquants

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| **B-1** — La **Vue d'ensemble** n'a aucune exigence, aucun scénario et aucune tâche : aucun delta ne porte les KPI avec source et « non mesuré » (REQ-OV-01), les décisions en attente triées par blocage (REQ-OV-02), le pipeline SDLC alimenté par `state.json` et les gates (REQ-OV-03) ni les risques ouverts par catégorie (REQ-OV-04) — quatre MUST. La section 7 de `tasks.md` (« Vues restantes ») ne contient pas d'entrée Vue d'ensemble. La seule trace est un effet de bord (« la vue d'ensemble le signale ») dans « Fraîcheur et états d'erreur », alors que design.md § Goals en fait l'objectif premier (« une vue unique et fiable ») et que le proposal promet les 12 vues alimentées | REQ-OV-01 à REQ-OV-04 ; proposal.md « What Changes » ; design.md § Goals ; tasks.md §7 | **bloquante** | Ajouter une exigence « Vue d'ensemble » (capability `console-core`) : KPI avec source et « non mesuré », décisions en attente avec lien de preuve, pipeline par étape, risques par catégorie ; ajouter la tâche correspondante (7.x). |
| La **Vue Agents IA** (liste des runs — agent, rôle, modèle, tâche, statut, durée, coût, tokens — et taux d'indépendance des revues avec seuil configuré déclenchant la décision humaine) : deux MUST sans exigence de delta ; la tâche 7.3 y pourvoit seule | REQ-AGT-01, REQ-AGT-03 ; REQ-REV-07 | **majeure** | Une exigence « Journal des runs et indépendance » dans `console-review` : liste des runs filtrable avec agent, modèle, statut, durée, coût ; taux d'indépendance affiché ; décision humaine exigée au-delà du seuil configuré (défaut 10 %). |
| L'**escalade** après `max_iterations` (tâche passée en `blocked`, humain notifié, itération conservée dans l'audit) : MUST sans exigence, scénario ni tâche 6.x dans le change | REQ-REV-06 ; CdC §14 scénario « Trois rejets escaladent » ; workflow-sdlc.md §12 | **majeure** | Scénario dans `console-review` : trois rejets → tâche `blocked`, humain notifié, itérations conservées dans l'audit. |
| La **validation du `Host` et le refus des `Origin`/`Referer` externes** : la SHALL de « Sécurité locale » porte la règle mais aucun scénario la vérifie (DNS rebinding), alors que c'est la menace principale hors bind, classée Élevé dans l'analyse de menaces | `console-ops` « Sécurité locale » ; ADR-003 ; menaces.md §2 lignes « API locale — S/DNS rebinding » | **mineure** | Scénario : une écriture avec `Host: evil.example` ou `Origin` externe est refusée explicitement et n'exécute rien. |
| La **limite de concurrence** (REQ-AGT-09 SHOULD : « un troisième run simultané est mis en file ») est présente dans design.md et ADR-005 mais sans scénario | REQ-AGT-09 ; ADR-005 ; design.md § Revue et agents | **mineure** | Scénario : dépassement de `max_concurrency` → run placé en `queued`. |
| Le **retrait d'un dépôt** (archivage `retired_at` par défaut, réélection du dépôt principal, suppression définitive explicite) : réglé au CdC (PRE-10, PRE-11, §7.2) et dans les tâches 2.1/2.7, mais sans scénario au niveau du change — l'engagement d'ADR-004 n'est pas rendu vérifiable | PRE-10, PRE-11 ; ADR-004 « Retrait d'un dépôt » ; tasks.md 2.1, 2.7 | **mineure** | Scénario : retrait du dépôt B → archivé, absent des agrégats, historique conservé, dépôt principal réélu, suppression définitive confirmée et auditée. |
| Le **statut terminal d'un run arrêté au plafond de budget** : le scénario « Plafond atteint » dit « le run est arrêté » sans statut, pendant que le CdC §14 mentionne `failed` (« Un run qui dépasse le budget est arrêté ») et que le scénario « Crash ou timeout » donne `failed` ou `timeout`. Deux documents, verdicts différents ; l'ambiguïté est signalée, pas tranchée | `console-review` « Budget et coût d'un run » (scénario « Plafond atteint ») ; CdC §14 ; PRE-17 | **mineure** | Préciser dans le scénario l'existence d'une règle de statut terminal pour l'arrêt au plafond et la présenter à la décision de l'auteur. |
| La **réversibilité de la fusion de personnes** : le scénario « Fusion auditée » affirme « la fusion est réversible » sans mécanisme (que deviennent les rattachements `person_id` des commits/MR au retour de fusion ?) | `console-core` « Identités canoniques » (scénario « Fusion auditée ») ; PRE-03 ; règle §7.2 | **mineure** | Préciser le mécanisme de dé-fusion (restauration du rattachement vers la personne supplantée, événement d'audit) ou reformuler « réversible » de façon vérifiable. |

## 2. Cas limites

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| La **portée des indexes d'identité** (constat N-05 de la revue 2, toujours ouvert) n'est pas reportée dans le change : design.md ne fixe ni l'unicité de l'email par projet ni le traitement des homonymes. Deux projets partageant un auteur, ou deux personnes distinctes de même nom, restent non spécifiés | N-05 (revue-cahier-des-charges-web-2.md) ; ADR-004 ; design.md « Modèle multi-dépôts » | **mineure** | Reporter dans design.md : unicité de l'email par projet, index non unique sur `display_name` avec fusion manuelle ; un scénario à deux projets partageant un auteur. |
| Le **dépassement des bornes cibles** (effet « dépôt volumineux, mesures prêtes » de NF §1) : les deltas prévoient les états « périmé » et « vide » mais aucune exigence de dégradation gracieuse au-delà des volumes cibles (100 k commits, 5 dépôts) | exigences-nf.md §1 (« Dégradation gracieuse ») ; CdC §3.3 | **mineure** | Une exigence ou un scénario : au-delà des cibles, avertissement visible, pagination, pas de chargement complet. |
| La **persistance du filtre de dépôt dans l'URL** (REQ-SOC-13, MUST) : le scénario « Création d'un projet à deux dépôts » mentionne le filtre mais jamais sa conservation dans l'URL, ni le partage de lien (REQ-GEN-02) | REQ-SOC-13 ; `console-core` « Projet multi-dépôts » (scénario 1) | **mineure** | Ajouter au scénario : « le choix de dépôt est conservé dans l'URL et partageable ». |

## 3. Gestion des erreurs

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Le **seuil de régression de performance** diverge selon les textes : le scénario est « le gate performance est `warn` ou `fail` selon le seuil de régression » à côté d'une SHALL « une régression observée SHALL bloquer » (requête REQ-GAT-05, MUST : « une régression observée bloque ») et de REQ-PER-05 (SHOULD : « alerter »). Un même scénario admet deux verdicts opposés | `console-quality` « Gate de performance » (scénario « Régression observée ») ; REQ-GAT-05, REQ-PER-05 | **mineure** | Fixer la règle unique dans le scénario : régression > seuil configuré → `fail` ; avertissement en dessous → `warn` ; et aligner la SHALL. |
| La **reprise après crash du serveur** pendant un run `running` ou une ingestion partielle n'est spécifiée nulle part (statut des runs après redémarrage, file d'ingestion interrompue, état des abonnements SSE) | PRE-08 (statuts fermés) ; ADR-005 ; `console-core` « Ingestion Git » ; menaces.md (D — API locale) | **mineure** | Une exigence : au démarrage, un run `queued`/`running` orphelin passe à un état terminal explicite avec la cause ; l'ingestion partielle reste rejouable de façon idempotente (déjà garanti par « Ingestion idempotente », à étendre au cas d'interruption). |

## 4. Sécurité

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Le **path traversal** (chemins allowlistés, résolution réelle, refus de `..`) : exigence « Obligatoire » de NF §2, menaces ingestion classées Élevé — totalement absent des cinq deltas **et** des 56 tâches | exigences-nf.md §2 (path traversal) ; menaces.md §2 (Ingestion — T/I, risque Élevé) ; CdC §11 | **majeure** | Une exigence sécurité (dans `console-core` ou `console-ops`) : chemins déclarés résolus en absolu, refus de tout chemin hors projet et de `..`, test dédié ; une tâche aux lots L0/L1. |
| La **redaction étendue** : PRE-19 (exports JSON/CSV, `stats_json`, journaux de runs) et REQ-AGT-05 (jamais de prompt ni de secret dans le journal) sont des MUST du CdC ; le change couvre l'environnement purgé et les logs échappés, mais aucune exigence de delta ne rend la redaction opposable sur les exports et agrégats en base | PRE-19 ; REQ-AGT-05, REQ-SEC-05 ; exigences-nf.md §2 (test faux jeton sur logs, exports, `stats_json`) | **majeure** | Une exigence : aucun secret ni prompt dans tout export, agrégat stocké (`stats_json`) et journal ; le test du faux jeton étendu à ces destinations. |
| La **CSP** (Content-Security-Policy) : menace UI React classée Élevé dans menaces.md et exigée par NF §2 (« Test XSS, CSP ») et CdC §10 ; le change couvre l'échappement (logs, Markdown) mais jamais la CSP elle-même | menaces.md §2 (UI React — I) ; CdC §10 (CSP) ; `console-review` « Logs d'agent échappés » ; `console-ops` « XSS dans un document » | **mineure** | Mentionner la CSP dans une exigence d'interface avec sa vérification en revue. |

## 5. Accessibilité (RGAA / WCAG)

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Les règles d'accessibilité ne sont que partiellement reportées : « Accessibilité et navigation » (`console-core`) couvre clavier, focus visible, SSE en `aria-live` sans déplacement du focus et non-couleur seule. **Restent hors change** : contraste AA des thèmes clair/sombre, équivalent textuel des graphiques, `caption` des tableaux, `prefers-reduced-motion` — tous exigés par NF §3 et censés être vérifiés par l'audit de la tâche 8.1, sans critère opposable dans la spec | exigences-nf.md §3 ; `console-core` « Accessibilité et navigation » ; tasks.md 8.1 | **mineure** | Étendre l'exigence d'accessibilité (ou explicitement le contenu de l'audit 8.1) aux quatre points ci-dessus. |

## 6. Cohérence avec les ADR

| Constat | Référence (ADR) | Gravité | Proposition |
|---|---|---|---|
| Aucune contradiction entre le change et les ADR acceptés, vérifié sur les cinq deltas et design.md : React 19 + TypeScript + Vite, build embarqué servi par FastAPI, Node au build seulement = ADR-001 ; FastAPI/SQLAlchemy 2/Alembic/Pydantic v2, SQLite 3.45+ WAL, un seul écrivain, portabilité PostgreSQL en conception seulement = ADR-002 ; bind `127.0.0.2:8765`, refus de tout bind hors `127.0.0.0/8`, sans auth, `Host`/`Origin`, CSRF, acteur non authentifié mentionné = ADR-003 ; GitHub+GitLab, empreinte et `dedup_group`, personnes canoniques, conjonction des gates multi-dépôts = ADR-004 ; modèles de commande, préflight, groupe de processus, budget échantillonné, environnement purgé, lecture seule = ADR-005 ; 12 mois, audit exclu de la purge automatique, ancrage, sauvegarde globale, chaîne par projet = ADR-006 | ADR-001 à ADR-006 ; design.md § Architecture, § Gates, § Revue et agents, § Audit ; les cinq deltas | conforme | — |

## 7. Cohérence avec les exigences non fonctionnelles

| Constat | Référence (exigence NF) | Gravité | Proposition |
|---|---|---|---|
| La **pagination serveur** (REQ-GEN-05, MUST : « 50 lignes par défaut ») n'apparaît dans aucun delta ni aucune tâche ; les routes du CdC garantissent pourtant la pagination de toutes les réponses | REQ-GEN-05 ; CdC §9.2 (« Toutes les réponses sont paginées ») | **majeure** | Une exigence transversale (capability `console-core`) et une tâche : listes paginées côté serveur, `limit`/`offset`/`total`, 50 par défaut. |
| La **matrice de performance NF** n'est passée qu'en partie : la tâche 8.2 fixe trois cibles (vue d'ensemble < 1,5 s, multi-dépôts < 2 s, listes < 500 ms) mais omet l'ingestion incrémentale (10 k commits < 60 s), le démarrage à froid (< 2 s) et la mémoire (< 512 Mo) | exigences-nf.md §1 ; tasks.md 8.2 | **mineure** | Compléter 8.2 avec les trois cibles restantes et leurs critères NF. |
| La **joignabilité WSL2** (PRE-21, MUST : documenter **et tester**) : la tâche 1.6 cite la matrice CI mais pas explicitement le test de joignabilité depuis le navigateur de l'hôte Windows (NAT vs miroir) ; le guide d'installation (8.6) doit porter la solution, sans critère opposable | PRE-21 ; exigences-nf.md §6 ; tasks.md 1.6, 8.6 | **mineure** | Item explicite dans 1.6 (test de matrice de joignabilité) et dans 8.6 (solution « miroir ou navigateur dans WSL »). |
| La **maintenance de la Console elle-même** (couverture ≥ 80 %, lint/typecheck verts, NF §7) n'est portée par aucune tâche : 1.6 couvre seulement les tests de sécurité et la matrice CI ; `scripts/ci.sh` n'est cité nulle part pour `apps/console` | exigences-nf.md §7 ; tasks.md 1.6 | **mineure** | Une tâche de câblage de `scripts/ci.sh` (lint, typecheck, couverture) pour `apps/console` avec seuil opposable. |

## 8. Traçabilité et testabilité

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| **B-1** (reprise) — la Vue d'ensemble : quatre MUST (REQ-OV-01 à 04) sans exigence de delta ni tâche. Détail en section 1 | REQ-OV-01 à REQ-OV-04 | **bloquante** | Voir section 1. |
| Les **features et tâches côté affichage** : le delta « Features et tâches multi-dépôts » couvre exclusivement la conjonction des gates multi-dépôts. Sans exigence ni scénario : lister les features avec phase, tâches, couverture, gate, exécutant, relecteur (REQ-FEA-01, MUST), ouvrir le détail d'une tâche avec fichiers, critères, statut et renvoi au rapport (REQ-FEA-02, MUST), signaler les incohérences `tasks.md` ↔ `state.json` (REQ-FEA-05, MUST — la tâche 3.2 porte l'ingestion et un mot, aucun critère opposable) | REQ-FEA-01, REQ-FEA-02, REQ-FEA-05 ; `console-core` « Features et tâches multi-dépôts » ; tasks.md 3.1, 3.2 | **majeure** | Une exigence « Liste et détail des features et tâches » : listage filtré par phase et gate, détail de tâche avec renvoi au rapport, incohérences listées. |
| Le **flux affiché avec ses gates** (REQ-PRO-03, MUST : « Afficher le flux avec les gates : feature, release, hotfix, gates ») est absent du delta processus, qui couvre la détection, les signaux, la surcharge, les DORA et le corpus | REQ-PRO-03 ; `console-team-process` « Détection de processus » | **majeure** | Compléter « Détection de processus » ou ajouter une exigence avec un scénario du flux affiché avec ses gates. |
| Les MUST et SHOULD **vérifiés couverts avec scénarios** : gates (REQ-GAT-01 à 09, 11, 12, 13, 14 et PRE-04 portée par design), revue (REQ-REV-01/02/03/04/05/08/09/10/11), équipe (REQ-EQ-01/02/03/07), processus (REQ-PRO-01/02/06/07 et PRE-22), déploiements (REQ-DEP-01/02/04), docs/config (REQ-DOC-01 à 03, REQ-CFG-01 à 03), transverse (REQ-GEN-04, 06, 07, 08, 09 ; GEN-01/02/05 sont signalés hors couverture aux constats m-8, M-6 et m-16), socle (REQ-SOC-01 à 05, 09, 10, 12, 14 à 17, 19), suivi (REQ-OV-07), et REQ-PRE-01 à 03, 05 à 09, 11 à 13, 16 à 19 portées par les deltas ou design.md | §6 et §7 du CdC ; les cinq deltas ; design.md | conforme | — |
| Les point **SHOULD ou COULD sans exigence ni tâche, non déclarés hors périmètre** : ingestion de `runs.jsonl` et `deploys.jsonl` (REQ-SOC-08), recherche globale (REQ-GEN-01), historique des runs de gate avec diff (REQ-GAT-10), option d'inclusion des bots (REQ-EQ-01), exigences export (REQ-GEN-03, REQ-EQ-08, REQ-CFG-04). Le silence de périmètre dans le proposal risque de compter ces SHOULD comme du livrable | REQ-SOC-08, REQ-GEN-01, REQ-GAT-10, REQ-EQ-01, REQ-EQ-06, REQ-GEN-03, REQ-EQ-08, REQ-CFG-04 ; tasks.md | **mineure** | Déclarer explicitement chaque SHOULD non couvert dans `proposal.md` (« What Changes » ou hors périmètre MVP) pour éviter l'ambiguïté. |
| Les **56 tâches** sont ordonnées et portent une dépendance `[x.y]`, couvrant les 8 lots L0–L7 (Socle 6, Projets/ingestion 7, Features/suivi 6, Gates 9, Équipe/processus 7, Revue/agents 9, Vues 5, Finition 7) ; en revanche **aucune tâche ne porte de critère d'acceptation** — l'opposabilité repose entièrement sur les deltas | tasks.md ; grille-contestation.md | **mineure** | Ajouter le critère d'acceptation (ou l'ID REQ du CdC) à chaque tâche, ou au minimum par lot. |

## 9. Impacts recette, déploiement, exploitation

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| La dépendance de 8.5 « Purge 12 mois » est `[4.8, 4.9]` : la purge dépend des dérogations et de l'empreinte de config, pas de la purge elle-même ; et le garde `backup_too_old` (8.4, sauvegarde vérifiée récente) n'est pas listé en dépendance de 8.5, alors que PRE-15 refuse la purge sans lui | tasks.md 8.4, 8.5 ; PRE-15 ; ADR-006 | **mineure** | Corriger : 8.5 dépend de 1.3 (base), 2.3 (file d'ingestion) et 8.4 (sauvegarde vérifiée), pas de 4.8/4.9. |
| Le reste de la chaîne recette/exploitation est couvert : fixtures hors réseau (2.5), matrice CI macOS/Linux/Windows-WSL (1.6), démonstration (8.6), sauvegarde/restauration testées (8.4), recette et matrice de scénarios (8.7), CLI `init`/`serve`/`doctor`/`schema`/`purge --audit`/`process corpus` (1.4, 5.7, 8.4, 8.5), routes Suivi (`/api/projects/{id}/suivi`, `/suivi/status`) et ouverture à la génération (3.4 à 3.6), codes de retour CLI et format d'erreur unique repris du CdC §9.2/§9.3 | tasks.md ; PRE-06, PRE-15, PRE-22, REQ-SOC-21, REQ-GEN-06/09 | conforme | — |

---

## Verdict

- Contestations bloquantes : **1** — Vue d'ensemble sans exigence de spec ni tâche (REQ-OV-01 à 04).
- Contestations majeures : **7** — M-1 features/tâches (REQ-FEA-01/02/05), M-2 escalade (REQ-REV-06), M-3 vue Agents IA (REQ-AGT-01/03), M-4 path traversal (NF §2), M-5 redaction étendue (PRE-19, AGT-05), M-6 pagination (REQ-GEN-05), M-7 flux avec gates (REQ-PRO-03).
- Contestations mineures : **18** — m-1 Host/Origin sans scénario, m-2 concurrence sans scénario, m-3 retrait de dépôt sans scénario, m-4 statut du run au plafond, m-5 réversibilité de fusion, m-6 portée des indexes identités (N-05), m-7 dégradation gracieuse, m-8 persistance du filtre en URL, m-9 seuil de régression perf, m-10 reprise après crash du serveur, m-11 CSP, m-12 a11y (contraste, équivalents textuels, `caption`, reduced-motion), m-13 NF perf incomplètes dans 8.2, m-14 joignabilité WSL2, m-15 maintenance CI de la Console, m-16 SHOULD/COULD silencieux (SOC-08, GEN-01, GAT-10, EQ-01…), m-17 critères d'acceptation absents des tâches, m-18 dépendance 8.5 à corriger.

**Verdict : non prêt pour spec_freeze.** Le socle est solide : validation OpenSpec verte, 45 exigences et 71 scénarios bien structurés, les six décisions du 2026-10-20 toutes couvertes, aucune contradiction avec les ADR acceptés, et l'exigence « le suivi s'ouvre dès qu'il est prêt » traçable de la spec (2 scénarios) au design, aux tâches et aux routes API. Mais la bloquante est incontournable : la Vue d'ensemble, objectif premier annoncé par le design, n'a ni exigence ni tâche ; et quatre des sept majeures sont des MUST du cahier des charges que les deltas ne rendent pas vérifiables. Corriger B-1 et les M-1 à M-7, traiter les mineures à faible coût, puis re-soumettre à la contestation.

---

*Revue contradictoire proposée par : contradicteur indépendant (GLM-5.3-Flash Free, agent OpenCode) — Date : 2026-10-20 — Lecture seule : aucun autre fichier modifié.*
