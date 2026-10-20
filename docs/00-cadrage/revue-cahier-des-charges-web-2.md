# Revue contradictoire itération 2 — Cahier des charges Console SDLC

> Avis de contestation établi selon [`.agents/skills/spec-review/references/grille-contestation.md`](../../.agents/skills/spec-review/references/grille-contestation.md), avant le gate `spec_freeze`.
> Document contesté : [`cahier-des-charges-web.md`](cahier-des-charges-web.md), statut « corrigé — en attente de la revue itération 2 ».
> Documents de contrôle lus : [`revue-cahier-des-charges-web.md`](revue-cahier-des-charges-web.md) (itération 1 : 2 bloquantes, 21 majeures, 23 mineures), [`brief.md`](brief.md), [`exigences-nf.md`](exigences-nf.md), [`../architecture/adr/README.md`](../architecture/adr/README.md) et ADR-001 à ADR-006, [`../architecture/menaces.md`](../architecture/menaces.md), [`../conception/workflow-sdlc.md`](../conception/workflow-sdlc.md), `AGENTS.md`, grille de contestation.
> Rôle : contradicteur indépendant, itération 2 — pas l'auteur du document. Mission : vérifier la correction des constats de l'itération 1, puis chercher de **nouveaux** problèmes, notamment ceux introduits par les corrections.

## 0. Identification

| Champ | Valeur |
|---|---|
| Document | Cahier des charges — Console SDLC (application web locale), version corrigée du 2026-10-20 |
| Auteur | Orchestrateur (session pilote du dépôt) |
| Contradicteur (≠ auteur) | GLM-5.3-Flash Free (agent OpenCode, lecture seule), itération 2 |
| Date | 2026-10-20 |
| Itération précédente | [`revue-cahier-des-charges-web.md`](revue-cahier-des-charges-web.md) |

---

## A. Vérification des constats de l'itération 1

Statuts : **résolu** (correction vérifiable dans la version corrigée), **partiellement résolu** (avancée réelle mais règle ou scénario encore incomplet), **non résolu** (aucun changement vérifiable).

### A.1 Constats bloquants et majeurs (itération 1)

