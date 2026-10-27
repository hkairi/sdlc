# console-review Specification

## Purpose
TBD - created by archiving change console-sdlc. Update Purpose after archive.
## Requirements
### Requirement: Indépendance de la revue

Le système SHALL sélectionner le relecteur éligible au niveau d'indépendance maximal
disponible et SHALL afficher le niveau : complète (agent, modèle et famille différents),
partielle (agent et modèle différents) ou dégradée. Une revue dégradée SHALL exiger une
dérogation humaine explicite et auditée.

#### Scenario: Relecteur indépendant
- **WHEN** un auteur utilise l'agent A et le modèle M1
- **AND** un relecteur B utilise le modèle M2 d'une autre famille
- **THEN** l'indépendance est affichée « complète »
- **AND** la revue peut être lancée

#### Scenario: Relecteur du même modèle
- **WHEN** seul un relecteur du même modèle que l'auteur est disponible
- **THEN** l'interface explique le blocage et propose un autre modèle
- **AND** aucune revue n'est lancée sans dérogation humaine

#### Scenario: Dérogation d'indépendance
- **WHEN** une dérogation humaine motivée est enregistrée
- **THEN** l'indépendance est affichée « dégradée »
- **AND** la dérogation est auditée

### Requirement: Paquet de revue aveugle

Le système SHALL construire un paquet de revue contenant la spec, le diff, les preuves des
gates et les ADR concernés, sans le récit de l'auteur, et SHALL le rendre téléchargeable et
traçable.

#### Scenario: Paquet aveugle
- **WHEN** une revue est préparée
- **THEN** le paquet contient la spec, le diff, les preuves et les ADR
- **AND** il ne contient pas le résumé de l'auteur
- **AND** son empreinte est enregistrée

### Requirement: Rapport de revue structuré

Le système SHALL produire un rapport de revue conforme à un schéma JSON : verdict, findings
typés (catégorie, sévérité, confiance, preuve, impact, correctif minimal), éléments non
vérifiés, décisions humaines et options. Chaque finding SHALL citer une preuve.

#### Scenario: Rapport valide
- **WHEN** la revue se termine
- **THEN** le rapport valide `review.schema.json`
- **AND** chaque finding cite un fichier, une ligne ou une commande

#### Scenario: Finding sans preuve
- **WHEN** un finding ne cite aucune preuve
- **THEN** le rapport est rejeté
- **AND** la revue est marquée incomplète

### Requirement: Fiche de décision

Le système SHALL produire une fiche de décision lisible : verdict, confiance, trois
bloquants maximum, matrice de risque, éléments non vérifiés, questions humaines, options
avec coût et risque, recommandation.

#### Scenario: Fiche de décision
- **WHEN** une revue est terminée
- **THEN** la fiche tient sur une page
- **AND** elle contient au plus trois bloquants avec correctif minimal
- **AND** elle propose des options chiffrées en effort et en risque

### Requirement: Décision humaine auditée

Le système SHALL permettre à l'humain d'approuver, d'approuver avec conditions, de rejeter
ou de demander une information. La décision SHALL être enregistrée avec acteur, date, motif
et portée, et SHALL être auditée.

#### Scenario: Approbation avec conditions
- **WHEN** l'humain approuve avec conditions
- **THEN** les conditions sont enregistrées
- **AND** l'audit contient l'acteur, la date et le motif
- **AND** la tâche reste bloquée jusqu'à la levée des conditions

#### Scenario: Acteur non authentifié
- **WHEN** la décision est prise depuis le poste local sans authentification
- **THEN** l'audit mentionne « décision depuis le poste local, non authentifiée »
- **AND** la limite de non-répudiation est visible

### Requirement: Préflight et lancement d'agent

Le système SHALL lancer un exécutant ou un relecteur depuis l'interface uniquement via un
modèle de commande configuré, après un préflight vérifiant la CLI, le modèle, le dépôt, le
budget et la durée. La commande exacte SHALL être affichée avant confirmation.

#### Scenario: Préflight bloquant
- **WHEN** la CLI est absente ou le budget dépasse le plafond du projet
- **THEN** le lancement est refusé avant exécution
- **AND** la cause est affichée
- **AND** aucune ligne de run n'est créée

#### Scenario: Commande libre refusée
- **WHEN** une commande arbitraire est soumise
- **THEN** elle est refusée et auditée
- **AND** seul un modèle configuré peut être exécuté

### Requirement: Cycle de vie et annulation d'un run

Le système SHALL utiliser les statuts fermés `queued`, `running`, `done`, `failed`,
`timeout` et `cancelled`, et SHALL annuler tout l'arbre de processus d'un run.

#### Scenario: Annulation d'un run en cours
- **WHEN** l'utilisateur annule un run `running`
- **THEN** le groupe de processus reçoit un signal
- **AND** le statut passe à `cancelled`
- **AND** aucun processus fils ne survit

