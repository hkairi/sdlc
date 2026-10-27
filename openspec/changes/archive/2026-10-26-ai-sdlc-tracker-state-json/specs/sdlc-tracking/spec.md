## MODIFIED Requirements

### Requirement: Cible résolue et annoncée

Le système SHALL déterminer seul la feature concernée par un change à partir de
`docs/suivi/state.json` (`features[].id` aligné sur `openspec/changes/<id>/`), et MUST annoncer le
fichier modifié. Le HTML n'est plus une source de vérité : il n'est ni lu ni écrit. Cette annonce
est obligatoire : une mise à jour appliquée au mauvais chantier ne doit pas pouvoir passer pour un
succès.

#### Scenario: Chantier suivi dans state.json

- **WHEN** une tâche est mise à jour pour un change dont `state.json` contient une `feature.id` correspondante
- **THEN** la feature est résolue et le fichier `docs/suivi/state.json` est nommé dans la réponse

#### Scenario: Change sans feature dans state.json

- **WHEN** une tâche est mise à jour pour un change absent de `state.json`
- **THEN** l'opération est refusée et la réponse liste les identifiants candidats

### Requirement: Mise à jour d'une tâche en une seule opération

Le système SHALL permettre de mettre à jour une tâche — statut, date, note, rôles — et la case
correspondante de `tasks.md` en **une seule** opération, via les scripts de référence `suivi-taches`.
L'opération MUST refuser une tâche inconnue sans modifier aucun fichier, et MUST écrire `state.json`
de façon atomique.

#### Scenario: Une tâche close

- **WHEN** une tâche est mise à `done` avec une note
- **THEN** `state.json` porte `status="done"`, sa date et sa note, et la case de `tasks.md` est cochée dans le même geste

#### Scenario: Une tâche rouverte

- **WHEN** une tâche déjà `done` est ramenée à `doing`, `blocked` ou `todo`
- **THEN** la case de `tasks.md` est décochée et le statut de `state.json` est mis à jour dans le même geste

#### Scenario: Tâche inconnue

- **WHEN** l'identifiant de tâche n'existe ni dans `state.json` ni dans `tasks.md`
- **THEN** aucun fichier n'est modifié et la réponse liste les identifiants candidats

### Requirement: Génération du suivi après validation stricte d'un change

Lorsqu'une validation OpenSpec stricte d'un change nommé réussit, le système SHALL déclencher la
génération du suivi de ce change en déléguant au script `generate.py` de la skill `suivi-taches`
(qui lit `state.json` et écrit le HTML), et SHALL le **créer** s'il n'existe pas, y compris sa
référence dans `docs/README.md`. La génération MUST préserver les statuts, dates, notes et phases
existants de `state.json`. Le déclenchement MUST se limiter au change nommé : une validation globale
ne doit générer aucun fichier.

#### Scenario: Change validé sans suivi

- **WHEN** une validation stricte réussit pour un change qui n'a pas encore d'entrée dans `state.json`
- **THEN** la génération est déléguée à `generate.py`, l'entrée et le fichier de suivi sont créés, et la sortie l'annonce

#### Scenario: Suivi existant régénéré

- **WHEN** une validation stricte réussit pour un change déjà présent dans `state.json`
- **THEN** le suivi est régénéré sans perdre aucun statut, date, note ni état de phase

#### Scenario: Validation globale

- **WHEN** une validation globale (`--all`) réussit
- **THEN** aucun fichier de suivi n'est créé ni régénéré

#### Scenario: Génération en échec

- **WHEN** la génération déléguée à `generate.py` échoue (par exemple détails de tâche incomplets)
- **THEN** la sortie de la commande signale l'échec et ce qu'il manque, sans faire échouer la validation

### Requirement: Signalement des écritures directes du suivi et des tâches

Toute écriture directe de `openspec/changes/*/tasks.md` ou de `docs/suivi/state.json` SHALL être
suivie de l'ajout, dans la sortie de l'outil, de l'état de synchronisation du change concerné.
L'écriture MUST NOT être refusée : rédiger les détails techniques et les critères d'acceptation
d'une tâche, ou corriger une formulation, sont des usages normaux.

#### Scenario: Case cochée à la main

- **WHEN** une case est cochée directement dans `tasks.md` sans passer par l'outil de mise à jour
- **THEN** la sortie de l'écriture porte la dérive constatée entre `tasks.md` et `state.json`, et la commande de correction

#### Scenario: Détail technique ajouté

- **WHEN** une sous-puce de détail est ajoutée à une tâche sans modifier les cases
- **THEN** la sortie ne signale aucune dérive

### Requirement: Repli sûr hors périmètre et interrupteur d'urgence

