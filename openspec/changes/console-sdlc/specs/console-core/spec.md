## ADDED Requirements

### Requirement: Projet multi-dépôts

Le système SHALL permettre de créer un projet rattaché à un ou plusieurs dépôts Git
GitHub ou GitLab, avec un dépôt principal, une branche par défaut et un fuseau horaire.

#### Scenario: Création d'un projet à deux dépôts
- **WHEN** l'utilisateur crée un projet avec deux dépôts GitHub et GitLab valides
- **THEN** le projet apparaît dans la barre latérale
- **AND** les deux dépôts sont listés avec leur fournisseur et leur dépôt principal
- **AND** les vues proposent le filtre « tous les dépôts » ou un dépôt
- **AND** le choix de dépôt est conservé dans l'URL et partageable

#### Scenario: Chemin de dépôt invalide
- **WHEN** l'utilisateur déclare un chemin qui n'est pas un dépôt Git
- **THEN** la création est refusée avec un message explicite
- **AND** aucun dépôt n'est enregistré

#### Scenario: Retrait d'un dépôt
- **WHEN** l'utilisateur retire le dépôt B d'un projet à deux dépôts
- **THEN** le dépôt B est archivé par défaut (`retired_at`)
- **AND** il disparaît des agrégats mais son historique reste consultable
- **AND** le dépôt principal est réélu si nécessaire
- **AND** une suppression définitive demande une confirmation et est auditée

### Requirement: Ingestion Git

Le système SHALL ingérer les commits de chaque dépôt : sha, personne, date, ajouts et
suppressions, fichiers, merge, bot, trailer IA et empreinte de commit.

#### Scenario: Ingestion idempotente
- **WHEN** l'utilisateur lance deux fois l'ingestion du même dépôt
- **THEN** le nombre de commits reste identique
- **AND** la date de dernière ingestion est mise à jour
- **AND** aucune donnée n'est dupliquée

### Requirement: Collecteurs GitHub et GitLab

Le système SHALL ingérer les pull requests GitHub et les merge requests GitLab dans un
modèle normalisé : auteur, état, dates, cible, stratégie de merge, revues et approbations.

#### Scenario: Normalisation des deux fournisseurs
- **WHEN** une PR GitHub et une MR GitLab sont ingérées
- **THEN** les deux apparaissent dans la vue Équipe et dans la vue Processus
- **AND** les valeurs absentes sont affichées « non mesuré »

#### Scenario: Quota fournisseur épuisé
- **WHEN** l'API GitHub ou GitLab renvoie un quota épuisé
- **THEN** le badge de la source passe à « échec »
- **AND** aucune donnée partielle n'est marquée « à jour »
- **AND** une relance reprend sans doublon

### Requirement: Ingestion des runs et déploiements

Le système SHALL ingérer `runs.jsonl` et `deploys.jsonl` : agent, rôle, modèle, tâche,
statut, durée, coût, tokens pour les runs ; environnement, version, statut, durée, auteur et
rollback pour les déploiements.

#### Scenario: Déploiement ingéré
- **WHEN** `deploys.jsonl` contient un déploiement prod réussi
- **THEN** la vue Déploiements affiche l'environnement, la version et la date
- **AND** le lead time et les métriques DORA sont alimentés

#### Scenario: Run ingéré
- **WHEN** `runs.jsonl` contient un run de relecteur
- **THEN** la vue Agents IA affiche l'agent, le modèle, la tâche et le coût
- **AND** le run est lié à sa tâche

### Requirement: Identités canoniques

Le système SHALL rapprocher les identités d'une même personne par email exact, puis par
compte fournisseur. Un conflit de nom SHALL produire une revue manuelle et jamais un
appariement silencieux. Les bots SHALL être marqués et exclus des métriques d'équipe.

#### Scenario: Contributeur multi-emails
- **WHEN** un contributeur a deux emails et deux comptes fournisseur
- **THEN** la vue Équipe affiche une seule personne
- **AND** son bus factor n'est pas doublé

#### Scenario: Fusion auditée
- **WHEN** deux personnes sont fusionnées
- **THEN** `superseded_by_person_id` est renseigné
- **AND** un événement d'audit est écrit
- **AND** une opération inverse auditée peut rétablir les rattachements d'origine

#### Scenario: Même email dans deux projets
- **WHEN** deux projets distincts contiennent la même adresse email
- **THEN** les deux personnes restent distinctes par projet
- **AND** aucune collision d'index n'empêche la seconde ingestion

