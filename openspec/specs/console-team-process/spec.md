# console-team-process Specification

## Purpose
TBD - created by archiving change console-sdlc. Update Purpose after archive.
## Requirements
### Requirement: Métriques d'équipe

Le système SHALL calculer par personne canonique et par dépôt : commits, MR, revues,
approbations, lignes modifiées, dernière activité et part assistée par IA. Les bots SHALL
être exclus. Une donnée absente SHALL être affichée « non mesuré ».

#### Scenario: Métriques d'un contributeur
- **WHEN** un contributeur a des commits dans deux dépôts
- **THEN** ses commits sont comptés une fois par dépôt et une fois dans le total dédupliqué
- **AND** sa part assistée par IA est calculée depuis les trailers

#### Scenario: Donnée absente
- **WHEN** aucun trailer IA n'est présent
- **THEN** la part assistée par IA affiche « non mesuré »
- **AND** aucune estimation n'est inventée

#### Scenario: Chaîne de validation
- **WHEN** la vue Équipe est affichée
- **THEN** la chaîne auteur → relecteur agent → humain est affichée
- **AND** les taux de revues agent et d'approbations humaines sont visibles

### Requirement: Bus factor et propriété

Le système SHALL calculer le bus factor par zone en cumulant les commits des personnes
canoniques jusqu'à 50 %, et SHALL afficher le propriétaire principal, le secondaire et une
alerte lorsque le bus factor vaut 1.

#### Scenario: Zone à bus factor 1
- **WHEN** une seule personne représente plus de 50 % des commits de la zone Billing
- **THEN** le bus factor affiché est 1
- **AND** la zone est signalée comme risque

### Requirement: Détection de processus

Le système SHALL détecter un profil de processus (GitHub Flow, Git Flow, trunk-based,
GitLab Flow) à partir des branches, merges, tags, protections et fichiers de CI, et SHALL
afficher les signaux observés, leur interprétation et un score de confiance heuristique.

#### Scenario: GitHub Flow avec releases
- **WHEN** le dépôt n'a pas de branche `develop`, a des tags semver et 80 % de squash
- **THEN** le profil « GitHub Flow + releases » est proposé
- **AND** la confiance et les signaux sont affichés

#### Scenario: Processus non identifiable
- **WHEN** le dépôt n'a ni tags, ni branches de flux, ni historique exploitable
- **THEN** le profil est « non identifiable »
- **AND** les raisons sont affichées
- **AND** aucune heuristique n'est inventée

### Requirement: Flux de processus avec gates

Le système SHALL afficher le flux de développement avec les gates : feature → MR → revue →
main, release → tag → préprod → recette → go/no-go → prod, hotfix → tests/sécurité → prod.

#### Scenario: Flux affiché avec ses gates
- **WHEN** l'utilisateur ouvre la vue Processus
- **THEN** le flux feature, release et hotfix est affiché
- **AND** les gates recette et go/no-go sont positionnés sur le flux
- **AND** chaque gate est cliquable vers sa preuve

### Requirement: Processus par dépôt et agrégation

Le système SHALL calculer un profil par dépôt, afficher le profil dominant au niveau projet
et signaler les divergences sans moyenne pondérée inventée.

#### Scenario: Dépôts divergents
- **WHEN** un dépôt est en GitHub Flow et l'autre en Git Flow
- **THEN** la vue projet affiche les deux profils
- **AND** elle signale la divergence

### Requirement: Surcharge de processus

Le système SHALL permettre une surcharge manuelle du profil, datée, motivée et auditée.

#### Scenario: Surcharge auditée
- **WHEN** l'utilisateur force le profil « Git Flow »
- **THEN** la surcharge est datée et motivée
- **AND** l'audit enregistre l'acteur et la raison

### Requirement: Métriques DORA

Le système SHALL calculer le lead time, la fréquence de déploiement, le change failure rate
et le MTTR, avec la fenêtre et la source affichées. Une métrique non mesurable SHALL être
affichée « non mesuré ».

#### Scenario: MTTR depuis les incidents
- **WHEN** un incident est présent dans `docs/incidents/*.md`
- **THEN** le MTTR est calculé depuis la date de début et de retour à la normale
- **AND** la source est affichée

### Requirement: Corpus de processus

Le système SHALL fournir un corpus de dépôts étiquetés et une commande de mesure de la
précision de détection, avec un rapport listant le taux et les échecs.

#### Scenario: Mesure de précision
- **WHEN** `sdlc-console process corpus <chemin>` est exécuté
- **THEN** le rapport contient le taux de classification
- **AND** la liste des dépôts mal classés

