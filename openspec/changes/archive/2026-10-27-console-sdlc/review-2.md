# Revue contradictoire — Change OpenSpec `console-sdlc` (itération 2)

> Avis de contestation établi selon `.agents/skills/spec-review/SKILL.md` et
> `.agents/skills/spec-review/references/grille-contestation.md`, avant le gate `spec_freeze`.
> La revue d'itération 1 reste consultable dans `review-1.md` (1 bloquante, 7 majeures,
> 18 mineures). La présente revue vérifie la correction de B-1 et de M-1 à M-7, le sort des
> 18 mineures, puis applique la grille complète aux problèmes résiduels.
> Documents de contrôle lus : `proposal.md`, `design.md`, `tasks.md`, les cinq deltas de spec
> (`console-core`, `console-quality`, `console-review`, `console-team-process`, `console-ops`),
> `docs/00-cadrage/cahier-des-charges-web.md`, `brief.md`, `exigences-nf.md`,
> `docs/architecture/adr/README.md` et ADR-001 à ADR-006, `docs/architecture/menaces.md`,
> `review-1.md`, skill `spec-review` et sa grille.
> Vérification exécutée : `openspec validate console-sdlc --strict` → « Change 'console-sdlc' is valid »
> (exécuté par le contradicteur le 2026-10-20). Le change compte désormais 56 exigences
> (14 console-core, 10 console-quality, 13 console-review, 8 console-team-process,
> 11 console-ops) et 91 scénarios WHEN/THEN, et 65 tâches à ID unique.

## 0. Identification

| Champ | Valeur |
|---|---|
| Change | `console-sdlc` |
| Auteur | Orchestrateur (session pilote du dépôt) |
| Contradicteur (≠ auteur) | GLM-5.3-Flash Free (agent OpenCode, lecture seule), itération 2 |
| Date | 2026-10-20 |

Conventions : `B-N` = bloquante, `M-N` = majeure, `m-N` = mineure. L'identifiant B-1
et M-1 à M-7 reprennent la numérotation de `review-1.md` ; les problèmes résiduels nouveaux de
la section C reprennent une numérotation `m-N` continue à partir de 19.

## A. Vérification de B-1 et de M-1 à M-7

