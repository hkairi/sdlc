# sdlc-tracking Specification

## Purpose
TBD - created by archiving change add-ai-sdlc-tracker. Update Purpose after archive.
## Requirements
### Requirement: Synchronisation appliquée dans la session

Un commit lancé par l'agent SHALL être refusé tant que le fichier de suivi et `tasks.md` divergent
pour les changes touchés par ce commit. Le refus MUST nommer les écarts et la correction à jouer, et
MUST provenir du même contrôle que celui du hook git et de la CI (`scripts/check_sync.py`), afin qu'un
verdict « synchrone » dans la session ne soit jamais contredit par un refus au commit.

Le contrôle MUST s'appliquer uniquement aux chemins touchés par le commit lorsqu'il peut les
déterminer, et MUST se replier sur l'ensemble des changes ouverts sinon.

#### Scenario: Commit avec un suivi désynchronisé
- **WHEN** l'agent lance `git commit` alors qu'une case de `tasks.md` est cochée sans que le suivi correspondant soit à `done`
- **THEN** le commit est refusé, le message nomme la tâche et les deux fichiers en cause, et indique la commande de correction

#### Scenario: Commit avec un suivi synchrone
- **WHEN** l'agent lance `git commit` alors que les suivis des changes touchés sont synchrones
- **THEN** le commit n'est pas refusé, et le verdict de synchronisation est ajouté à la sortie de la commande

#### Scenario: Verdict identique au gate hors session
- **WHEN** le même ensemble de chemins est contrôlé dans la session puis par `.githooks/pre-commit` ou la CI
- **THEN** les deux verdicts sont identiques (même code de sortie, mêmes écarts listés)

### Requirement: Mise à jour d'une tâche en une seule opération

Le système SHALL permettre de mettre à jour une tâche — statut, date, note — et la case correspondante
de `tasks.md` en **une seule** opération, afin qu'aucun état intermédiaire désynchronisé ne puisse
exister. L'opération MUST refuser une tâche inconnue sans modifier aucun fichier.

#### Scenario: Une tâche close
- **WHEN** une tâche est mise à `done` avec une note
- **THEN** le suivi porte `data-status="done"` et sa date, et la case de `tasks.md` est cochée dans le même geste

#### Scenario: Une tâche rouverte
- **WHEN** une tâche déjà `done` est ramenée à `doing`, `blocked` ou `todo`
- **THEN** la case de `tasks.md` est décochée et le statut du suivi est mis à jour dans le même geste

#### Scenario: Tâche inconnue
- **WHEN** l'identifiant de tâche n'existe ni dans le suivi ni dans `tasks.md`
- **THEN** aucun fichier n'est modifié et la réponse liste les identifiants candidats

### Requirement: Cible résolue et annoncée

Le système SHALL déterminer seul si un chantier est suivi dans un fichier mono (`docs/suivi-<id>.html`)
ou dans le suivi multi-chantiers (`docs/suivi-multi.html`), et MUST annoncer le fichier qu'il a modifié.
Cette annonce est obligatoire : une mise à jour appliquée au mauvais fichier ne doit pas pouvoir passer
pour un succès.

#### Scenario: Chantier suivi en mono
- **WHEN** une tâche est mise à jour pour un change dont le suivi mono existe
- **THEN** le fichier mono est modifié et nommé dans la réponse

#### Scenario: Chantier référencé par le suivi multi
- **WHEN** une tâche est mise à jour pour un change référencé dans le suivi multi et sans suivi mono
- **THEN** le bloc d'état du suivi multi est modifié pour ce chantier, et le fichier multi est nommé dans la réponse

#### Scenario: Cible forcée
- **WHEN** l'appel désigne explicitement un fichier de suivi
- **THEN** ce fichier est utilisé, et il est nommé dans la réponse même s'il diffère de la résolution automatique

### Requirement: Preuve exigée pour clore une tâche

Le système MUST refuser de passer une tâche à `done` sans note, et MUST refuser une note qui ne contient
aucun indice de vérification. L'indice de vérification MUST être évalué avec le **même motif** que celui
du contrôle de synchronisation (`EVIDENCE_RE` de `scripts/check_sync.py`), et un test MUST échouer si
les deux règles divergent.

#### Scenario: Note absente
- **WHEN** une tâche est passée à `done` sans note
- **THEN** l'opération est refusée et rappelle ce qu'une note doit contenir

