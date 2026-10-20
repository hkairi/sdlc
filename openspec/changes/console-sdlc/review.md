# Revue contradictoire — Change OpenSpec `console-sdlc` (itération 3)

> Avis de contestation établi selon `.agents/skills/spec-review/SKILL.md` et
> `.agents/skills/spec-review/references/grille-contestation.md`, avant le gate `spec_freeze`.
> La revue d'itération 2 (`review-2.md`) avait conclu : 1 majeure (M-8) et 11 mineures
> (dont 2 suivis de partiellement résolues). La présente revue vérifie la correction de
> M-8 et des mineures résiduelles, puis applique la grille complète aux problèmes
> résiduels avant le gel.
> Documents de contrôle lus : `proposal.md`, `design.md`, `tasks.md`, les cinq deltas de
> spec (`console-core`, `console-quality`, `console-review`, `console-team-process`,
> `console-ops`), `review-1.md`, `review-2.md`, `docs/00-cadrage/cahier-des-charges-web.md`,
> `brief.md`, `exigences-nf.md`, `docs/architecture/adr/README.md` et ADR-001 à ADR-006,
> `docs/architecture/menaces.md`, `.sdlc/workflow-sdlc.md` (§12), skill `spec-review` et sa grille.
> Vérification exécutée : `openspec validate console-sdlc --strict` → « Change 'console-sdlc'
> is valid » (exécutée par le contradicteur le 2026-10-20). Le change compte désormais
> **57 exigences** (15 console-core, 10 console-quality, 13 console-review,
> 8 console-team-process, 11 console-ops), **98 scénarios** WHEN/THEN et **67 tâches** à ID
> unique (comptages vérifiés par lecture des fichiers).

## 0. Identification

| Champ | Valeur |
|---|---|
| Change | `console-sdlc` |
| Auteur | Orchestrateur (session pilote du dépôt) |
| Contradicteur (≠ auteur) | GLM-5.3-Flash Free (agent OpenCode, lecture seule), itération 3 |
| Date | 2026-10-20 |

Conventions : `B-N` = bloquante, `M-N` = majeure, `m-N` = mineure. La numérotation reprend
celle de `review-2.md` ; les constats nouveaux sont numérotés en continu (M-9 ;
m-31 à m-35).

## A. Vérification de M-8 et des mineures résiduelles de l'itération 2