| Constat revue 1 | Statut | Preuve |
|---|---|---|
| **B-1** — Vue d'ensemble sans exigence, scénario ni tâche (REQ-OV-01 à 04) | **résolu** | Exigence « Vue d'ensemble » (`console-core`, lignes 139–159) : les six KPI (avancement, gates, couverture, vulnérabilités, coût IA, délai spec→prod) avec « Chaque KPI SHALL indiquer sa source et afficher « non mesuré » », les décisions en attente triées par blocage, le pipeline alimenté par `state.json` et les gates, les risques ouverts par catégorie. Trois scénarios : « KPI avec source » (un KPI sans donnée affiche « non mesuré »), « Décisions en attente » (lien vers preuve ou fiche), « Pipeline et risques ». Tâche 3.7 « Vue d'ensemble : KPI avec source et « non mesuré », décisions en attente, pipeline, risques par catégorie » (dépendances 3.1, 4.1). Les quatre MUST REQ-OV-01 à 04 sont désormais opposables. |
| **M-1** — Features/tâches côté affichage (REQ-FEA-01, 02, 05) | **résolu** | Exigence « Liste et détail des features et tâches » (`console-core`, lignes 161–180) : listage avec phase, tâches, couverture, gate, exécutant et relecteur ; détail de tâche avec fichiers, critères, statut et rapport ; signalement des incohérences `tasks.md` ↔ `state.json`. Trois scénarios : « Liste filtrée » (phase et gate), « Détail d'une tâche » (renvoi au rapport), « Incohérence de suivi » (tâche cochée dans `tasks.md` absente de `state.json`). Tâche 3.8 qui référence explicitement les incohérences `tasks.md` ↔ `state.json`. |
| **M-2** — Escalade après `max_iterations` (REQ-REV-06 ; CdC §14 ; workflow §12) | **résolu** | Exigence « Escalade après rejets » (`console-review`, lignes 133–142) : la tâche passe en `blocked`, l'humain est notifié, les itérations restent conservées dans l'audit. Scénario « Trois rejets ». Tâche 6.10 « Escalade après `max_iterations` : tâche `blocked`, notification humaine, itérations conservées ». |
| **M-3** — Vue Agents IA sans exigence (REQ-AGT-01, 03) | **résolu** | Exigence « Journal des runs et indépendance » (`console-review`, lignes 144–159) : liste des runs (agent, rôle, modèle, tâche, statut, durée, coût, tokens) avec filtres, taux de revues dont le modèle diffère de celui de l'auteur, décision humaine exigée au-delà du seuil configuré (défaut 10 %). Scénarios « Journal filtrable » et « Seuil d'indépendance dépassé ». Tâche 6.11 (journal des runs + taux d'indépendance, seuil 10 %) et vue 7.3 « Vue Agents IA ». Conforme à REQ-AGT-03 (seuil configuré, défaut 10 %). |
| **M-4** — Path traversal (NF §2 ; menaces.md Ingestion Élevé) | **résolu** | Exigence « Chemins d'ingestion confinés » (`console-core`, lignes 193–203) : résolution en absolu, refus de tout chemin hors périmètre et de tout segment `..`, interdiction de lire un fichier de secrets. Scénario « Path traversal » (refus explicite, aucun fichier lu, tentative auditée). Tâche 1.7 « Confiner les chemins d'ingestion : résolution absolue, refus de `..` et de tout chemin hors périmètre, test de path traversal ». Design.md § Interface (« Chemins d'ingestion résolus en absolu, refus de `..` et de tout chemin hors périmètre »). |
| **M-5** — Redaction étendue (PRE-19 ; REQ-SEC-05, REQ-AGT-05 ; NF §2) | **résolu** | Exigence « Redaction étendue » (`console-ops`, lignes 130–140) : jamais de secret ni de prompt dans un export JSON/CSV, un champ agrégé (`stats_json`) ou un journal de run ; test du faux jeton couvrant les trois destinations. Scénario « Faux jeton dans un export » (masqué export, `stats_json` et journal ; test de non-régression). Tâche 6.12. Alignée sur NF §2 (« Test avec faux jeton sur logs, exports et `stats_json` »). |
| **M-6** — Pagination serveur (REQ-GEN-05 ; CdC §9.2) | **résolu** | Exigence « Pagination serveur » (`console-core`, lignes 182–191) : pagination côté serveur avec `limit`, `offset` et `total`, 50 lignes par défaut. Scénario « Liste paginée » (120 éléments → page de 50, `total` 120, `offset=50`). Tâche 7.6 et critère du lot 3 (« pagination 50 »). Design.md § Interface. |
| **M-7** — Flux affiché avec ses gates (REQ-PRO-03) | **résolu** | Exigence « Flux de processus avec gates » (`console-team-process`, lignes 47–56) : feature → MR → revue → main, release → tag → préprod → recette → go/no-go → prod, hotfix → tests/sécurité → prod. Scénario « Flux affiché avec ses gates » (gates recette et go/no-go positionnés sur le flux, chaque gate cliquable vers sa preuve). Tâche 5.8. |

**Bilan A : B-1 et M-1 à M-7 = 7/7 résolus**, exigence + scénarios + tâche + (le cas échéant)
design et critère de lot pour chacun. Aucune correction ne se limite à un effet de bord.

## B. Sort des 18 mineures de la revue 1

| m-N (revue 1) | Objet | Statut | Preuve |
|---|---|---|---|
| m-1 | Validation `Host`/`Origin` sans scénario | **résolu** | Scénario « DNS rebinding » (`console-ops`, « Sécurité locale ») : écriture avec `Host` ou `Origin` externe refusée ; tâche 1.5. |
| m-2 | Limite de concurrence sans scénario | **résolu** | Exigence « Concurrence et reprise après crash » (`console-review`) + scénario « Troisième run simultané » (run excédentaire en `queued`, démarre au slot libéré) ; tâche 6.5. |
| m-3 | Retrait de dépôt sans scénario | **résolu** | Scénario « Retrait d'un dépôt » (`console-core`, « Projet multi-dépôts ») : `retired_at` par défaut, absent des agrégats, historique consultable, dépôt principal réélu, suppression définitive confirmée et auditée ; tâches 2.1, 2.7. Conforme à PRE-10/PRE-11 et ADR-004. |
| m-4 | Statut terminal du run au plafond de budget | **résolu** | Scénario « Plafond atteint » tranché : statut `failed` avec cause `budget_exceeded`, coût réel affiché, dépassement signalé (`console-review`, « Budget et coût d'un run »). Cohérent avec PRE-17 et les causes du scénario « Crash ou timeout » (`server_restart`). |
| m-5 | Réversibilité de la fusion de personnes | **résolu** | Scénario « Fusion auditée » reformulé : `superseded_by_person_id` renseigné, événement d'audit, « une opération inverse auditée peut rétablir les rattachements d'origine » (`console-core`, « Identités canoniques »). Conforme à REQ-PRE-03. |
| m-6 | Portée des indexes d'identité (N-05 de la revue 2 du CdC) | **partiellement résolu** | design.md « Modèle multi-dépôts » fixe désormais « unicité de l'email **par projet** » et « `display_name` non unique avec fusion manuelle auditée » (aligné sur le modèle §8 du CdC : `(project_id, email)` unique, `(project_id, display_name)` non unique). Il manque toujours le scénario proposé : deux projets partageant un même auteur ou des homonymes dans un même projet. Voir m-21 (section C). |
| m-7 | Dégradation gracieuse au-delà des volumes cibles | **résolu** | Exigence « Dégradation gracieuse » (`console-core`, lignes 205–213) + scénario « Dépôt volumineux » (avertissement « dépôt volumineux, mesures prêtes », listes paginées) ; tâche 7.6. Alignée NF §1. |
| m-8 | Persistance du filtre de dépôt dans l'URL | **résolu** | Scénario « Création d'un projet à deux dépôts » : « le choix de dépôt est conservé dans l'URL et partageable » (`console-core`). Couvre REQ-SOC-13 et REQ-GEN-02. |
| m-9 | Seuil de régression de performance divergent | **résolu** | Scénario « Régression observée » tranché : `fail` si la régression dépasse le seuil configuré, `warn` en dessous, preuve `reports/perf/*.json` liée. La SHALL (« une régression observée SHALL bloquer ») n'a pas été reformulée ; voir m-26 (section C). |
| m-10 | Reprise après crash du serveur | **résolu** | Exigence « Concurrence et reprise après crash » : au démarrage, tout run orphelin `queued`/`running` passe à un état terminal explicite avec cause (scénario « Redémarrage après crash » : `failed` / `server_restart`, ingestion partielle rejouable sans doublon). |
| m-11 | CSP absente des deltas | **résolu** | Exigence « En-têtes de sécurité et CSP » (`console-ops`, lignes 142–150) + scénario « CSP active » ; mention « CSP vérifiée en revue » (tâche 6.12). Cover menaces.md (UI React, XSS Élevé) et CdC §10. |
| m-12 | A11y incomplète (contraste, équivalents textuels, `caption`, reduced-motion) | **résolu** | Exigence « Accessibilité et navigation » étendue : contraste AA des thèmes clair et sombre, « un équivalent textuel aux graphiques, des `caption` aux tableaux et `prefers-reduced-motion` » ; scénario « Équivalent textuel d'un graphique » ; tâche 8.1 citant exactement ces quatre points. Alignée NF §3. |
| m-13 | Cibles NF de performance incomplètes dans 8.2 | **résolu** | Tâche 8.2 complète : vue d'ensemble < 1,5 s, multi-dépôts < 2 s, listes < 500 ms, ingestion 10 k commits < 60 s, démarrage < 2 s, mémoire < 512 Mo — les six cibles de NF §1. |
| m-14 | Joignabilité WSL2 (PRE-21) | **partiellement résolu** | La tâche 8.6 porte désormais « solution WSL2 (mode miroir ou navigateur dans WSL) », conformément à NF §6 et ADR-003. En revanche, la tâche 1.6 cite la matrice CI « macOS/Linux/Windows-WSL » sans item explicite de **test de joignabilité depuis le navigateur de l'hôte Windows** (NAT vs miroir) demandé par la revue 1. La moitié « documenter » est faite, la moitié « tester » reste implicite dans 1.6. |
| m-15 | Maintenance CI de la Console elle-même | **résolu** | Tâche 8.8 : câblage de `scripts/ci.sh` pour `apps/console` (lint, typecheck, tests, couverture ≥ 80 %, SAST, dépendances, secrets, build). Alignée NF §7. |
| m-16 | SHOULD/COULD silencieux non déclarés | **résolu** | `proposal.md` § « Hors périmètre MVP » déclare explicitement REQ-SOC-08, REQ-GEN-01, REQ-GAT-10, REQ-EQ-01, REQ-GEN-03, REQ-EQ-08, REQ-CFG-04 et REQ-EQ-06 — soit les huit identifiés par la revue 1 (l'exhaustivité de la liste est reprise en m-19, section C). |
| m-17 | Critères d'acceptation absents des tâches | **résolu** | `tasks.md` ajoute la section « Critères d'acceptation par lot » avec un tableau couvrant les 8 lots, reprenant les contrôles associés (bind 127.0.0.2, path traversal refusé, pagination 50, `not_run` par tier, corpus ≥ 80 %…). Solution au niveau lot, comme proposé. |
| m-18 | Dépendance de 8.5 erronée | **résolu** | Tâche 8.5 dépend désormais de `[1.3, 2.3, 8.4]` (base, file d'ingestion, sauvegarde vérifiée) — conforme à PRE-15 et ADR-006, et sans lien parasite avec 4.8/4.9. |

**Bilan B : 16/18 résolues, 2/18 partiellement résolues (m-6, m-14), 0 non résolue.**
Les deux résiduelles sont signalées à nouveau bas section C (m-21, m-22) avec la portion
exacte qui reste à corriger.

## C. Problèmes résiduels (nouvelle grille, itération 2)

Constats nouveaux depuis la revue 1, ou restes vérifiables des constats partiels de la
section B. Chaque constat porte référence, gravité et proposition.

### C.1 Scénarios manquants

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| La liste « Hors périmètre MVP » du proposal n'est **pas exhaustive** : d'autres SHOULD/COULD du CdC restent sans exigence, scénario, tâche **ni déclaration de périmètre** — REQ-DEP-05 (afficher la procédure de rollback), REQ-OV-05 (activité récente), REQ-OV-06 (résumé équipe/processus), REQ-PRO-04 (branches actives), REQ-PRO-05 (cycle time, taille de MR, taux de hotfix). Le problème m-16 était porté sur les huit premiers identifiants ; la règle voulue par la revue 1 (« toute exigence hors change doit être déclarée ») n'est satisfaite que pour ces huit-là | REQ-DEP-05, REQ-OV-05, REQ-OV-06, REQ-PRO-04, REQ-PRO-05 ; `proposal.md` § Hors périmètre MVP | mineure (m-19) | Étendre la liste « Hors périmètre MVP » à ces cinq identifiants (ou les couvrir : c'est le choix de l'auteur, mais il doit être explicite). |
| La **matrice de traçabilité** (REQ-FEA-03, SHOULD) a une tâche (3.3) mais **aucune exigence de delta ni scénario** : une fonctionnalité planifiée sans critère opposable, à l'inverse du schéma suivi partout ailleurs dans le change | REQ-FEA-03 ; `tasks.md` 3.3 ; design.md (aucune trace) | mineure (m-20) | Ajouter un scénario court à « Liste et détail des features et tâches » (`console-core`) : une exigence sans test est signalée dans la matrice. |
| L'**escalade après timeout de tâche** (`task_timeout_min` de `sdlc.config.yaml`) n'est pas couverte : l'exigence « Escalade après rejets » ne porte que `max_iterations`, alors que le workflow SDLC (§ 12) escalade aussi après un timeout de tâche | `console-review` « Escalade après rejets » ; `.sdlc/workflow-sdlc.md` § 12 | mineure (m-25) | Étendre l'exigence (ou son scénario) : un dépassement de `task_timeout_min` conduit au même état `blocked` avec notification. |

### C.2 Cas limites

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| (Reste de m-6) Deux projets partageant le même auteur, ou deux personnes distinctes de même nom dans un projet, restent **sans scénario** : la règle d'unicité « par projet » est fixée dans design.md mais rien ne la vérifie | design.md « Modèle multi-dépôts » ; REQ-PRE-01 ; `console-core` « Identités canoniques » | mineure (m-21) | Ajouter un scénario : deux projets dont un même email → deux personnes distinctes (une par projet), aucune fusion automatique inter-projets. |
| Le scénario « Liste paginée » teste 120 éléments (3 pages) mais **aucune borne haute** : le comportement sur la dernière page partielle (70 éléments, 20 dans la dernière page) ou `offset ≥ total` liste fermée n'est pas spécifié | `console-core` « Pagination serveur » ; REQ-GEN-05 | mineure (m-27) | Compléter le scénario : dernière page partielle renvoie `total` inchangé et les seuls éléments restants ; `offset ≥ total` renvoie une liste vide sans erreur. |
| Le scénario « Seuil d'indépendance dépassé » suppose un seuil dépassé, mais rien ne définit le comportement **exactement au seuil** (10 % atteint mais non dépassé) ni la fenêtre de mesure (depuis quand, quel périmètre : projet, dépôt, global) | `console-review` « Journal des runs et indépendance » ; REQ-AGT-03 | mineure (m-28) | Fixer : « au-delà du seuil » déclenche, « au seuil » non ; la fenêtre de mesure est la durée de rétention courante du projet, affichée avec le taux. |

### C.3 Gestion des erreurs

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Aucun nouveau constat. Les erreurs d'ingestion (quota, réseau, jeton), de purge (`purge_busy`, `backup_too_old`), de schéma, de démarrage (chaîne altérée, schéma plus récent), de préflight et de budget sont couvertes par scénarios depuis la revue 1 | `console-core`, `console-ops`, `console-review` | conforme | — |

### C.4 Sécurité

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Le **paquet aveugle** est un artefact téléchargeable contenant le diff et les preuves, mais l'exigence « Redaction étendue » ne couvre que « un export JSON/CSV, un champ agrégé (`stats_json`) ou un journal de run » : un secret présent dans une preuve ou dans le diff n'est pas couvert par le test du faux jeton pour cette destination | `console-review` « Paquet de revue aveugle » ; `console-ops` « Redaction étendue » ; NF §2 ; menaces.md (Ingestion — fuite de jeton, Élevé) | mineure (m-29) | Étendre « Redaction étendue » (ou un scénario du paquet aveugle) : le paquet de revue subit la redaction du faux jeton avant téléchargement. |
| La validation porte sur `Host`/`Origin` mais **`Referer`** — cité par ADR-003 (« Refus des `Origin`/`Referer` externes ») et NF §2 — n'apparaît ni dans la SHALL « Sécurité locale » ni dans le scénario « DNS rebinding » | ADR-003 ; exigences-nf.md §2 ; `console-ops` « Sécurité locale » | mineure (m-30) | Ajouter `Referer` à la SHALL et au scénario, ou documenter pourquoi il est inutile avec `Host`/`Origin` vérifiés. |

### C.5 Accessibilité (RGAA / WCAG)

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Aucun nouveau constat. Les quatre écarts de la revue 1 (contraste clair/sombre, équivalents textuels, `caption`, `prefers-reduced-motion`) sont couverts par l'exigence étendue et la tâche 8.1 | `console-core` « Accessibilité et navigation » ; `tasks.md` 8.1 ; NF §3 | conforme | — |

### C.6 Cohérence avec les ADR

| Constat | Référence (ADR) | Gravité | Proposition |
|---|---|---|---|
| Aucune contradiction : les ajouts (Vue d'ensemble, pagination, chemins confinés, redaction, concurrence/reprise, journal des runs, flux avec gates, dégradation gracieuse, CSP) restent dans les décisions ADR-001 à ADR-006 — la concurrence et la reprise alignées sur ADR-005 (statuts fermés, limite de concurrence), le retrait de dépôt et la fusion sur ADR-004, la redaction et la CSP sur ADR-003/menaces.md, le re-calcul des gates sur l'empreinte de config existante | ADR-001 à ADR-006 ; design.md ; les cinq deltas | conforme | — |
| Les ajouts n'introduisent **ni lock-in IDE, ni lock-in agent, ni SaaS** : le journal des runs liste agents et modèles sans privilégier un fournisseur, la détection traverse GitHub et GitLab, aucune fonction ne dépend d'un outil propriétaire (le corpus et les fixtures restent hors réseau) | ADR-001 (pas de lock-in IDE), ADR-004, ADR-005 ; CdC §5 principe 4 | conforme | — |

### C.7 Cohérence avec les exigences non fonctionnelles

| Constat | Référence (exigence NF) | Gravité | Proposition |
|---|---|---|---|
| (Reste de m-14) Le **test de joignabilité WSL2** depuis l'hôte Windows n'a pas d'item explicite dans la tâche 1.6 ; la solution (8.6) est documentée mais la vérification promise par PRE-21 (« documenter **et tester** ») n'est rendue opposable qu'à moitié | PRE-21 ; exigences-nf.md §6 ; `tasks.md` 1.6, 8.6 | mineure (m-22) | Ajouter à 1.6 un item « test de joignabilité depuis le navigateur de l'hôte Windows (NAT vs miroir) » dans la matrice CI. |
| Aucun autre écart : les six cibles de performance (8.2), la couverture ≥ 80 % (8.8), la dégradation gracieuse, la redaction sur les trois destinations NF et la CSP sont alignés sur `exigences-nf.md` §1, §2, §3 et §7 | exigences-nf.md §1, §2, §3, §7 | conforme | — |

### C.8 Traçabilité et testabilité

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| **M-8 (nouveauté itération 2)** — La **vue Déploiements** (une des 12 vues promises, « 12 / 12 vues MVP » du brief) est **orpheline à double titre** : (a) aucune tâche ne l'implémente — le lot 7 « Vues restantes » couvre Sécurité, Performance & données, Agents IA, Documentation, Configuration, et aucun lot 3 à 6 ne touche aux déploiements ; (b) **sa source de données est déclarée hors périmètre MVP** : l'exigence « Déploiements et go/no-go » (`console-ops`) exige l'affichage des environnements dev/préprod/prod et de l'historique, REQ-DEP-01 rend la source obligatoire (`deploys.jsonl` ou API CI), mais l'ingestion de `deploys.jsonl` (REQ-SOC-08) figure dans la liste « Hors périmètre MVP » du `proposal.md` et aucune tâche n'ingère les déploiements par une autre voie. En l'état, la vue sera structurellement vide en MVP, la checklist go/no-go ne partira pas d'un inventaire de déploiements, et le **lead time / délai spec→prod** de la Vue d'ensemble (KPI porté par B-1, REQ-DEP-02) perdra sa source « déploiement prod ». La cohérence entre deux MUST (brief 12/12 vues ↔ proposal hors périmètre) est ambiguë et n'est pas tranchée en faveur de l'un ni de l'autre | REQ-DEP-01, REQ-DEP-03, REQ-DEP-04 ; REQ-SOC-08 ; `console-ops` « Déploiements et go/no-go » ; `proposal.md` § Hors périmètre MVP ; `brief.md` § 2 (« 12 / 12 vues MVP ») ; exigences-nf.md §5 (supervision) | **majeure** | Trancher explicitement, au choix de l'auteur : soit (1) inclure l'ingestion minimale de `deploys.jsonl` au MVP (retirer la moitié « deploys.jsonl » de l'exclusion REQ-SOC-08) et ajouter une tâche vue Déploiements (7.x) à côté de la checklist go/no-go ; soit (2) maintenir l'exclusion et déclarer explicitement que REQ-DEP-01/03 passe en v1 avec un état « désactivé » opposable dans la spec — le délai spec→prod de la Vue d'ensemble resterait alors « non mesuré », ce qui reste conforme à B-1 (un KPI sans donnée s'affiche « non mesuré ») mais dégrade un objectif du CdC. La voie 1 est recommandée : coût d'ingestion faible, elle restaure le go/no-go et le lead time. |
| Les **dépendances 3.7 et 3.8 pointent vers 4.1** (moteur de gates, lot 4) : dépendance valide (l'ID existe, pas de cycle, pas de doublon) mais **vers l'avant** dans le document ; toutes les autres dépendances du fichier restent arrière. La Vue d'ensemble et la liste des features dépendent fonctionnellement du moteur — c'est cohérent, mais l'ordonnancement des lots suggère le lot 3 avant le lot 4, ce qui n'est pas exécutable tel quel | `tasks.md` 3.7 `[3.1, 4.1]`, 3.8 `[3.1, 4.1]`, 4.1 ; grille-contestation (ordre et validité des dépendances) | mineure (m-23) | Déplacer 3.7 et 3.8 dans le lot 4 (ils dépendent du moteur de gates), ou ajouter en marge de « Critères d'acceptation par lot » la note d'ordonnancement « 4.1 doit précéder 3.7/3.8 ». |
| La SHALL « Gate de performance » (« Une régression observée SHALL bloquer ») reste **plus large** que la règle tranchée par le scénario (« `fail` si la régression dépasse le seuil configuré, `warn` en dessous »), reste le reliquat de m-9 ; régression < seuil n'est pas « bloquante » | `console-quality` « Gate de performance » ; REQ-GAT-05 (« une régression observée bloque »), REQ-PER-05 (SHOULD alerte) | mineure (m-26) | Reformuler la SHALL : « une régression observée au-delà du seuil configuré SHALL bloquer ; en dessous du seuil, elle SHALL alerter ». |
| Les 65 tâches restent **ordonnées et à ID unique** (vérifié : aucun doublon, aucune autoréférence — 6.9 dépend de `[6.3, 6.5]`), les critères d'acceptation par lot sont cohérents avec les ajouts (path traversal au lot 1, pagination 50 au lot 3, Vue d'ensemble citée au lot 3) ; les 8 nouvelles tâches (1.7, 3.7, 3.8, 5.8, 6.10, 6.11, 6.12, 7.6) sont articulées au reste sans redondance | `tasks.md` ; grille-contestation | conforme | — |

### C.9 Impacts recette, déploiement, exploitation

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Aucun nouveau constat. Les fixtures hors réseau (2.5), la matrice CI (1.6), la sauvegarde/restauration (8.4), la purge corrigée (8.5), la recette (8.7) et la CI de la Console (8.8) restent couverts ; les ajouts de cette itération n'introduisent aucun changement de cible de déploiement ni de runbook non porté par une tâche | `tasks.md` ; CdC §9.3 | conforme | — |

---

## Verdict

- Contestations bloquantes : **0** — B-1 est résolue (exigence « Vue d'ensemble » + 3 scénarios + tâche 3.7).
- Contestations majeures : **1** — M-1 à M-7 toutes résolues (7/7) ; une **nouvelle** majeure (M-8) : la vue Déploiements sans tâche et sans source de données en MVP (`deploys.jsonl` déclaré hors périmètre), qui laisse la checklist go/no-go et le lead time sans fondement de données.
- Contestations mineures : **18 de la revue 1 — 16 résolues, 2 partiellement résolues** (m-6, m-14 ; suivies en m-21 et m-22). **11 mineures dans cette revue** : 2 suivis des partiellement résolues (m-21 scénario inter-projets, m-22 test WSL2 dans 1.6) et **9 nouvelles** — m-19 liste hors périmètre non exhaustive, m-20 traçabilité sans exigence de delta, m-23 dépendances 3.7/3.8 vers 4.1, m-25 escalade sur timeout, m-26 reformulation SHALL perf, m-27 bornes de pagination, m-28 seuil d'indépendance (au seuil vs au-delà, fenêtre), m-29 redaction du paquet aveugle, m-30 `Referer`.

**Verdict : non prêt pour spec_freeze** — mais de peu et pour une seule raison. Le change a été substantiellement corrigé depuis la revue 1 : la bloquante et les sept majeures sont levées avec exigence, scénarios et tâche à chaque fois, 16 des 18 mineures sont traitées, la validation OpenSpec reste verte et les ajouts ne contredisent aucun ADR ni aucune exigence NF. Ce qui empêche le gel est une **seule incohérence de périmètre** (M-8) entre deux MUST : la vue Déploiements est promise (« 12 / 12 vues MVP ») et spécifiée (exigence `console-ops` avec scénario), mais son unique source de données en MVP et son implémentation sont absentes. Trancher M-8 (voie recommandée : inclure l'ingestion de `deploys.jsonl` au MVP + une tâche 7.x) et traiter les mineures à faible coût d'écriture (m-19 à m-30, aucune ne demande de conception nouvelle), puis re-soumettre : **le change sera alors prêt pour spec_freeze**.

---

*Revue contradictoire proposée par : contradicteur indépendant (GLM-5.3-Flash Free, agent OpenCode, itération 2) — Date : 2026-10-20 — Lecture seule : seul `review.md` a été écrit.*