#### Scenario: Note sans indice de vérification
- **WHEN** une tâche est passée à `done` avec une note du type « c'est fait »
- **THEN** l'opération est refusée et donne un exemple de note acceptée

#### Scenario: Note avec preuve
- **WHEN** une tâche est passée à `done` avec une note citant un résultat chiffré ou une commande (par exemple « go test ./... : 0 échec »)
- **THEN** l'opération est acceptée et la note est écrite telle quelle dans le suivi

#### Scenario: Divergence des deux règles de preuve
- **WHEN** le motif de preuve du script de contrôle change sans que la règle du système soit mise à jour
- **THEN** le test d'alignement échoue et signale la divergence

### Requirement: Une seule tâche en cours par lot

Le système MUST refuser d'ouvrir une tâche (`doing`) lorsqu'une autre tâche du même lot est déjà en
cours. Deux cas MUST rester autorisés : la tâche en cours est `blocked` et porte une note documentant la
dépendance externe, ou l'ouverture est explicitement forcée avec une raison non vide, consignée dans la
note. Le refus MUST nommer la tâche en cours et l'action qui la débloque.

#### Scenario: Deuxième tâche ouverte dans le même lot
- **WHEN** une tâche est ouverte alors qu'une autre tâche du même lot est déjà `doing` avec une note
- **THEN** l'opération est refusée, la tâche en cours est nommée, et la marche à suivre est indiquée

#### Scenario: Tâche en cours bloquée par une dépendance externe
- **WHEN** une tâche est ouverte alors que la tâche en cours du même lot est `blocked` avec une note
- **THEN** l'ouverture est acceptée

#### Scenario: Ouverture forcée et justifiée
- **WHEN** une tâche est ouverte avec une demande explicite de forçage et une raison non vide
- **THEN** l'ouverture est acceptée et la raison est conservée dans la note

#### Scenario: Travail dans un autre lot
- **WHEN** une tâche est ouverte dans un lot différent de celui de la tâche en cours
- **THEN** l'ouverture est acceptée

### Requirement: Génération du suivi après validation stricte d'un change

Lorsqu'une validation OpenSpec stricte d'un change nommé réussit, le système SHALL générer le suivi de
ce change — et SHALL le **créer** s'il n'existe pas, y compris sa référence dans `docs/README.md`. La
génération MUST préserver les statuts, dates, notes et phases existants. Le déclenchement MUST se
limiter au change nommé : une validation globale ne doit générer aucun fichier.

#### Scenario: Change validé sans suivi
- **WHEN** une validation stricte réussit pour un change qui n'a pas encore de fichier de suivi
- **THEN** le fichier de suivi est créé, la référence est ajoutée à `docs/README.md`, et la sortie de la commande l'annonce

#### Scenario: Suivi existant régénéré
- **WHEN** une validation stricte réussit pour un change qui a déjà un suivi
- **THEN** le suivi est régénéré sans perdre aucun statut, date, note ni état de phase

#### Scenario: Validation globale
- **WHEN** une validation globale (`--all`) réussit
- **THEN** aucun fichier de suivi n'est créé ni régénéré

#### Scenario: Génération en échec
- **WHEN** la génération échoue (par exemple détails de tâche incomplets)
- **THEN** la sortie de la commande signale l'échec et ce qu'il manque, sans la faire échouer

### Requirement: Signalement des écritures directes du suivi et des tâches

Toute écriture directe de `openspec/changes/*/tasks.md` ou d'un fichier de suivi SHALL être suivie de
l'ajout, dans la sortie de l'outil, de l'état de synchronisation du change concerné. L'écriture MUST NOT
être refusée : rédiger les détails techniques et les critères d'acceptation d'une tâche, ou corriger une
formulation, sont des usages normaux.

#### Scenario: Case cochée à la main
- **WHEN** une case est cochée directement dans `tasks.md` sans passer par l'outil de mise à jour
- **THEN** la sortie de l'écriture porte la dérive constatée et la commande de correction

#### Scenario: Détail technique ajouté
- **WHEN** une sous-puce de détail est ajoutée à une tâche sans modifier les cases
- **THEN** la sortie ne signale aucune dérive

