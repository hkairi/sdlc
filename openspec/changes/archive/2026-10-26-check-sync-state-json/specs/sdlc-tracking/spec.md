## MODIFIED Requirements

### Requirement: Synchronisation appliquée dans la session

Un commit lancé par l'agent SHALL être refusé tant que `docs/suivi/state.json` et `tasks.md`
divergent pour les changes touchés par ce commit. Le refus MUST nommer les écarts et la correction à
jouer, et MUST provenir du même contrôle que celui du hook git et de la CI
(`scripts/check_sync.py`), afin qu'un verdict « synchrone » dans la session ne soit jamais contredit
par un refus au commit.

Le contrôle MUST s'appliquer uniquement aux chemins touchés par le commit lorsqu'il peut les
déterminer, et MUST se replier sur l'ensemble des changes ouverts sinon. Un chemin
`docs/suivi/state.json` est un **suivi global** : il déclenche le contrôle de tous les changes ouverts.

#### Scenario: Commit avec un état désynchronisé

- **WHEN** l'agent lance `git commit` alors qu'une case de `tasks.md` est cochée sans que la tâche de `state.json` soit à `done`
- **THEN** le commit est refusé, le message nomme la tâche et les deux fichiers en cause, et indique la commande de correction

#### Scenario: Commit avec un état synchrone

- **WHEN** l'agent lance `git commit` alors que `state.json` des changes touchés est synchrone avec `tasks.md`
- **THEN** le commit n'est pas refusé, et le verdict de synchronisation est ajouté à la sortie

#### Scenario: Verdict identique au gate hors session

- **WHEN** le même ensemble de chemins est contrôlé dans la session puis par `.githooks/pre-commit` ou la CI
- **THEN** les deux verdicts sont identiques (même code de sortie, mêmes écarts listés)

#### Scenario: Écriture directe de state.json

- **WHEN** `docs/suivi/state.json` est écrit directement sans passer par l'outil de mise à jour
- **THEN** la sortie de l'écriture porte l'état de synchronisation des changes concernés

#### Scenario: State.json absent

- **WHEN** le contrôle est lancé dans un dépôt qui a des `tasks.md` mais pas de `docs/suivi/state.json`
- **THEN** il échoue (code 2) avec un message orientant vers `migrate_from_html.py`, jamais un passage silencieux

#### Scenario: Change sans feature dans state.json

- **WHEN** un change ouvert n'a pas de feature correspondante dans `state.json`
- **THEN** le contrôle signale un problème (« tasks.md présent mais feature absente de state.json »)

### Requirement: Scripts de référence uniques et contrôlés

Le système SHALL n'appliquer les règles de synchronisation, de mise à jour et de génération qu'à
travers les scripts de référence de la skill `suivi-taches` (`track.py`, `track_phase.py`,
`generate.py`, `state_io.py`, `check_sync.py`), sans en réimplémenter la logique. Le script
`check_sync.py` lit `state.json` (source de vérité), jamais le HTML. La copie versionnée de
`check_sync.py` MUST porter l'indication de sa source (la skill), et un contrôle MUST détecter une
divergence.

#### Scenario: Le contrôle lit la source de vérité

- **WHEN** la synchronisation est évaluée
- **THEN** elle compare `state.json` à `tasks.md`, et un test échoue si le contrôle et la source divergent

#### Scenario: Copie vendorisée divergent de sa source

- **WHEN** `scripts/check_sync.py` diffère de `.agents/skills/suivi-taches/scripts/check_sync.py`
- **THEN** le contrôle le signale en nommant le fichier divergent

#### Scenario: Version de schéma non reconnue

- **WHEN** `state.json` porte un `schema` différent de 1
- **THEN** le contrôle échoue (code 2) avec un message explicite, sans lecture silencieuse

#### Scenario: JSON illisible

- **WHEN** `state.json` est invalide ou illisible
- **THEN** le contrôle échoue (code 2) avec un message clair