| Constat (revue 2) | Statut | Preuve |
|---|---|---|
| **M-8** — Vue Déploiements orpheline : sans tâche et sans source ( `deploys.jsonl` hors périmètre) | **résolu** | Quatre preuves, aux quatre niveaux demandés : (1) **périmètre** — `proposal.md` « Hors périmètre MVP » ne mentionne plus REQ-SOC-08 ; l'ingestion des journaux est désormais dans le MVP ; (2) **exigence** — « Ingestion des runs et déploiements » (`console-core`, lignes 54–68) : SHALL d'ingestion de `runs.jsonl` et `deploys.jsonl` (environnement, version, statut, durée, auteur, rollback) ; (3) **scénario** — « Déploiement ingéré » (la vue Déploiements affiche environnement, version et date ; lead time et DORA alimentés) et « Run ingéré » ; (4) **tâches** — 2.8 « Ingérer `runs.jsonl` et `deploys.jsonl` » `[1.3]` et 7.7 « Vue Déploiements : dev/préprod/prod, historique, DORA, checklist go/no-go, rollback » `[2.8]`, dépendance valide et arrière. Cohérent avec REQ-DEP-01 (source `deploys.jsonl`), REQ-DEP-03 (scénario « Historique des déploiements » : rollback visible et daté, CFR recalculé) et REQ-DEP-04. Le lead time spec→prod de la Vue d'ensemble dispose de sa source : plus d'incohérence entre brief (« 12 / 12 vues MVP ») et proposal. Vérification croisée ADR-004/multi-dépôts : rien à signaler. |
| m-6 — scénario identités inter-projets | **résolu** | Scénario « Même email dans deux projets » (`console-core` « Identités canoniques », lignes 87–90) : deux personnes distinctes par projet, aucune collision d'index n'empêche la seconde ingestion. Conforme au choix tranché dans design.md (« unicité de l'email par projet », ADR-004). Remarque de complétude, sans nouveau constat : deux personnes de même nom **dans un même projet** (index `display_name` non unique, fusion manuelle) restent décrites par design.md seul, sans scénario — la règle est tranchée, le cas n'est pas démontré. |
| m-14 — test WSL2 dans 1.6 | **résolu** | Tâche 1.6 : « Ajouter les tests de sécurité locale (bind, Host, Origin, Referer, CSRF, secrets), la matrice CI macOS/Linux/Windows-WSL et le test de joignabilité WSL2 ». PRE-21 (« documenter **et tester** ») est désormais opposable des deux côtés : test en 1.6, solution en 8.6 (mode miroir ou navigateur dans WSL). |
| m-19 — liste hors périmètre exhaustive | **résolu** | `proposal.md` « Hors périmètre MVP » couvre désormais les cinq identifiants manquants : REQ-DEP-05 (procédure de rollback détaillée), REQ-OV-05/06 (activité récente, résumé équipe/processus), REQ-PRO-04/05 (branches actives, cycle time). Toute exigence SHOULD/COULD hors change est déclarée (vérifié contre les tableaux REQ du CdC, lignes 152–364). |
| m-20 — traçabilité | **résolu** | Scénario « Traçabilité » ajouté à « Liste et détail des features et tâches » (`console-core`, lignes 203–206) : scénarios, tests et tâches liés à l'exigence affichée ; « une exigence sans test est signalée ». Répond exactement à REQ-FEA-03 (SHOULD). |
| m-23 — dépendances 3.7/3.8 vers 4.1 | **résolu** | 3.7 dépend de `[3.1]`, 3.8 de `[3.1, 3.2]` : plus de dépendance vers le lot 4. Vérification programmatique des 67 tâches : aucun ID dupliqué, aucune référence à un ID inexistant, aucune dépendance avant (forward), aucune autoréférence. Remark : le KPI « gates » de la Vue d'ensemble s'affichera « non mesuré » tant que le lot 4 n'a pas produit de gate — comportement conforme à la propre SHALL de « Vue d'ensemble » (« un KPI sans donnée affiche non mesuré »), donc acceptable. |
| m-25 — escalade sur timeout | **résolu** | Scénario « Dépassement du temps de tâche » (`console-review` « Escalade après rejets », lignes 144–148) : dépassement de `task_timeout_min` → `blocked`, humain notifié, événement audité. Conforme à `.sdlc/workflow-sdlc.md` §12 (escalade après `max_review_iterations` **ou** `task_timeout_min`). |
| m-26 — SHALL perf plus large que la règle tranchée | **résolu** | SHALL de « Gate de performance » reformulée (`console-quality`, lignes 66–69) : « Une régression observée **au-delà du seuil configuré** SHALL bloquer ; en dessous, elle SHALL alerter. Un signal statique SHALL alerter. » Cohérente avec le scénario « Régression observée » et avec REQ-PER-05. |
| m-27 — bornes de pagination | **partiellement résolu** | Un scénario « Bornes de pagination invalides » a été ajouté (`console-core`, lignes 219–222) : `limit` > 200 ou `offset` négatif → `400` avec les bornes autorisées. Mais la partie non corrigée du constat initial reste ouverte : le comportement de la **dernière page partielle** (70 éléments, 20 restants) et de `offset ≥ total` (liste vide sans erreur) n'est spécifié nulle part. Suivi en m-27 (section B.2). |
| m-28 — seuil d'indépendance : au seuil, fenêtre | **résolu** | SHALL tranchée (`console-review` « Journal des runs et indépendance », lignes 152–155) : « Au seuil configuré (défaut 10 % de revues dégradées, **atteint ou dépassé**), une décision humaine SHALL être exigée », sur une « fenêtre glissante de 30 jours ». Remarque : ce choix est plus strict que REQ-AGT-03 (« au-delà d'un seuil configuré ») et introduit une fenêtre de 30 jours absente du CdC — choix explicite de l'auteur, énoncé dans la SHALL, donc pas d'ambiguïté tranchée en silence ; aucun constat. |
| m-29 — redaction du paquet aveugle | **résolu** | SHALL de « Redaction étendue » étendue (`console-ops`, lignes 137–139) : jamais de secret ni de prompt « dans un export JSON/CSV, un champ agrégé (`stats_json`), un journal de run **ou le paquet de revue**. Le test du faux jeton SHALL couvrir ces **quatre** destinations ». Remarque : le scénario « Faux jeton dans un export » (lignes 141–145) ne démontre que les trois premières destinations ; la quatrième est portée par la SHALL et le test exigé — suffisant pour l'opposabilité. |
| m-30 — `Referer` | **résolu en substance** | Scénario « DNS rebinding » (`console-ops`, lignes 130–133) : « un `Host`, un `Origin` **ou un `Referer`** externe » → refus ; les tests de la tâche 1.6 incluent `Referer`. Remarque : la SHALL « Sécurité locale » (lignes 116–118) cite toujours seulement `Host` et `Origin` ; le comportement est opposable par le scénario et les tests, mais l'énoncé normatif gagnerait à citer `Referer` pour rester aligné mot à mot sur ADR-003 et NF §2 — simple harmonie d'écriture, sans constat. |