#### Scenario: Annulation d'un run en file
- **WHEN** l'utilisateur annule un run `queued`
- **THEN** le statut passe à `cancelled`
- **AND** aucun processus n'est lancé

#### Scenario: Crash ou timeout
- **WHEN** le processus plante ou dépasse la durée maximale
- **THEN** le statut passe à `failed` ou `timeout` avec la cause
- **AND** les logs sont conservés
- **AND** le coût réel est affiché

### Requirement: Budget et coût d'un run

Le système SHALL estimer la consommation d'un run à cadence configurable, arrêter le run au
plafond estimé, afficher le coût réel et signaler tout dépassement sans le masquer.

#### Scenario: Plafond atteint
- **WHEN** le coût estimé atteint le budget de 2 €
- **THEN** le run est arrêté avec le statut `failed` et la cause `budget_exceeded`
- **AND** le coût réel est affiché
- **AND** un éventuel dépassement est signalé

### Requirement: Escalade après rejets

Le système SHALL escalader une tâche après `max_iterations` rejets : la tâche passe en
`blocked`, l'humain est notifié et les itérations sont conservées dans l'audit.

#### Scenario: Trois rejets
- **WHEN** une tâche est rejetée trois fois
- **THEN** la tâche passe en `blocked`
- **AND** l'humain est notifié
- **AND** les trois itérations restent consultables dans l'audit

#### Scenario: Dépassement du temps de tâche
- **WHEN** une tâche dépasse `task_timeout_min`
- **THEN** elle passe en `blocked`
- **AND** l'humain est notifié
- **AND** l'événement est audité

### Requirement: Journal des runs et indépendance

Le système SHALL afficher la liste des runs (agent, rôle, modèle, tâche, statut, durée,
coût, tokens) avec filtres, et SHALL afficher le taux de revues dont le modèle diffère de
celui de l'auteur sur une fenêtre glissante de 30 jours. Au seuil configuré (défaut 10 % de
revues dégradées, atteint ou dépassé), une décision humaine SHALL être exigée.

Le journal SHALL être l'union des runs ingérés (`runs.jsonl`, origine `ingérée`) et des
runs lancés depuis l'interface (origine `lancée`), dédupliqués par `run_id`. Le taux
d'indépendance SHALL être calculé sur cette union.

#### Scenario: Journal filtrable
- **WHEN** l'utilisateur filtre les runs par agent, rôle et statut
- **THEN** seuls les runs correspondants sont affichés
- **AND** le coût et les tokens sont visibles

#### Scenario: Deux provenances de runs
- **WHEN** un même run apparaît dans `runs.jsonl` et a été lancé depuis l'interface
- **THEN** il n'est compté qu'une fois dans le journal
- **AND** son origine est affichée
- **AND** le taux d'indépendance est calculé sur l'union dédupliquée

#### Scenario: Seuil d'indépendance dépassé
- **WHEN** plus de 10 % des revues sont dégradées
- **THEN** la vue Agents IA le signale
- **AND** une décision humaine est exigée et auditée

### Requirement: Concurrence et reprise après crash

Le système SHALL limiter la concurrence par agent et par projet, mettre les runs excédentaires
en `queued`, et, au démarrage, passer tout run orphelin `queued`/`running` dans un état
terminal explicite avec la cause. Une ingestion interrompue SHALL rester rejouable sans doublon.

#### Scenario: Troisième run simultané
- **WHEN** un troisième run est demandé alors que la limite est de deux
- **THEN** il est placé en `queued`
- **AND** il démarre lorsqu'un slot se libère

#### Scenario: Redémarrage après crash
- **WHEN** le serveur redémarre avec un run `running`
- **THEN** le run passe à `failed` avec la cause `server_restart`
- **AND** l'ingestion partielle est rejouable sans doublon

### Requirement: Environnement et lecture seule

Le système SHALL purger du processus agent les jetons et secrets du serveur, SHALL
appliquer la lecture seule pour une revue, et SHALL refuser toute écriture Git.

#### Scenario: Jeton non hérité
- **WHEN** un run est lancé
- **THEN** l'environnement du processus ne contient aucun jeton GitHub/GitLab
- **AND** une tentative de lecture de secret est refusée

#### Scenario: Écriture Git refusée
- **WHEN** un agent tente une commande Git en écriture
- **THEN** la commande est refusée
- **AND** la tentative est auditée

### Requirement: Logs d'agent échappés

Le système SHALL afficher les logs d'agent en texte échappé, jamais en HTML interprété, et
SHALL diffuser leur mise à jour sans déplacer le focus.

#### Scenario: Log contenant du HTML
- **WHEN** un log contient `<script>alert(1)</script>`
- **THEN** le texte est affiché littéralement
- **AND** aucun script n'est exécuté