### Requirement: Agrégation multi-dépôts sans double comptage

Le système SHALL calculer les métriques par dépôt puis les agréger en dédupliquant les
commits par empreinte et par groupe de déduplication. L'interface SHALL afficher le dépôt
d'origine et un badge « dédoublonnage appliqué ».

#### Scenario: Commit présent dans deux dépôts
- **WHEN** le même commit est présent dans un dépôt miroir et dans le dépôt principal
- **THEN** il n'est compté qu'une fois dans le total « tous les dépôts »
- **AND** le dépôt d'origine est affiché

### Requirement: Features et tâches multi-dépôts

Le système SHALL permettre à une feature de couvrir plusieurs dépôts et à une tâche de
toucher plusieurs dépôts. Le gate d'une feature SHALL être la conjonction des gates de ses
dépôts.

#### Scenario: Feature sur deux dépôts
- **WHEN** une feature couvre les dépôts API et Web
- **THEN** la vue Gates affiche un statut par dépôt
- **AND** la feature n'est verte que si les deux dépôts sont verts

### Requirement: Fichier de suivi ouvert dès qu'il est prêt

Le système SHALL générer le fichier de suivi et l'ouvrir automatiquement dès qu'il est
prêt, une seule fois, sans bloquer l'interface, avec un lien persistant.

#### Scenario: Ouverture automatique du suivi
- **WHEN** la génération du fichier de suivi se termine
- **THEN** la vue Suivi s'ouvre dans un nouvel onglet
- **AND** un lien persistant reste disponible
- **AND** l'interface n'est pas bloquée
- **AND** aucune ouverture supplémentaire n'a lieu si la vue est déjà active

#### Scenario: Ouverture désactivée
- **WHEN** `ui.open_suivi_on_ready` vaut `false`
- **THEN** aucun onglet ne s'ouvre
- **AND** un bandeau avec le lien du suivi est affiché

### Requirement: Suivi synchrone tâche par tâche

Le système SHALL mettre à jour `tasks.md`, `state.json` et le fichier de suivi HTML dans la
même opération logique à chaque changement de statut de tâche, en moins de 2 secondes. Il
SHALL resynchroniser les modifications externes de `tasks.md` ou `state.json` via un watcher
et SHALL émettre `suivi.updated`. Aucun mode « lot » ne remplace la mise à jour tâche par
tâche.

#### Scenario: Changement de statut
- **WHEN** une tâche passe de `todo` à `done` avec une note
- **THEN** `tasks.md` est coché
- **AND** `state.json` contient `done` et la note
- **AND** le fichier de suivi HTML est régénéré
- **AND** `suivi.updated` est émis en moins de 2 s

#### Scenario: Modification externe
- **WHEN** `tasks.md` est modifié hors de l'interface
- **THEN** le watcher détecte le changement
- **AND** `state.json` et le HTML sont resynchronisés
- **AND** un conflit est signalé si `state.json` diverge

#### Scenario: Échec d'écriture
- **WHEN** l'écriture de `state.json` échoue après la mise à jour de `tasks.md`
- **THEN** l'opération est annulée ou rejouée
- **AND** les trois supports restent cohérents
- **AND** l'erreur est affichée et auditée

### Requirement: Fraîcheur et états d'erreur

Le système SHALL afficher la fraîcheur de chaque source et les états de chargement, vide,
erreur, périmé et projet ou dépôt désactivé.

#### Scenario: Source en retard
- **WHEN** la dernière ingestion d'un dépôt date de plus de la cadence configurée
- **THEN** un badge « en retard » est affiché sur ce dépôt
- **AND** la vue d'ensemble le signale

### Requirement: Accessibilité et navigation

Le système SHALL être navigable au clavier, respecter RGAA 4.1 AA et WCAG 2.2 AA, annoncer
les mises à jour SSE dans une région `aria-live` sans déplacer le focus, et ne jamais porter
une information par la couleur seule. Il SHALL respecter le contraste AA des thèmes clair et
sombre, fournir un équivalent textuel aux graphiques, des `caption` aux tableaux et
`prefers-reduced-motion`.

#### Scenario: Parcours clavier des 12 vues
- **WHEN** un utilisateur navigue uniquement au clavier
- **THEN** chaque action des 12 vues est atteignable
- **AND** le focus reste visible
- **AND** les mises à jour SSE sont annoncées sans déplacer le focus

