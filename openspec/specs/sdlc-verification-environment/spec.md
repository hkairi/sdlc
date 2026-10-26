# sdlc-verification-environment Specification

## Purpose
TBD - created by archiving change containerize-sdlc-verification. Update Purpose after archive.
## Requirements
### Requirement: Reproducible Verification Toolchain

Les contrôles de la chaîne d'agents SHALL pouvoir s'exécuter dans une image dont
les versions sont épinglées : Ruby 3.4.11, Go 1.26, Node 22, OpenSpec 0.18.0.
Aucun contrôle MUST NOT dépendre de la version de Node, de Ruby ou du client
PostgreSQL installés sur la machine de l'agent.

#### Scenario: Chaîne vérifiée dans le conteneur

- **WHEN** `make sdlc-check` est exécuté sur une machine dont le Node local est
  cassé
- **THEN** `openspec validate --all --strict`, `check_sync.py`,
  `learnings.py --check` et `handoff_check.py` SHALL s'exécuter dans l'image
  épinglée
- **AND** le résultat MUST NOT dépendre du toolchain de l'hôte

#### Scenario: Version d'OpenSpec figée

- **WHEN** l'image est construite
- **THEN** la version d'`@fission-ai/openspec` SHALL être passée en argument de
  build, jamais `@latest`
- **AND** la même version MUST NOT être installée implicitement par un
  `npx` au moment du contrôle

### Requirement: Isolated Verification Services

Postgres et Faktory nécessaires aux tests SHALL être fournis par le compose du
SDLC, sur des ports qui ne heurtent pas une installation locale, et la base de
test MUST NOT persister entre deux exécutions.

#### Scenario: Postgres jetable

- **WHEN** `make sdlc-check-db` démarre les services
- **THEN** Postgres SHALL écouter sur `127.0.0.1:5433` côté hôte
- **AND** ses données MUST NOT survivre à un `make sdlc-down`

#### Scenario: Faktory disponible pour les tests Go

- **WHEN** les tests de `engagement-api/internal/server` s'exécutent dans le
  conteneur
- **THEN** Faktory SHALL être joignable sur le réseau du compose
- **AND** le digest de l'image SHALL être celui utilisé par la CI

### Requirement: Orchestration Stays On The Host

L'orchestration (agents, plugin, hooks) MUST NOT être déplacée dans le
conteneur : elle partage le système de fichiers, git et l'éditeur de l'agent.

#### Scenario: Contrôle depuis la session

- **WHEN** un agent lance un contrôle
- **THEN** le processus agent SHALL rester sur l'hôte
- **AND** seuls les outils de vérification SHALL être exécutés dans l'image

### Requirement: Explicit Failure Without Docker

Si Docker est indisponible, les cibles SHALL échouer avec un message explicite
plutôt que d'exécuter silencieusement les contrôles sur l'hôte avec un toolchain
non épinglé.

#### Scenario: Docker arrêté

- **WHEN** `make sdlc-check` est lancé sans démon Docker
- **THEN** la cible SHALL échouer en nommant Docker
- **AND** elle MUST NOT retomber silencieusement sur les binaires de l'hôte