#### Scenario: Écriture du suivi généré
- **WHEN** le fichier de suivi est réécrit par la génération
- **THEN** l'état de synchronisation est recalculé sur le fichier écrit, pas sur l'état antérieur

### Requirement: Lecture d'état et rapport de clôture

Le système SHALL exposer une lecture d'état synthétique, en lecture seule et sans effet de bord, et
SHALL pouvoir produire un rapport de clôture d'un chantier sous forme de fichier HTML autonome,
ouvrable hors ligne et imprimable. La lecture d'état MUST signaler au minimum les dérives, les tâches
en cours depuis longtemps et les tâches closes sans preuve.

#### Scenario: État d'un dépôt à plusieurs chantiers
- **WHEN** l'état est demandé
- **THEN** la réponse donne, par chantier, la progression, les dérives et les anomalies constatées, dans un format court

#### Scenario: Aucun effet de bord
- **WHEN** l'état est demandé
- **THEN** aucun fichier n'est créé ni modifié

#### Scenario: Rapport de clôture
- **WHEN** un rapport est demandé pour un chantier
- **THEN** un fichier HTML autonome est écrit dans `docs/`, sans ressource externe, et son chemin est retourné

#### Scenario: Rapport déjà existant
- **WHEN** un rapport est demandé pour un chantier dont le rapport existe déjà
- **THEN** l'écrasement est refusé sans demande explicite

### Requirement: Repli sûr hors périmètre et interrupteur d'urgence

Dans un dépôt sans change OpenSpec ni fichier de suivi reconnu, le système MUST NOT bloquer aucune
action, et MUST signaler son inactivité plutôt que de rester silencieux. Un interrupteur d'urgence MUST
permettre de désactiver tous les blocages sans retirer le plugin ni modifier un fichier versionné.

#### Scenario: Dépôt non reconnu
- **WHEN** un commit est lancé dans un dépôt sans change OpenSpec ni suivi
- **THEN** le commit n'est pas bloqué, et la sortie indique que le contrôle est inactif faute de suivi reconnu

#### Scenario: Mode strict
- **WHEN** le mode strict est activé et que le dépôt n'est pas reconnu
- **THEN** l'action est bloquée avec un message de configuration, au lieu d'être laissée passer

#### Scenario: Interrupteur d'urgence
- **WHEN** l'interrupteur d'urgence est actif dans l'environnement de la commande
- **THEN** aucun blocage n'est appliqué, y compris dans un dépôt reconnu et en mode strict

### Requirement: Scripts de référence uniques et contrôlés

Le système SHALL n'appliquer les règles de synchronisation et de mise à jour qu'à travers les scripts de
référence du dépôt, sans en réimplémenter la logique. Les copies versionnées MUST porter l'indication de
leur source, et un contrôle MUST détecter une divergence : comparaison à la source lorsqu'elle est
disponible, vérification d'intégrité versionnée sinon.

#### Scenario: Divergence détectée sur un poste de travail
- **WHEN** un script vendorisé diffère de sa source
- **THEN** le contrôle échoue en nommant le fichier divergent

#### Scenario: Vérification d'intégrité sans la source
- **WHEN** la source n'est pas disponible (intégration continue)
- **THEN** l'intégrité des copies versionnées est vérifiée et un écart est signalé

#### Scenario: Le système n'invente pas de règle
- **WHEN** une règle de synchronisation ou de preuve est évaluée
- **THEN** elle provient du script de référence, et un test échoue si le système et le script divergent

### Requirement: Un défaut interne du plugin ne fait jamais échouer un outil

Le système MUST distinguer un **refus volontaire** (un gate qui bloque) d'une **erreur interne**
(script absent, sortie illisible, exception). Seul un refus volontaire MUST faire échouer l'opération ;
toute erreur interne MUST être journalisée en une ligne et MUST laisser l'opération se poursuivre.

L'échec d'installation d'un contrôle MUST NOT empêcher les autres contrôles ni les outils de
fonctionner.

#### Scenario: Erreur interne dans un hook après exécution
- **WHEN** un hook d'après-exécution lève une exception inattendue (dépendance manquante, sortie illisible)
- **THEN** l'appel d'outil se termine normalement, et une ligne de journal nomme le hook et l'erreur

#### Scenario: Refus volontaire
- **WHEN** un gate refuse une action (commit en dérive)
- **THEN** l'opération échoue avec le message du refus, et ce message atteint l'appelant