| Constat (revue 1) | Gravité | Statut | Preuve dans la version corrigée | Commentaire |
|---|---|---|---|---|
| Décisions d'architecture tranchées sans ADR | bloquante | résolu | `docs/architecture/adr/README.md` : ADR-001 à ADR-006, tous « accepté 2026-10-20 », couvrant stack frontend (ADR-001), backend/SQLite (ADR-002), local sans auth (ADR-003), GitHub+GitLab / multi-dépôts (ADR-004), runner d'agents (ADR-005), rétention/audit (ADR-006) | L'ampleur couvre les six décisions structurantes demandées ; les ADR documentent contexte, décision, conséquences, alternatives ; la forme du gabarit est respectée |
| `brief.md` et `exigences-nf.md` absents | bloquante | partiellement résolu | [`brief.md`](brief.md) et [`exigences-nf.md`](exigences-nf.md) créés, structurés, cohérents avec le CdC et la revue 1 | Les deux documents portent « Statut : à valider » ; aucune trace de validation humaine (gate « brief validé » de l'étape 1). Voir N-20 |
| Scénario de purge/rétention absent | majeure | résolu | CdC §14 « Rétention et intégrité » (2 scénarios : purge 12 mois hors audit ; purge d'audit avec ancrage) ; REQ-GEN-06, REQ-GEN-09 ; ADR-006 | Les deux voies (purge standard et purge d'audit) ont chacune un scénario vérifiable |
| Retrait d'un dépôt sans scénario | majeure | partiellement résolu | §14 scénario « Le retrait d'un dépôt est explicite » ; API `DELETE /api/projects/{id}/repositories/{repo_id}` ; CLI `sdlc-console project repo remove` (« règle de conservation explicite ») | Le scénario propose « conservation ou suppression », mais ces options ne sont pas définies face à la contrainte `ON DELETE CASCADE` (§8) : « conserver » des commits rattachés à un dépôt supprimé est contradictoire ; la ré-élection du dépôt principal n'est pas traitée. Voir N-23 |
| Aucun scénario d'échec d'ingestion | majeure | résolu | REQ-SOC-17 (MUST : jeton expiré, quota, réseau coupé, reprise) ; §14 scénario « Un quota GitHub interrompt proprement » | Badge « échec » par source, aucune donnée partielle marquée « à jour », reprise sans doublon (REQ-SOC-09) |
| Aucun scénario de run d'agent en échec | majeure | partiellement résolu | §14 scénario « Un run qui dépasse le budget est arrêté » (statut `failed`, coût réel, absence de processus fils survivant) ; REQ-AGT-07, REQ-AGT-12 | Seul le chemin « budget dépassé » a un scénario ; crash du processus et timeout dépassé sans scénario dédié (le champ `status` de `task_runs` reste non énuméré). Voir N-01 et N-15 |
| Ingestion MR GitHub/GitLab sans scénario nommé | majeure | résolu | §14 scénario « Une PR GitHub et une MR GitLab sont normalisées » (modèle commun, valeurs absentes « non mesuré ») ; ADR-004 (contrat commun normalisé) | Conforme au résultat attendu |
| Identité multi-emails non tranchée | majeure | résolu | REQ-SOC-15 (MUST : une personne = plusieurs emails/comptes) ; tables `persons` / `person_identities` (§8) ; ADR-004 (identité canonique, commits rapprochés par email, comptes MR par identité fournisseur) ; §14 scénario « Un contributeur multi-identités est compté une fois » ; règle des risques §16 | Tranché. Les règles fines de rapprochement restent à préciser — N-06 ; le présent constat de l'itération 1 est, lui-même, traité |
| Double comptage multi-dépôts | majeure | résolu | REQ-SOC-14/16 (MUST) ; règle §7 « Périmètre multi-dépôts » (déduplication par empreinte et `dedup_group`) ; ADR-004 ; §14 scénario d'agrégation sans double comptage ; §16 | Tranché et testable ; la définition exacte de l'empreinte reste ambiguë — N-09 |
| Feature/tâche à cheval sur plusieurs dépôts | majeure | résolu | Tables `feature_repositories` / `task_repositories` (§8) ; ADR-004 (« un gate est évalué par dépôt », « la tâche n'est terminée que lorsque tous les dépôts concernés passent ») ; lot L2 « tâches multi-dépôts » | Modèle tranché par ADR accepté ; la règle de passage « tous les dépôts » et la vue Gates par feature n'ont pas d'ID REQ — N-24 |
| Purge concurrente d'une ingestion | majeure | partiellement résolu | ADR-006 : « la purge passe par la même file que l'ingestion », attend les ingestions et gate_runs en cours, journalise les lignes supprimées | La règle est dans l'ADR seulement, ni REQ ni scénario Gherkin : elle n'est pas testable au niveau exigence. Voir N-12 |
| Purge de l'audit casse la chaîne de hachage | majeure | résolu | REQ-GEN-09 (ancrage avant purge d'audit explicite) ; ADR-006 (audit exclu de la purge auto, commande `purge --audit`, ancrage de génération, contrôle d'intégrité après purge) ; §14 scénario « La purge d'audit exige un ancrage » ; §7 « Rétention » | Tranché conformément à la proposition de la revue 1 |
| `not_run` vs tier 2 non tranché | majeure | résolu | REQ-GAT-14 (MUST : `not_run` par contrôle attendu du tier ; SQL/shell tier 2 sans couverture ne fait pas échouer le gate couverture) ; règle §7 « Verdict de gate » (contrôle attendu pour le tier = `fail` si `not_run` ; hors périmètre du tier = `not_applicable`) | Tranché avec la sémantique exacte demandée |
| Annulation sans kill-tree | majeure | résolu | REQ-AGT-12 (MUST : groupe de processus, « Aucun processus fils ne survit à l'annulation ») ; ADR-005 ; menaces (signal au groupe, vérification de terminaison) ; §16 | Mécanisme décrit ; la déclinaison par OS reste à préciser dans le change (cf. négatives ADR-005 « tests multi-OS ») |
| Plafond de coût non garanti | majeure | partiellement résolu | REQ-AGT-13 reformulée (« arrêt au plafond, dépassement éventuel signalé, jamais masqué ») ; règle §7 « Budget agent » ; ADR-005 ; §14 scénario « Un run qui dépasse le budget est arrêté » | **Reliquat** : le premier scénario du §14 (« Lancement d'agent ») conserve la ligne « Et son coût ne dépasse pas le budget » (ligne 639), qui contredit REQ-AGT-13 et l'ADR-005. Voir N-22 |
| CSRF inopérant / DNS rebinding non traité | majeure | résolu | Exigences NF §2 (validation stricte du `Host`, refus des `Origin`/`Referer` externes — Obligatoire) ; ADR-003 (Host, CORS désactivé, Content-Type JSON obligatoire, jeton d'écriture) ; menaces (STRIDE S, mitigation `Host`/`Origin`) ; §10 et §11 | Traitement complet et testable ; le mécanisme CSRF sans session reste à préciser — N-11 |
| Bind LAN non couvert par « `0.0.0.0` refusé » | majeure | résolu | §10 « tout bind hors `127.0.0.0/8` refusé » avec test paramétré (`0.0.0.0`, IP LAN, `::`, hostname) ; ADR-003 ; menaces (E — refus de tout bind hors boucle, message explicite) | Exactement la formulation demandée |
| Environnement des agents héritant des jetons | majeure | résolu | REQ-AGT-11 (MUST : environnement purgé, « un test vérifie qu'aucun jeton n'est hérité ») ; menaces (Runner d'agents — I, environnement purgé, variables minimales) ; ADR-005 ; exigences NF §2 | Tranché avec test dédié |
| Analyse de menaces non finalisée | majeure | résolu | [`docs/architecture/menaces.md`](../architecture/menaces.md) : STRIDE par composant, hypothèses et limites, plan de traitement avec lots | Couvre toutes les mitigations du CdC §11, dont DNS rebinding et environnement agent ; alignée sur les ADR 003/005/006 |
| Seuil « 8 % » fictif recopié | majeure | résolu | REQ-AGT-03 : taux affiché ; au-delà d'un seuil **configuré** (défaut 10 %), décision humaine exigée | Paramétré conformément à la proposition de la revue 1 |
| Tension REQ-REV-01 / REQ-REV-11 / REQ-AGT-03 | majeure | résolu | REQ-REV-01 reformulée (« niveau d'indépendance maximal disponible », niveau affiché) ; REQ-REV-11 (refus du même modèle sauf dérogation humaine audité) ; règle §7 « Indépendance de revue » (dégradée ⇒ dérogation humaine explicite) | Les trois textes disent désormais la même règle |
| Corpus pour l'objectif ≥ 80 % de détection absent | majeure | résolu | CdC livrable 7 (« corpus de dépôts étiquetés ») ; lot L4 ; §17.1 ; §16 « Faux positif de détection » | Livrable et lot nommés ; la procédure de mesure reste succincte — N-28 |
| Recette dépendant d'API distantes sans fixtures | majeure | résolu | REQ-SOC-21 (MUST : tests d'ingestion sans réseau) ; livrable 6 (fixtures GitHub/GitLab/CI avec ETag, pagination, erreurs) ; §9.4 ; lot L1 ; §17.1 | Couvre la proposition de la revue 1 |

### A.2 Constats mineurs de l'itération 1 (vérification ciblée)

| Constat (revue 1) | Gravité | Statut | Preuve dans la version corrigée | Commentaire |
|---|---|---|---|---|
| Quota, ETag, backoff, mode fichier non exigés | mineure | partiellement résolu | REQ-SOC-17 (échecs et reprise, MUST) ; fixtures REQ-SOC-21 ; mais **aucune REQ** sur les requêtes conditionnelles (ETag), le backoff ou le mode fichier : ils restent narratifs (§9.4, livrable 6, §16 risques, menaces) | La protection contre l'échec est exigée, le respect **proactif** du quota non. Voir N-21 |
| État « accès refusé » sans règle | mineure | résolu | §9.1 : état « projet ou dépôt désactivé » à la place de « accès refusé » | Remplacé, sans-auth assumé |
| Préflight d'un run agent absent | mineure | résolu | REQ-AGT-10 (MUST : préflight bloquant — CLI, modèle, dépôt, budget, durée, cause affichée avant confirmation) | Aligné avec ADR-005 |
| XSS via logs SSE non traité | mineure | résolu | REQ-AGT-14 (MUST : logs en texte échappé, test XSS) ; §9.1 ; §10 (CSP) ; menaces (UI React) | Même canal que REQ-DOC-02 |
| Acteur non authentifié non mentionné | mineure | résolu | `decisions.actor_person_id` nullable + `actor_label` (§8) ; menaces (R — « mention explicite poste local non authentifié ») ; exigences NF §2 ; ADR-003 | Limite consignée de façon honnête aux trois endroits |
| SQLite en clair non consigné | mineure | résolu | §11 (ligne « lecture en clair, limite assumée, chiffrement disque OS recommandé ») ; menaces (§2 I + §3 limites) ; exigences NF §4 (« Limite assumée ») | Consigné |
| Trousseau OS non couvert par OS | mineure | résolu | §10 (Keychain macOS, libsecret Linux, Credential Manager Windows/WSL — « Test par OS ») ; exigences NF §6 (WSL « à valider », fallback env = usage de développement) | Matrice honnête ; validation WSL traquée au lot L0 (§17.1) |
| RGPD non traité | mineure | résolu | exigences NF §4 (données traitées, localisation, base légale à confirmer, durées par catégorie, minimisation, droits export/purge, mesures) | La base légale est explicitement « à confirmer, aucune base légale inventée » — conforme au principe 6 du workflow |
| Référence des métriques d'équipe non désignée | mineure | résolu | CdC livrable 8 (script de référence pour recalculer les métriques d'équipe, écart ≤ 2 %) ; lot L4 ; règles §7 « Bus factor » et « Part des commits » normalisées | La référence est un script sur jeu étiqueté + des formules normatives |
| MTTR sans source d'incidents | mineure | résolu | REQ-SOC-18 (ingestion de `docs/incidents/*.md` et `docs/metrics/history.jsonl`) ; règle §7 « MTTR » explicite | Source nommée |
| Preuve de performance sans format | mineure | résolu | REQ-GAT-12 (MUST) ; règle §7 « Preuve de performance » ; §9.4 (JSON `reports/perf/*.json` avec fenêtre, cas, p50/p95/p99, budget, commit, outil) | Format complet |
| Double source des seuils de gates | mineure | résolu | REQ-GAT-13 (MUST : source unique `sdlc.config.yaml`, la base ne fait que cacher avec empreinte de version) | La colonne d'empreinte reste absente du schéma — N-25 |
| Migration de schéma non spécifiée | mineure | résolu | REQ-SOC-19 (MUST : vérification et migration au démarrage, schéma plus récent refusé) ; CLI `schema status` / `schema migrate` (sauvegarde préalable) ; exigences NF §5 ; lot L0 | Comportement complet ; scénario Gherkin absent — N-02 |
| Purge sans confirmation ni garde | mineure | résolu | REQ-GEN-06 (MUST : purge confirmée, précédée d'une sauvegarde vérifiée, journalisée) ; CLI `purge` ; ADR-006 | Le seuil de « sauvegarde récente » n'est pas borné — N-10 |
| `doctor` sans vérification des jetons | mineure | résolu | REQ-SOC-20 (`doctor --with-tokens` : jeton invalide ou quota épuisé signalé avant le premier run) ; CLI §9.3 ; exigences NF §5 | Conforme |
| Âge de sauvegarde non affiché | mineure | résolu | REQ-GEN-07 (MUST : âge de la dernière sauvegarde et de la dernière ingestion, dépassement de cadence signalé) ; §9.1 ; exigences NF §5 | Conforme |
| API incomplète pour des exigences MUST | mineure | résolu | REQ-GEN-08 (chemin UI ou CLI documenté pour dérogation, purge, export, dépôt principal) ; §9.2 ajoute `POST /waivers`, `POST /purge`, `GET /export`, `PUT /repositories/{id}/primary`, `POST /backups/{id}/verify` | Toutes les actions nommées ont une route |

---

## B. Nouvelle grille (itération 2)

Priorité donnée aux **nouveaux problèmes introduits ou laissés par les corrections** : identités et fusions, empreinte et déduplication, multi-dépôts appliqué aux gates, audit chaîné, runner d'agents, gates, API, accessibilité, traçabilité, processus, cohérence brief/NF/ADR/menaces.

### B.1 Scénarios manquants

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| **N-01** — Le scénario d'échec de run par crash ou timeout est absent : seul « budget dépassé » est décrit. REQ-AGT-07 (limiter durée et coût) exige un comportement testable si le processus meurt ou reste bloqué (logs conservés, coût consommé affiché, fils terminés, statut `failed` ou `timeout`) | REQ-AGT-07 ; §14 « Un run qui dépasse le budget est arrêté » | mineure | Ajouter un scénario : étant donné un run avec durée max 20 min, quand le processus plante ou que le timeout expire, alors le statut passe à `failed` avec la cause, les logs sont conservés, le coût réel affiché, les fils terminés |
| **N-02** — REQ-SOC-19 (MUST) : aucun scénario Gherkin de migration et de refus de schéma au démarrage | REQ-SOC-19 ; CLI `schema status` / `schema migrate` ; exigences NF §5 | mineure | Scénario : version de schéma antérieure → sauvegarde puis migration proposée ; version plus récente → démarrage refusé avec message ; version inconnue → refus explicite |
| **N-03** — REQ-AGT-10 (MUST) : le préflight bloquant n'a pas de scénario ; le scénario nominal passe directement au lancement | REQ-AGT-10 ; ADR-005 ; §14 « Un run est lancé… » | mineure | Scénario : CLI absente ou budget supérieur au plafond projet → lancement refusé avant confirmation, cause affichée, aucune ligne `task_runs` créée |
| **N-04** — REQ-REV-11 (MUST) : aucun scénario pour le refus d'un relecteur du même modèle ni pour la dérogation dégradée | REQ-REV-11 ; REQ-REV-01 ; règle §7 « Indépendance de revue » | mineure | Deux scénarios : relecteur du même modèle → l'interface explique le blocage et propose un autre modèle ; dérogation humaine → niveau `dégradée`, décision journalisée |

### B.2 Cas limites

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| **N-05** — `person_identities` porte un index unique sur `(email)` **sans le `project_id`** : deux projets distincts contenant la même adresse email entreront en collision à la deuxième insertion (échec d'ingestion du second projet). Symétriquement, l'index unique `(project_id, display_name)` de `persons` interdit deux homonymes dans un projet, alors que le même nom d'affichage peut correspondre à deux personnes distinctes (cf. N-06) | §8 tables `persons` / `person_identities` ; REQ-SOC-15 | mineure | Statuer la portée des indexes : `(email)` unique **par projet** (les fusions inter-projets restent manuelles), et remplacer l'unicité sur `display_name` par un index non unique + règles de fusion ; scénario à deux projets partageant un auteur |
| **N-06** — Règles de rapprochement et de fusion des personnes non spécifiées : même email avec noms différents, même nom avec emails différents, bots fournisseurs (`dependabot[bot]`, `github-actions[bot]`) à marquer `is_bot`, suppression d'une personne (que devient `commits.person_id` sous FK cascade ?), fusion « tracée dans l'audit » promise par ADR-004 mais sans exigence ni critère correspondant | REQ-SOC-15 ; ADR-004 ; §8 tables `persons`, `person_identities`, `commits` | mineure | Préciser l'algorithme d'appariement exact (email exact → même personne ; conflit de nom → revue manuelle, pas d'appariement silencieux), la détection des bots (motif fournisseur + champ `is_bot` du commit) et interdire l'effacement d'une personne référencée (re-rattachement ou champ `superseded_by_person_id`, fusion tracée dans l'audit) |
| **N-07** — Dérogation sans finding impossible : `waivers.finding_id` n'est pas marqué nullable, alors que des gates échouent sans finding (couverture sous le seuil, `not_run`, tier 3) — aucune voie de dérogation n'est alors définie | §8 table `waivers` ; REQ-GAT-09 ; REQ-SEC-03 | mineure | Rendre `finding_id` nullable et ajouter `gate_run_id` comme cible alternative ; test : dérogation sur un gate `not_run` |
| **N-08** — Cherry-picks et forks non déclarés : l'empreinte et le `dedup_group` ne dédupliquent que les miroirs/forks déclarés ; un fork réel non déclaré ou un cherry-pick laisse le commit compté deux fois dans « tous les dépôts », sans signal dans l'interface | REQ-SOC-16 ; ADR-004 ; règle §7 « Périmètre multi-dépôts » | mineure | Exiger le badge « dédoublonnage appliqué » et l'affichage du dépôt d'origine annoncés dans ADR-004 ; un guide de déclaration du `dedup_group` ; un scénario sur un cherry-pick compté deux fois avec mention explicite |
| **N-09** — Définition exacte de `commit_fingerprint` ambiguë : « sha + auteur + date » (ADR-004) — « auteur » signifie-t-il email ou nom ? « date » la date d'auteur ou la date de commit ? L'empreinte régissant la déduplication MUST (REQ-SOC-14/16), la précision est nécessaire pour éviter deux implémentations divergentes | Règle §7 « Périmètre multi-dépôts » ; ADR-004 ; §8 `commits.commit_fingerprint` | mineure | Écrire normativement, par exemple `sha256(sha + email_auteur + date_auteur_iso8601)`, en une seule formulation identique dans le CdC et l'ADR-004 |
| **N-10** — REQ-GEN-06 exige une « sauvegarde vérifiée récente » comme garde de purge, sans seuil chiffré ni champ de cadence : « récente » varie selon l'implémentation | REQ-GEN-06 ; ADR-006 ; exigences NF §5 | mineure | Définir « récente » : cadence configurable par projet (cf. REQ-GEN-07), défaut explicite (par exemple 24 h), erreur `backup_too_old` documentée |

### B.3 Gestion des erreurs

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| **N-11** — Mécanisme CSRF sans session non spécifié : ADR-003 exige un « jeton d'écriture pour les formulaires, même sans session », mais rien ne dit comment l'UI React obtient ce jeton (endpoint dédié, cookie double-submit, en-tête) ; sans cette précision, l'implémentation risque d'être inexistante ou non testable | ADR-003 ; exigences NF §2 (CSRF — Obligatoire) ; §9.2 | mineure | Spécifier le mécanisme et son test : GET d'un jeton d'écriture, transmission par en-tête sur chaque écriture, refus 403 sinon |
| **N-12** — La coordination purge/file d'ingestion n'est pas exigée dans le CdC : l'ADR-006 la porte seul ; aucun comportement d'erreur n'est défini côté API (refus « ingestion en cours » sur `POST /api/projects/{id}/purge`) | ADR-006 ; REQ-GEN-06 ; §9.2 | mineure | Une exigence : la purge s'exécute dans la même file que l'ingestion ; si une ingestion est en cours, la purge attend ou est refusée avec le motif dans le format `{code, message, details}` ; scénario Gherkin de purge pendant ingestion |
| **N-13** — Source de l'estimation du budget en cours de run non définie : l'arrêt au plafond (REQ-AGT-13) suppose une lecture périodique de la consommation que l'adaptateur doit fournir ; cadence d'observation et réaction non spécifiées | REQ-AGT-13 ; ADR-005 ; règle §7 « Budget agent » | mineure | Préciser : l'adaptateur expose l'usage périodiquement (ou à la fin de chaque appel) ; la Console échantillonne à une cadence configurable et arrête le processus au dépassement d'estimation ; scénario d'un tick dépassant le plafond |
| **N-14** — Annulation d'un run en file non définie : REQ-AGT-09 met « un troisième run en file », mais aucun comportement d'annulation ou d'affichage pour un run `queued` n'est spécifié (les filtres REQ-AGT-04 listent « statut » sans états) | REQ-AGT-09 ; REQ-REV-10 ; §8 `task_runs.status` | mineure | Statuer le cycle de vie : `queued` → annulable → `cancelled` sans exécution ; les limites par agent et par projet s'appliquent à la mise en file |
| **N-15** — L'énumération des statuts de `task_runs` n'est écrite nulle part : le §9.1 cite `queued`/`running`/`done`/`cancelled` pour les revues, le §14 ajoute `failed` pour un dépassement de budget ; sans liste fermée, les scénarios, les filtres et les métriques divergent | §8 `task_runs` ; REQ-AGT-01/07 ; §9.1 ; §14 | mineure | Énumérer la liste fermée des états avec transitions autorisées (au minimum `queued`, `running`, `done`, `failed`, `timeout`, `cancelled`), en cohérence avec `ingestion_runs.status` |

### B.4 Sécurité

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| **N-16** — Accès navigateur depuis l'hôte Windows en WSL2 : l'écoute sur `127.0.0.2` a une sémantique particulière sous WSL2 (en mode NAT, les connexions de l'hôte arrivent via `127.0.0.1` ; `127.0.0.2` est concerné par le mode réseau miroir). La matrice compat liste « Windows 11 via WSL2 » comme cible MVP, mais rien ne traite la joignabilité de l'UI depuis le navigateur de l'hôte | §12 (écoute `127.0.0.2`) ; exigences NF §6 (Windows 11 via WSL2, « natif non garanti ») ; §10 (portabilité) | mineure | Documenter le comportement attendu sous WSL2 : test de matrice « serveur joignable depuis le navigateur hôte », et mention du mode réseau miroir comme solution de contournement ; un point d'installation dédié dans le guide |
| **N-17** — Périmètre de la chaîne d'audit par projet vs global non tranché : `audit_events` porte `project_id` et un index `(generation)` ; la règle `hash = sha256(prev_hash + payload)` ne dit pas si la chaîne continue d'un projet à l'autre (mélange) ou si chaque projet a la sienne — la restauration et le contrôle d'intégrité en dépendent | §8 `audit_events` ; REQ-GEN-04 ; ADR-006 | mineure | Trancher : une chaîne **par projet**, `prev_hash` et `generation` adossés au couple (projet, génération) ; un scénario avec deux projets en simultané |
| **N-18** — Contrôle d'intégrité de l'audit porté par l'ADR seulement : ADR-006 exige qu'un échec « bloque le démarrage et alerte », mais aucune REQ (ni critère, ni scénario) ne porte ce contrôle ni ses déclencheurs (démarrage, après purge, à la demande) | REQ-GEN-04 ; ADR-006 ; CLI `doctor` | mineure | Une REQ : contrôle d'intégrité de la chaîne au démarrage et après toute purge d'audit, échec bloquant et alerte visible ; un scénario sur une chaîne volontairement altérée |
| **N-19** — La rédaction des secrets couvre l'affichage mais pas explicitement les données exportées : `ingestion_runs.stats_json`, les contenus ingérés de `runs.jsonl` et l'export REQ-GEN-03 peuvent contenir des valeurs sensibles ; le test « faux jeton » (REQ-SEC-05) ne vise que le log affiché | REQ-AGT-05 ; REQ-SEC-05 ; REQ-GEN-03 | mineure | Étendre le test « faux jeton » aux contenus exportés (JSON/CSV) et aux champs agrégés stockés en base (`stats_json`, journal des runs) |

### B.5 Accessibilité (RGAA / WCAG)

**Section conforme.** Vérifié : `aria-live` pour les mises à jour SSE sans déplacement du focus (§9.1, exigences NF §3), navigation clavier couverte par le scénario « Les 12 vues sont navigables au clavier » (§14), focus visible, aucune information portée par la seule couleur (badge + texte, §9.1), tableaux avec `caption`, équivalent textuel de la carte d'activité (REQ-EQ-06), `prefers-reduced-motion` exigé (exigences NF §3), thèmes clair et sombre contrastés avec etiquettes lisibles, RGAA 4.1 AA / WCAG 2.2 AA avec audit et tests clavier (§10).

### B.6 Cohérence avec les ADR

**Section conforme.** Vérifié : ADR-001 (React 19/Vite, build embarqué, Node au build seulement = §12) ; ADR-002 (FastAPI/SQLAlchemy/Alembic, SQLite WAL, un seul écrivain, migrations versionnées = §8) ; ADR-003 (boucle locale, refus de tout bind hors `127.0.0.0/8`, sans auth assumé = §10/§11/§12) ; ADR-004 (multi-dépôts, personnes canoniques = §7/§8) ; ADR-005 (runner : préflight, groupe de processus, budget, environnement purgé = §6.11) ; ADR-006 (rétention 12 mois, audit hors purge auto, ancrage = §7/§8). Aucune contradiction entre le CdC et les ADR acceptés. Les résidus applicatifs (retrait « conservation ou suppression », coordination purge/file) sont signalés en B.2/B.3/B.8 sans constituer des contradictions d'ADR.

### B.7 Cohérence avec les exigences non fonctionnelles

| Constat | Référence (exigence NF) | Gravité | Proposition |
|---|---|---|---|
| **N-20** — Brief et exigences NF toujours « à valider » : les deux documents portent « Statut : à valider » sans trace de validation datée ; le gate « brief validé » (étape 1) n'est pas autrement prouvé, et l'entrée du gate `spec_freeze` repose sur ces documents d'entrée | [`brief.md`](brief.md) (ligne finale) ; [`exigences-nf.md`](exigences-nf.md) (ligne finale) ; workflow §5 étape 1 | **majeure** | Faire valider (acte du responsable humain) le brief et les exigences NF, dater les en-têtes (« Validé par … — Date »), et le référencer dans le change OpenSpec avant le gel |
| **N-21** — Respect proactif du quota API absent des exigences : ETag/requêtes conditionnelles, backoff et mode fichier restent narratifs (§9.4, livrable 6, §16, menaces) ; aucune REQ ne les rend opposables, alors que le brief liste « API GitHub/GitLab limitée » en risque | [`brief.md`](brief.md) §5 ; §16 ; REQ-SOC-17 | mineure | Une exigence SHOULD : requêtes conditionnelles (ETag / If-Modified-Since), backoff exponentiel, cache local et mode fichier pour les collecteurs, avec test sans réseau |
| Performance, sécurité, accessibilité, confidentialité, compatibilité de [`exigences-nf.md`](exigences-nf.md) cohérentes avec §10/§11/§12 du CdC (aucun chiffre divergent, aucune contradiction CSRF/bind/trousseau) : conforme | exigences NF §1, §2, §3, §4, §6, §7 | conforme | — |

### B.8 Traçabilité et testabilité

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| **N-22** — Critère contradictoire résiduel : « Et son coût ne dépasse pas le budget » (nouvelle vérification : ligne 639 de la version corrigée) est infaisable et contredit REQ-AGT-13 (MUST), l'ADR-005 (négative explicite « le coût réel peut dépasser légèrement ») et le scénario du même §14 « Un run qui dépasse le budget est arrêté » ; deux scénarios du même document mènent à des verdicts opposés en recette | §14 scénario « Un run est lancé avec un budget et annulable » (ligne 639) vs REQ-AGT-13 ; ADR-005 ; §14 scénario budget | **majeure** | Supprimer la ligne et la remplacer par « Et si le plafond est atteint, le run est arrêté ; le coût réel est affiché et tout dépassement est signalé » |
| **N-23** — La règle du retrait « conservation ou suppression » du scénario (§14) n'a pas de sémantique face à `ON DELETE CASCADE` (§8, sauf `audit_events` et `backup_runs`) : conserver les commits d'un dépôt supprimé est impossible avec la cascade actuelle ; la ré-élection du dépôt principal (`repositories.is_primary`) n'est pas spécifiée | §14 scénario « Le retrait d'un dépôt est explicite » ; §8 contraintes FK ; REQ-SOC-12 | mineure | Trancher : soit « suppression » par cascade (option unique, le scénario simplifié), soit conservation par table d'archivage (`repositories.retired_at` + données conservées hors agrégation) ; exiger la ré-élection automatique du dépôt principal ou le refus du retrait du dépôt principal |
| **N-24** — La règle « tâche terminée seulement si tous les dépôts concernés passent » et la vue Gates à l'échelle d'une feature ne figurent pas dans le tableau des exigences : la jointure entre `gate_runs` (repository_id nullable) et la feature n'est pas décrite (aucune liaison `gate → feature`), REQ-FEA-01 expose un « gate » par feature sans règle d'agrégation définie | ADR-004 ; §8 (`gate_runs`, `feature_repositories`, `tasks`) ; REQ-FEA-01/02 ; REQ-GAT-10 | mineure | Ajouter (ou étendre) une REQ : le gate d'une feature = conjonction des gates des dépôts couverts par `feature_repositories` / `task_repositories` ; chaque run de gate porte son `repository_id` ; le statut feature est vert si et seulement si tous les dépôts passent |
| **N-25** — L'empreinte de version de config du REQ-GAT-13 n'a pas de champ récepteur dans le schéma : `gates.config_json` existe, mais ni colonne d'empreinte ni table de versions ; l'exigence est implémentable hors modèle sans ancrage clair | REQ-GAT-13 ; §8 table `gates` | mineure | Ajouter un champ `config_fingerprint` à `gates` (ou une table `config_versions`) et une règle : changement de config ⇒ gates marqués « recalcul requis » |
| **ID uniques et compte des exigences : conforme.** Comptage vérifié sur la version corrigée : SOC 21, OV 6, FEA 5, GAT 14, REV 11, DEP 5, EQ 8, PRO 7, SEC 5, PER 5, AGT 14, DOC 4, CFG 4, GEN 9 = **118 exigences** ; numérotation régulière, IDs uniques ; chaque MUST porte un critère d'acceptation, hormis les résidus signalés ci-dessus | §6.1 à §6.14 | conforme | — |
| **Couverture Gherkin des corrections de l'itération 1 : conforme** : purge (2 scénarios), retrait d'un dépôt, contributeur multi-identités, quota, collecteurs GitHub/GitLab, run dépassant le budget, profil « non identifiable », escalade après 3 rejets, accessibilité clavier, sécurité d'écoute locale sont désormais écrits (§14) | §14 | conforme | — |

### B.9 Impacts recette, déploiement, exploitation

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| **N-26** — Granularité de sauvegarde incohérente : la base est un **fichier unique** SQLite (`data/sdlc.sqlite3`), mais les sauvegardes sont exposées **par projet** (`POST /api/projects/{id}/backup`, `backup_runs.project_id`) et globalement par CLI (`sdlc-console backup --verify` sans argument projet). Une sauvegarde « par projet » d'un fichier unique n'existe pas : soit la sauvegarde couvre toute la base (l'attribut projet est un simple marqueur d'affichage), soit c'est un export partiel (alors distinct d'un restore complet) | §8 (`backup_runs`, fichier unique) ; §9.2 ; §9.3 ; exigences NF §5 | mineure | Trancher : la sauvegarde est toujours **le fichier complet** ; retirer `project_id` de `backup_runs` (ou le documenter comme filtre d'affichage) ; la restauration ramène tous les projets — en cohérence avec les routes API, le CLI et l'âge de sauvegarde (REQ-GEN-07) |
| **N-27** — Purge des fichiers de logs hors base (`task_runs.log_path`, fichiers de logs sous `reports/`) : la rétention de 12 mois porte sur les tables, pas sur les fichiers ; une purge de base laissera des logs de plus de 12 mois sur le disque, en contradiction avec la doctrine RGPD de l'exigence NF §4 | §7 « Rétention » ; §8 `task_runs.log_path` ; exigences NF §4 | mineure | Étendre `sdlc-console purge` aux fichiers de logs datés au-delà de la rétention, avec journalisation et sauvegarde préalable ; un test de purge des fichiers |
| **N-28** — Procédure de mesure du corpus processus peu spécifiée : le livrable 7 (corpus étiqueté) et le lot L4 existent, mais ni la commande, ni l'exécutant, ni le livrable de sortie (rapport de recette ?) ne sont définis — l'objectif ≥ 80 % reste faiblement opposable en fin de projet | CdC livrable 7 ; lot L4 ; §17.1 ; §2 | mineure | Ajouter : une commande de mesure (par exemple `sdlc-console process corpus <chemin>`), un fichier de résultat dans le rapport de recette avec la précision mesurée et la liste des échecs de classification |
| **Routes REST et CLI posées pour les actions MUST : conforme** après vérification — waivers, purge, export, backup + verify, dépôt principal, surcharge processus, annulations, SSE : toutes présentes (§9.2/§9.3/REQ-GEN-08), avec le format d'erreurs unique | §9.2, §9.3 | conforme | — |
| **Diagnostic et exploitation conformes** : `/api/health` (version, schéma), doctor (jetons via `--with-tokens`), codes de retour CLI normalisés (0/1/2), âges affichés, portabilité testée en matrice CI : conforme | §9.2/§9.3 ; §10 ; exigences NF §5 | conforme | — |

---

## C. Verdict

### C.1 Décompte de l'itération 1

| Catégorie | Résolus | Partiellement résolus | Non résolus |
|---|---|---|---|
| Bloquantes (2) | 1 (ADR absents) | 1 (brief + exigences NF : créés mais « à valider ») | 0 |
| Majeures (21) | 17 | 4 (retrait de dépôt, run d'agent en échec, purge concurrente, plafond de coût) | 0 |
| Mineures vérifiées (17) | 16 | 1 (quota / ETag / backoff / mode fichier) | 0 |

Aucun constat de l'itération 1 n'est resté sans mouvement. Les corrections sont visibles, référencées et, pour la plupart, testables.

### C.2 Nouvelles contestations

- **Bloquantes : 0.**
- **Majeures : 2** — N-20 (brief et exigences NF créés mais toujours « à valider », gate « brief validé » sans trace) ; N-22 (critère contradictoire « son coût ne dépasse pas le budget » conservé dans un scénario du §14, en contradiction avec REQ-AGT-13 et l'ADR-005).
- **Mineures : 26** — N-01 à N-19, N-21, N-23 à N-28, réparties ainsi : scénarios manquants pour quatre MUST (4) ; cas limites identités, dérogations sans finding, empreinte, forks/cherry-picks, garde de purge (6) ; erreurs CSRF, purge/file, budget en cours, run en file, statuts de run (5) ; sécurité WSL2, périmètre de la chaîne d'audit, contrôle d'intégrité, secrets exportés (4) ; NF quota proactif (1) ; traçabilité multi-dépôts, contrat de retrait, empreinte de config (3) ; exploitation sauvegarde, fichiers de logs, mesure du corpus (3).

### C.3 Verdict

**Non prêt pour spec_freeze — résiduel faible, corrections ponctuelles avant le gel.** Aucune bloquante nouvelle ; les résidus sont précis et d'une charge de correction faible :

1. **N-22 (majeure)** — §14, scénario « Lancement d'agent depuis l'interface » : supprimer « Et son coût ne dépasse pas le budget » et la remplacer par « Et si le plafond est atteint, le run est arrêté ; le coût réel est affiché et tout dépassement est signalé ». Une seule ligne ; sans elle, la matrice de recette produira deux verdicts opposés sur le même sujet (REQ-AGT-13, ADR-005).
2. **N-20 (majeure)** — [`brief.md`](brief.md) et [`exigences-nf.md`](exigences-nf.md) : attacher la validation humaine (« Validé par … — Date ») pour boucler le gate « brief validé » de l'étape 1 ; sans elle, l'entrée du gate spec_freeze repose sur des documents non validés.
3. **Mineures à intégrer au change OpenSpec** — portée des indexes `persons`/`person_identities` et règles de fusion (N-05, N-06), définition normative de `commit_fingerprint` (N-09), coordination purge/file au niveau REQ (N-12), énumération des statuts de `task_runs` (N-15), contrat de retrait d'un dépôt vs cascade (N-23), gates multi-dépôts à portée d'exigence (N-24), empreinte de config sans champ (N-25), granularité de sauvegarde (N-26), purge des fichiers de logs (N-27).
4. **Traiter les 5 partiellement résolus de l'itération 1** dans le change : retrait de dépôt, scénario de run en échec (crash/timeout), purge concurrente, plafond de coût, quota proactif.
5. **Le change OpenSpec `console-sdlc` reste à écrire** (§3.4 et §17.1 du CdC) : c'est lui qui passera le gate `spec_freeze` ; toutes les corrections ci-dessus doivent y atterrir.

Le contenu technique du cadrage est solide : les décisions structurantes sont couvertes par les six ADR acceptés, l'analyse de menaces est complète, les 118 exigences sont traçables ; ce qui reste relève de divergences ponctuelles induites par la vague de corrections elle-même et d'exigences de traçabilité à reporter depuis les ADR vers le tableau des REQ.

---

*Revue contradictoire itération 2 proposée par : contradicteur indépendant (GLM-5.3-Flash Free, agent OpenCode) — Date : 2026-10-20 — Lecture seule : aucun autre fichier modifié.*
