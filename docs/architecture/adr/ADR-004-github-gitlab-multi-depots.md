# ADR-004 — Collecteurs GitHub + GitLab et modèle multi-dépôts

## Statut

Accepté — 2026-10-20.

Remplacé par : —

## Contexte

Un projet SDLC dépasse souvent un seul dépôt : API, web, infrastructure, bibliothèques
partagées. Les équipes utilisent GitHub ou GitLab, parfois les deux. Les métriques d'équipe
et de processus doivent rester justes malgré des historiques distincts et des identités
multiples (même personne, plusieurs emails, comptes différents).

La revue contradictoire a signalé deux risques : un contributeur compté plusieurs fois et un
commit présent dans deux dépôts compté deux fois dans l'agrégat « tous ».

## Décision

- **Un projet contient N dépôts** (`repositories`), chacun avec `provider` (`github` |
  `gitlab`), `url`, `local_path`, `default_branch`, `is_primary`.
- **Collecteurs séparés** GitHub et GitLab, avec un contrat commun normalisé
  (MR/PR, revues, approbations, état, dates, stratégie de merge).
- **Identité canonique** : table `persons`, avec `person_identities` (provider, external_id,
  email). Les commits sont rapprochés par email ; les comptes MR par identité fournisseur.
  Une fusion de personnes est possible, tracée dans l'audit.
- **Déduplication multi-dépôts** : un `commit_fingerprint` =
  `sha256(sha + "\n" + email_auteur_normalisé + "\n" + author_date_utc_iso8601)` ; les
  dépôts déclarés comme miroirs ou forks partagent un `dedup_group`. Le total « tous les
  dépôts » déduplique par empreinte ; l'interface indique le dépôt d'origine et un badge
  « dédoublonnage appliqué ».
- **Rapprochement des identités** : email exact d'abord, puis compte fournisseur ; un conflit
  de nom ne provoque jamais d'appariement silencieux. Les bots fournisseur sont marqués
  `is_bot` et exclus des métriques. Une personne référencée n'est pas supprimée : une fusion
  renseigne `superseded_by_person_id` et écrit un événement d'audit.
- **Retrait d'un dépôt** : archivage par défaut (`retired_at`), suppression définitive
  explicite et cascadée ; le dépôt principal est réélu ou le retrait est refusé.
- **Métriques par dépôt**, puis agrégation explicite : le filtre « tous » ne fait pas une
  simple somme si un `dedup_group` est présent.
- **Processus par dépôt** : un profil et une confiance par dépôt ; la vue projet affiche le
  profil dominant et signale les divergences, sans moyenne inventée.
- **Features et tâches multi-dépôts** : une feature peut couvrir N dépôts ; une tâche peut
  toucher N dépôts via `task_repositories`. Un gate est évalué par dépôt ; la tâche n'est
  terminée que lorsque tous les dépôts concernés passent.
- Fournisseurs en MVP : **GitHub et GitLab**. Bitbucket et Azure DevOps hors périmètre.

## Conséquences

### Positives

- Vue fidèle des projets réels multi-dépôts.
- Identité et agrégation explicites, testables.
- Un modèle commun permet d'ajouter un fournisseur sans réécrire les vues.
- Les features transverses sont représentables.

### Négatives

- Ingestion et tests plus complexes (deux API, pagination, quotas).
- Nécessité d'une table `persons` et de règles de rapprochement.
- Les dépôts miroirs/forks doivent être déclarés pour dédupliquer correctement.
- Les gates par dépôt augmentent le nombre de runs.

## Alternatives envisagées

| Alternative | Avantages | Inconvénients | Raison du rejet |
|---|---|---|---|
| Un dépôt par projet | Modèle simple | Ne couvre pas les projets réels | Contredit la décision multi-dépôts |
| Somme naïve des dépôts | Implémentation simple | Double comptage des miroirs/forks | Fausse les métriques |
| Un projet par dépôt | Isolation | Perd la vue projet et les features transverses | Ne répond pas au besoin |
| Ajouter Bitbucket/Azure dès le MVP | Couverture | Trois ou quatre API à maintenir | Reporté |

## Références

- Cahier des charges §3, §6.1, §6.7, §6.8, §7, §8 : [`../00-cadrage/cahier-des-charges-web.md`](../../00-cadrage/cahier-des-charges-web.md)
- Revue contradictoire §2 : [`../00-cadrage/revue-cahier-des-charges-web.md`](../../00-cadrage/revue-cahier-des-charges-web.md)

---

*Date de proposition : 2026-10-20 — Date d'acceptation : 2026-10-20*