**Bilan A : M-8 et les 11 mineures = 12/12 traitées ; 11 résolues, 1 partiellement résolue
(m-27, suivie en section B.2). Aucune correction ne se limite à un effet de bord, aucune
nouvelle contradiction n'a été introduite par ces corrections** (vérifié contre ADR-001 à
ADR-006 : l'ingestion des journaux reste locale et multi-fournisseurs, le scénario
« Même email dans deux projets » applique ADR-004, la redaction à quatre destinations
applique NF §2, la tranchée « atteint ou dépassé » reste dans l'esprit de REQ-AGT-03).

## B. Grille complète (problèmes résiduels, itération 3)

### B.1 Scénarios manquants

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| **M-9** — REQ-DOC-04 (« Marquer les documents générés « ne pas modifier » », **MUST** du CdC) n'est couvert par **aucune SHALL, aucun scénario ni tâche critériée** : la seule trace du change est la mention « documents générés » dans la tâche 7.4, sans critère. `review-1.md` avait tracé « REQ-DOC-01 à 03 » et omis DOC-04 ; l'oubli a survécu aux deux itérations. La règle commune du framework (AGENTS.md §3 : « le HTML est généré et porte la mention ») n'est donc opposable nulle part pour la Console, qui génère précisément le fichier de suivi (3.4) et affiche des documents générés (7.4, vue Documentation) | REQ-DOC-04 ; `console-ops` « Documentation et fraîcheur » (lignes 19–33) ; `tasks.md` 3.4, 3.5, 7.4 ; AGENTS.md §3 | **majeure** | Étendre « Documentation et fraîcheur » : tout document généré (fichier de suivi, rapports de gate, exports) porte une mention visible « fichier généré, ne pas modifier », scénario correspondant ; critère dans la tâche 7.4. |
| REQ-EQ-05 (« Afficher la chaîne de validation auteur → relecteur agent → humain », **SHOULD** du CdC) a une tâche (5.3) mais **aucune exigence de delta ni scénario** — le même schéma que REQ-FEA-03 traité en m-20 | REQ-EQ-05 ; `tasks.md` 5.3 ; `console-team-process` (aucune trace) | mineure (m-31) | Ajouter un scénario à « Métriques d'équipe » : la chaîne de validation (revues agent, approbations humaines) est affichée avec taux, ou déclarer REQ-EQ-05 hors périmètre MVP dans le proposal. |

### B.2 Cas limites

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| (Reste de m-27) Le comportement de la **dernière page partielle** (total non multiple de `limit`) et de **`offset ≥ total`** n'est spécifié nulle part ; le scénario « Bornes de pagination invalides » ne traite que les bornes interdites (`limit` > 200, `offset` négatif) | `console-core` « Pagination serveur » (lignes 208–222) ; REQ-GEN-05 | mineure (m-27) | Compléter le scénario « Liste paginée » : la dernière page renvoie `total` inchangé et les seuls éléments restants ; `offset ≥ total` renvoie une liste vide sans erreur. |
| La journalisation des runs a **deux sources** sans règle de réunion : les runs **ingérés** de `runs.jsonl` (exigence « Ingestion des runs et déploiements », tâche 2.8 — REQ-SOC-08) et les runs **lancés depuis l'interface** (tâches 6.5–6.8, exigences « Préflight », « Cycle de vie », journal REQ-AGT-01/REQ-REV-07). Le SHALL « Journal des runs et indépendance » affiche « la liste des runs » sans dire comment ces deux provenances se combient ; un même run présent dans `runs.jsonl` et exécuté localement pourrait être compté deux fois, faussant la liste filtrable et le taux d'indépendance de la fenêtre 30 jours | `console-core` « Ingestion des runs et déploiements » (lignes 65–68) ; `console-review` « Journal des runs et indépendance » (lignes 150–165) ; REQ-SOC-08, REQ-AGT-01, ADR-005 (journal) | mineure (m-32) | Spécifier la règle : le journal est l'union des deux provenances, identifiées (origine `ingérée` / `lancée`) ; une clé de déduplication est définie ; le taux d'indépendance est calculé sur l'union. |