#### Scenario: Installation partielle
- **WHEN** l'installation d'un contrôle échoue au chargement
- **THEN** les autres contrôles et les six outils restent disponibles, et l'échec est journalisé

### Requirement: Les commandes externes sont bornées dans le temps

Toute commande lancée par le plugin (`python3`, `git`) MUST être bornée par un délai configurable
(défaut dix secondes). À l'expiration, le processus MUST être arrêté et le résultat MUST porter un code
et un message explicites. Un dépassement MUST être traité comme une erreur interne, sauf pour le
contrôle de commit, où il MUST produire un refus explicite.

#### Scenario: Script bloqué
- **WHEN** un script lancé par un outil ne rend pas la main avant le délai
- **THEN** il est arrêté, l'outil rend un message de dépassement, et la session n'est pas gelée

#### Scenario: Dépassement pendant un commit
- **WHEN** le contrôle de synchronisation dépasse le délai au moment d'un commit
- **THEN** le commit est refusé avec un message qui distingue le dépassement d'une dérive

### Requirement: Un contrôle de santé répond sans lire les journaux

Le système SHALL exposer une lecture de santé en **lecture seule** qui donne, en une commande : la
version du plugin, le périmètre détecté, la configuration effective, la présence des scripts et des
gabarits, l'état du hook git, la dette gelée et le binaire Python utilisé. Elle MUST conclure par un
verdict et les actions à mener.

#### Scenario: Installation incomplète
- **WHEN** un script de référence ou un gabarit manque
- **THEN** le contrôle de santé le nomme, conclut « à corriger » et indique la commande de vendorisation

#### Scenario: Installation saine
- **WHEN** tout est présent et le hook git est installé
- **THEN** le contrôle conclut « prêt » sans modifier aucun fichier

### Requirement: La dette historique est gelée et datée

Les problèmes existants (changes sans suivi, tâches closes sans preuve) MUST pouvoir être figés dans
un fichier versionné, daté. La lecture d'état MUST distinguer les problèmes **nouveaux** des problèmes
**connus**, et MUST rappeler en une ligne le nombre et la date de la dette gelée.

#### Scenario: Dette gelée
- **WHEN** la baseline contient six changes sans suivi et qu'aucun nouveau problème n'apparaît
- **THEN** l'état annonce zéro nouvelle dérive et rappelle les six connues avec leur date

#### Scenario: Nouveau problème
- **WHEN** un change est ajouté sans suivi après la date de la baseline
- **THEN** il est compté comme nouvelle dérive, distinctement de la dette gelée

### Requirement: Le comportement par défaut ne dépend d'aucun projet

Sans configuration, le nom de projet MUST être déduit du dépôt courant, et le binaire Python MUST être
choisi selon la plateforme. Aucun défaut MUST citer un projet particulier.

#### Scenario: Dépôt sans configuration
- **WHEN** un suivi est généré dans un dépôt dont le nom n'est pas configuré
- **THEN** le titre et l'en-tête portent le nom du dépôt, jamais celui d'un autre projet

#### Scenario: Plateforme Windows
- **WHEN** le plugin s'exécute sur Windows sans `pythonBin` configuré
- **THEN** le binaire `python` est utilisé, et le contrôle de santé l'affiche

### Requirement: Les règles du plugin sont vérifiées en intégration continue

Les tests du plugin et le typecheck MUST s'exécuter en intégration continue, sur plusieurs versions de
Node. Un harnais MUST exercer le **câblage complet** (chargement du module, enregistrement des hooks,
décisions de blocage et d'autorisation) sans dépendre d'un serveur OpenCode. La version du plugin MUST
être explicite, et une montée de la dépendance d'API MUST exiger cette vérification.

#### Scenario: Export par défaut manquant
- **WHEN** le module n'exporte pas une définition par défaut avec un identifiant et une fonction d'initialisation
- **THEN** la CI échoue

#### Scenario: Câblage cassé
- **WHEN** un hook n'est plus enregistré par l'initialisation
- **THEN** le harnais d'intégration échoue, même si les tests unitaires du hook passent

#### Scenario: Concurrence d'écriture
- **WHEN** un tiers modifie le suivi ou `tasks.md` pendant une mise à jour
- **THEN** l'opération le signale et invite à rejouer, au lieu d'écraser silencieusement