#### Scenario: Équivalent textuel d'un graphique
- **WHEN** un graphique est affiché
- **THEN** un équivalent textuel ou un tableau de données est disponible
- **AND** le contraste des thèmes clair et sombre est conforme AA

### Requirement: Vue d'ensemble

Le système SHALL afficher une vue d'ensemble avec les KPI (avancement, gates, couverture,
vulnérabilités, coût IA, délai spec→prod), les décisions en attente triées par blocage, le
pipeline SDLC alimenté par `state.json` et les gates, et les risques ouverts par catégorie.
Chaque KPI SHALL indiquer sa source et afficher « non mesuré » lorsqu'elle manque.

#### Scenario: KPI avec source
- **WHEN** la vue d'ensemble est affichée
- **THEN** chaque KPI indique sa source
- **AND** un KPI sans donnée affiche « non mesuré »

#### Scenario: Décisions en attente
- **WHEN** une migration destructive bloque un gate
- **THEN** la vue d'ensemble affiche une décision en attente
- **AND** un lien ouvre la preuve ou la fiche de décision

#### Scenario: Pipeline et risques
- **WHEN** une étape du pipeline est en échec
- **THEN** l'étape est signalée dans la vue d'ensemble
- **AND** les risques ouverts sont listés par catégorie

### Requirement: Liste et détail des features et tâches

Le système SHALL lister les features avec phase, tâches, couverture, gate, exécutant et
relecteur, permettre d'ouvrir le détail d'une tâche avec ses fichiers, critères, statut et
rapport, et signaler les incohérences entre `tasks.md` et `state.json`.

#### Scenario: Liste filtrée
- **WHEN** l'utilisateur filtre les features par phase et par gate
- **THEN** la liste ne contient que les features correspondantes
- **AND** le filtre est conservé dans l'URL

#### Scenario: Détail d'une tâche
- **WHEN** l'utilisateur ouvre une tâche terminée
- **THEN** les fichiers, critères et statut sont affichés
- **AND** un lien ouvre le rapport de fin de tâche

#### Scenario: Incohérence de suivi
- **WHEN** une tâche est cochée dans `tasks.md` mais absente de `state.json`
- **THEN** l'incohérence est listée
- **AND** elle est signalée dans la vue Features

#### Scenario: Traçabilité
- **WHEN** une exigence est affichée
- **THEN** ses scénarios, tests et tâches sont liés
- **AND** une exigence sans test est signalée

### Requirement: Pagination serveur

Le système SHALL paginer les listes côté serveur avec `limit`, `offset` et `total`, et
SHALL utiliser 50 lignes par défaut.

#### Scenario: Liste paginée
- **WHEN** une liste contient 120 éléments
- **THEN** la première page contient 50 éléments
- **AND** `total` vaut 120
- **AND** la page suivante utilise `offset=50`

#### Scenario: Bornes de pagination invalides
- **WHEN** `limit` dépasse 200 ou `offset` est négatif
- **THEN** la requête est refusée avec `400`
- **AND** le message indique les bornes autorisées

#### Scenario: Dernière page partielle
- **WHEN** une liste contient 120 éléments, `limit=50` et `offset=100`
- **THEN** la page contient les 20 éléments restants
- **AND** `total` reste 120

#### Scenario: Offset au-delà du total
- **WHEN** `offset` est supérieur ou égal à `total`
- **THEN** la liste est vide
- **AND** la réponse est `200` avec `total` inchangé

### Requirement: Chemins d'ingestion confinés

Le système SHALL résoudre les chemins de dépôt et de rapports en absolu, refuser tout
chemin hors du périmètre déclaré et tout segment `..`, et ne JAMAIS lire un fichier de
secrets.

#### Scenario: Path traversal
- **WHEN** un chemin d'ingestion contient `../` ou sort du projet
- **THEN** l'ingestion est refusée avec un message explicite
- **AND** aucun fichier n'est lu
- **AND** la tentative est auditée

### Requirement: Dégradation gracieuse

Le système SHALL avertir lorsque les volumes dépassent les cibles (100 k commits, 5 dépôts)
et SHALL paginer sans charger l'intégralité des données.

#### Scenario: Dépôt volumineux
- **WHEN** un dépôt dépasse 100 k commits
- **THEN** un avertissement « dépôt volumineux, mesures prêtes » est affiché
- **AND** les listes restent paginées