### B.3 Gestion des erreurs

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Aucun nouveau constat. Les erreurs d'ingestion (quota, réseau, jeton, chemin invalide), de pagination (bornes → 400), de purge (`purge_busy`, `backup_too_old`), de schéma (plus récent refusé), de démarrage (chaîne altérée), de préflight (CLI absente, budget dépassé, commande libre refusée), de budget (`budget_exceeded`) et de reprise après crash (`server_restart`) sont couvertes par des scénarios et inchangées depuis la revue 2 | `console-core`, `console-quality`, `console-ops`, `console-review` | conforme | — |

### B.4 Sécurité

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Deux décisions de durcissement d'**ADR-003** (accepté) ne sont tracées nulle part dans le change : **CORS désactivé** (« le frontend est servi par le même origin ») et **Content-Type JSON obligatoire pour les écritures**. La SHALL « Sécurité locale » vérifie `Host`/`Origin`/CSRF/bind, le scénario « DNS rebinding » inclut désormais `Referer`, mais ni le design (§ « Interface » ou § Architecture), ni la tâche 1.5, ni un scénario ne portent ces deux règles : elles ne sont ni testables ni auditables telles qu'acceptées | ADR-003 § Décision (« CORS désactivé », « Content-Type JSON obligatoire ») ; `console-ops` « Sécurité locale » (lignes 114–133) ; `tasks.md` 1.5 ; design.md § Architecture | mineure (m-33) | Ajouter au SHALL « Sécurité locale » (ou à la tâche 1.5 avec un test) : CORS désactivé et refus d'une écriture sans `Content-Type: application/json`. |
| La redaction à quatre destinations (m-29) et la CSP (m-11) sont désormais opposables ; le path traversal (M-4), la redaction étendue (M-5), l'environnement purgé, la lecture seule, le refus Git en écriture et le « contenu externe = données » restent couverts et inchangés | `console-ops` ; `console-core` « Chemins d'ingestion confinés » ; `console-review` ; menaces.md §2 | conforme | — |

### B.5 Accessibilité (RGAA / WCAG)

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Aucun nouveau constat. Clavier sur les 12 vues, focus visible, `aria-live` sans déplacement du focus, non-couleur seule, contraste AA clair/sombre, équivalents textuels, `caption`, `prefers-reduced-motion` : couverts par l'exigence « Accessibilité et navigation » et la tâche 8.1 (inchangés depuis la revue 2) | `console-core` « Accessibilité et navigation » (lignes 141–158) ; `tasks.md` 8.1 ; NF §3 | conforme | — |

### B.6 Cohérence avec les ADR

| Constat | Référence (ADR) | Gravité | Proposition |
|---|---|---|---|
| ADR-006 fixe la configurabilité de la rétention « **par projet et par table** » ; la SHALL « Rétention et purge » (`console-ops`, ligne 63–64) ne dit que « configurable **par table** » : le change sous-spécifie un ADR accepté (la configurabilité par projet a disparu) | ADR-006 § Décision ; `console-ops` « Rétention et purge » ; `tasks.md` 8.5 | mineure (m-34) | Rétablir « configurable par projet et par table » dans la SHALL, ou corriger ADR-006 si l'auteur a changé d'avis — mais pas de divergence silencieuse entre un ADR accepté et la spec. |
| Aucune autre contradiction : statuts fermés, préflight, concurrence, budget, lecture seule = ADR-005 ; identités par projet, retrait de dépôt, déduplication, type de scénario conforme = ADR-004 ; bind, `Host`/`Origin`/`Referer`, CSRF = ADR-003 (hors m-33) ; React 19/FastAPI/SQLite = ADR-001/002 ; audit exclu de la purge, ancrage, sauvegarde vérifiée = ADR-006 (hors m-34). Aucun lock-in IDE/agent/SaaS introduit : l'ingestion des journaux liste agents et modèles sans privilégier de fournisseur, les collecteurs restent GitHub/GitLab, rien ne dépend d'un outil propriétaire | ADR-001 à ADR-006 ; design.md ; les cinq deltas ; CdC §5 principe 4 | conforme | — |

### B.7 Cohérence avec les exigences non fonctionnelles

| Constats | Référence (exigence NF) | Gravité | Proposition |
|---|---|---|---|
| Aucun nouveau constat. Les six cibles de performance (tâche 8.2), la dégradation gracieuse au-delà des volumes cibles, la redaction des quatre destinations de NF §2, la CSP, le refus `Origin`/`Referer` externes (scénario « DNS rebinding » + tests 1.6), le test de joignabilité WSL2 (1.6) et la solution (8.6), la couverture ≥ 80 % (8.8) sont alignés sur `exigences-nf.md` §1, §2, §3, §6 et §7 | exigences-nf.md | conforme | — |

