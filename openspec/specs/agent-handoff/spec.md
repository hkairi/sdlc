# agent-handoff Specification

## Purpose

Définir le passage de relais entre les agents d'un change OpenSpec : un artefact versionné par étape
(`handoff/`), une preuve qui doit être une commande exécutée, des portes qui refusent une tâche cochée
sans couverture, un routage de modèle par étape, et des permissions qui rendent AGENTS.md mécanique
plutôt que déclaratif.
## Requirements
### Requirement: Handoff As The Sole Channel

Chaque étape de la chaîne d'agents SHALL produire un artefact versionné dans
`openspec/changes/<id>/handoff/`, nommé `NN-<stage>.md` (`10-spec`, `20-impl`,
`30-test`, `40-review`, `45-learn`, `50-close`), portant un frontmatter TOML
complet. Un agent MUST NOT dépendre du résumé d'une conversation pour connaître
l'état de l'étape précédente.

#### Scenario: Un sous-agent reprend une étape

- **WHEN** un sous-agent démarre une étape
- **THEN** son entrée SHALL être le dossier `handoff/` du change, `tasks.md` et
  les deltas de spec
- **AND** aucune information nécessaire MUST NOT exister uniquement dans
  l'historique de conversation

#### Scenario: Une étape sans travail produit quand même son artefact

- **WHEN** une étape n'a rien à modifier
- **THEN** elle SHALL écrire son artefact avec `status = "ready"` et une preuve
  de ce qu'elle a contrôlé
- **AND** l'absence d'artefact MUST NOT être interprétée comme un succès

### Requirement: Evidence Must Be Executed

Un artefact `ready` SHALL citer au moins une preuve composée d'une commande et
d'un résultat observable (chiffre ou verdict explicite). Pour les étapes `impl`
et `test`, la commande MUST correspondre au champ `Tests :` d'une des tâches
couvertes par l'artefact.

#### Scenario: Preuve exécutée

- **WHEN** `20-impl.md` déclare une tâche `2.1` dont le champ `Tests :` est
  `bundle exec rspec spec/x_spec.rb`
- **THEN** son entrée `evidence` SHALL citer cette commande avec un résultat
  contenant un nombre d'exemples ou d'échecs
- **AND** une affirmation sans commande MUST être refusée

#### Scenario: Preuve étrangère à la tâche

- **WHEN** l'artefact cite une commande absente du champ `Tests :` de toutes
  les tâches couvertes
- **THEN** `handoff_check.py` SHALL refuser l'artefact en nommant la commande

### Requirement: Stage Gating And Rework

Aucune étape MUST NOT démarrer avant que l'artefact de l'étape précédente ne
soit `status = "ready"`. Un rejet de revue SHALL rouvrir les tâches concernées
et produire une nouvelle révision de l'étape rejetée, sans supprimer
l'artefact précédent.

#### Scenario: Revue qui rejette

- **WHEN** `40-review.md` porte `status = "rejected"` et au moins un finding
- **THEN** l'orchestrateur SHALL repasser les tâches visées en `todo` via
  `sdlc_track`
- **AND** l'étape `impl` SHALL être rejouée en `20-impl-r2.md`

#### Scenario: Rejet sans motif

- **WHEN** un artefact porte `status = "rejected"` sans `findings`
- **THEN** `handoff_check.py` SHALL le refuser

### Requirement: Task Done Requires Handoff Coverage

Toute tâche cochée dans `tasks.md` SHALL être couverte par un artefact `ready`
du handoff. Une tâche appartenant à une section de cadrage ne peut être couverte
que par l'artefact `spec`.

#### Scenario: Tâche cochée sans artefact

- **WHEN** `tasks.md` porte `- [x] 2.2` et qu'aucun artefact `ready` ne liste
  `2.2`
- **THEN** `handoff_check.py` SHALL échouer avec un message nommant `2.2`

### Requirement: Per-Stage Model Routing

Chaque agent SHALL avoir un modèle explicitement configuré et un mode
(`primary` ou `subagent`). L'orchestrateur MUST NOT pouvoir lancer un agent
hors de la chaîne déclarée.

#### Scenario: Chargement de la chaîne

- **WHEN** `opencode debug agents` est exécuté
- **THEN** les sept agents de la chaîne SHALL apparaître avec leur modèle et
  leur mode
- **AND** l'orchestrateur SHALL lister exactement `spec`, `impl`, `test`,
  `review`, `learn`, `docs` comme sous-agents autorisés

### Requirement: Git Writes Denied At The Permission Layer

Les écritures git interdites par AGENTS.md §7 SHALL être refusées par la
configuration, pas seulement par la consigne.

#### Scenario: Commit demandé par l'utilisateur

- **WHEN** un agent tente `git commit`, `git push`, `git tag`, `git merge`,
  `git rebase`, `git reset`, `git stash`, `git checkout` ou `git worktree`
- **THEN** la permission SHALL résoudre en `deny`
- **AND** l'agent SHALL s'arrêter et décrire l'état au lieu de commiter