Dans un dépôt sans change OpenSpec ni `docs/suivi/state.json` reconnu, le système MUST NOT bloquer
aucune action, et MUST signaler son inactivité plutôt que de rester silencieux. Un interrupteur
d'urgence MUST permettre de désactiver tous les blocages sans retirer le plugin ni modifier un
fichier versionné.

#### Scenario: Dépôt non reconnu

- **WHEN** un commit est lancé dans un dépôt sans change OpenSpec ni `state.json`
- **THEN** le commit n'est pas bloqué, et la sortie indique que le contrôle est inactif faute de suivi reconnu

#### Scenario: Mode strict

- **WHEN** le mode strict est activé et que le dépôt n'est pas reconnu
- **THEN** l'action est bloquée avec un message de configuration, au lieu d'être laissée passer

#### Scenario: Interrupteur d'urgence

- **WHEN** l'interrupteur d'urgence est actif dans l'environnement de la commande
- **THEN** aucun blocage n'est appliqué, y compris dans un dépôt reconnu et en mode strict

### Requirement: Scripts de référence uniques et contrôlés

Le système SHALL n'appliquer les règles de synchronisation, de mise à jour et de génération qu'à
travers les scripts de référence de la skill `suivi-taches` (`track.py`, `track_phase.py`,
`generate.py`, `state_io.py`, `check_sync.py`), sans en réimplémenter la logique. L'invocation MUST
résoudre le chemin sous le répertoire de la skill et MUST refuser tout chemin hors périmètre. Les
copies versionnées MUST porter l'indication de leur source, et un contrôle MUST détecter une
divergence.

#### Scenario: Divergence détectée sur un poste de travail

- **WHEN** un script de référence diffère de sa source
- **THEN** le contrôle échoue en nommant le fichier divergent

#### Scenario: Le système n'invente pas de règle

- **WHEN** une règle de synchronisation ou de preuve est évaluée
- **THEN** elle provient du script de référence, et un test échoue si le système et le script divergent

#### Scenario: Chemin de script hors périmètre

- **WHEN** la configuration pointe vers un script hors du répertoire de la skill `suivi-taches`
- **THEN** l'invocation est refusée (erreur interne journalisée), jamais exécutée

## ADDED Requirements

### Requirement: Source de vérité unique dans state.json

Le système SHALL lire l'état du suivi dans `docs/suivi/state.json` (schéma 1) et MUST considérer le
HTML (`docs/suivi-*.html`) comme un rendu généré, jamais comme une source de vérité. Tout champ
inconnu vaut `null` et ne doit jamais être inventé.

#### Scenario: HTML présent mais state.json absent

- **WHEN** un dépôt contient un ancien `docs/suivi-*.html` mais pas `docs/suivi/state.json`
- **THEN** le plugin reste inerte (fail-open) et signale que le modèle `state.json` est attendu

#### Scenario: État lu sans effet de bord

- **WHEN** l'état est lu
- **THEN** aucun fichier n'est créé ni modifié

#### Scenario: Version de schéma non reconnue

- **WHEN** `state.json` porte un `schema` différent de `1`
- **THEN** le plugin reste inerte et signale la version non reconnue, sans lire les champs

#### Scenario: JSON illisible

- **WHEN** `state.json` est invalide ou illisible
- **THEN** l'erreur est traitée comme une erreur interne (journalisée, fail-open), jamais comme un refus volontaire

### Requirement: Relecteur différent de l'auteur

Le système SHALL appliquer la règle « relecteur ≠ auteur » : une tâche ne peut être close (`done`)
avec un `reviewer` identique à l'`executor`, ni avec un `reviewer` **absent**. Le système MUST
exposer les rôles (`executor`, `reviewer`, `review_iteration`, `escalated`, `ready_to_commit`,
`commit_message`) et MUST signaler l'escalade lorsque l'itération dépasse
`organisation.max_review_iterations`.

#### Scenario: Relecteur identique à l'auteur

- **WHEN** une tâche passe à `done` alors que `reviewer` est défini et égal à `executor`
- **THEN** l'opération est refusée (ou signalée en mode non strict) et la règle est rappelée

#### Scenario: Relecteur absent

- **WHEN** une tâche passe à `done` sans `reviewer` assigné (`null` ou absent)
- **THEN** l'opération est refusée (ou signalée en mode non strict) avec l'indication d'assigner un relecteur distinct de l'auteur

#### Scenario: Relecteur distinct

- **WHEN** une tâche passe à `done` avec un `reviewer` différent de l'`executor`
- **THEN** l'opération est acceptée

#### Scenario: Itérations et escalade

- **WHEN** `review_iteration` dépasse `organisation.max_review_iterations`
- **THEN** la tâche passe `blocked` et `escalated` est mis à `true`