### B.8 Traçabilité et testabilité

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Les **critères d'acceptation par lot** n'ont pas été mis à jour avec les tâches nouvelles : la ligne du lot 7 (« Sécurité, performance/données, agents, docs et configuration alimentées par des preuves ») ne cite ni la **Vue Déploiements** (7.7) ni la **pagination/dégradation gracieuse** (7.6) ; de plus « pagination 50 » figure aux critères du **lot 3** alors que la tâche qui l'implémente (7.6) est au lot 7 | `tasks.md` § Critères d'acceptation par lot, lignes 99–108 ; 7.6, 7.7 | mineure (m-35) | Compléter la ligne du lot 7 (« Déploiements alimentés par `deploys.jsonl` ; pagination et dégradation gracieuse ») et retirer « pagination 50 » du lot 3 (ou la laisser au lot 3 seulement si 7.6 est ramené au lot 3). |
| Les **67 tâches** restent ordonnées et à ID unique (vérifié programmatiquement : aucun doublon, aucune dépendance vers un ID inexistant, aucune dépendance avant, aucune autoréférence — 7.7 `[2.8]`, 6.9 `[6.3, 6.5]`, 8.5 `[1.3, 2.3, 8.4]`) ; les **12 vues** ont chacune une trace d'implémentation (3.7 Vue d'ensemble, 3.8 Features & tâches, 4.2–4.9 Gates & qualité, 6.1–6.9 Revue indépendante, 7.7 Déploiements, 5.1–5.3 Équipe, 5.4–5.8 Processus, 7.1 Sécurité, 7.2 Performance & données, 7.3 Agents IA, 7.4 Documentation, 7.5 Configuration) ; les **6 décisions du 2026-10-20** restent toutes opposées (React, aucune auth + `127.0.0.2`, GitHub+GitLab, multi-dépôts, agents lancés depuis l'interface, rétention 12 mois) ; l'**ouverture automatique du suivi** reste tracée de bout en bout (exigence + 2 scénarios `console-core`, tâches 3.4–3.6, design `ui.open_suivi_on_ready`) | `tasks.md` ; les cinq deltas ; `proposal.md`, `design.md` | conforme | — |

### B.9 Impacts recette, déploiement, exploitation

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Aucun nouveau constat. Les fixtures hors réseau (2.5), la matrice CI + joignabilité WSL2 (1.6), la sauvegarde/restauration (8.4), la purge (8.5, dépendances corrigées), la recette (8.7), la CI de la Console (8.8) et le CLI `sdlc-console` (1.4) restent couverts ; les ajouts de l'itération 3 (2.8, 7.7, scénarios) n'introduisent ni cible de déploiement ni runbook non portés | `tasks.md` ; CdC §9.3 | conforme | — |

---

## Verdict

- Contestations bloquantes : **0**.
- Contestations majeures : **1** — M-9 : REQ-DOC-04 (MUST, mention « ne pas modifier » sur les documents générés) sans SHALL, scénario ni critère de tâche ; oubliée par les trois itérations de revue (`review-1.md` § 8 tracait « REQ-DOC-01 à 03 »).
- Contestations mineures : **6** — m-27 (restante : dernière page partielle et `offset ≥ total`), m-31 (REQ-EQ-05 sans delta), m-32 (règle d'union/déduplication des deux provenances de runs), m-33 (CORS désactivé et Content-Type JSON d'ADR-003 non tracés), m-34 (configurabilité de rétention « par projet » disparue face à ADR-006), m-35 (critères d'acceptation du lot 7 incomplets).

**Verdict : non prêt pour spec_freeze** — pour une seule raison, de Correction triviale.
La majeure héritée (M-8) et onze des douze mineures sont résolues avec des preuves aux
quatre niveaux (périmètre, exigence, scénario, tâche) ; la validation OpenSpec reste verte,
les 67 tâches sont ordonnées sans doublon ni dépendance invalide, les 12 vues, les
6 décisions du 2026-10-20 et l'ouverture automatique du suivi restent tracées de bout en
bout, et aucune correction n'a introduit de lock-in ni de contradiction ADR/NFR. Ne bloque
plus le gel qu'une exigence MUST du CdC restée sans critère (M-9), à corriger en une
exigence + un scénario + un critère dans 7.4 (une demi-heure d'écriture), avec le traitement
des six
mineures à faible coût d'écriture — dont la seule à conséquence structurelle est m-32 —
puis re-soumettre : **le change sera alors prêt pour spec_freeze**.

---

*Revue contradictoire proposée par : contradicteur indépendant (GLM-5.3-Flash Free, agent
OpenCode, itération 3) — Date : 2026-10-20 — Lecture seule : seul `review.md` a été écrit.*
