# sdlc-learnings Specification

## Purpose

Définir le registre des apprentissages : des entrées falsifiables, localisées par `scope` et révocables,
consultées à la demande plutôt que chargées en bloc dans le contexte, produites par une étape dédiée de
la chaîne et validées par le hook de pre-commit comme par la CI.
## Requirements
### Requirement: Falsifiable, Localized, Revocable Entries

Chaque apprentissage SHALL être un fichier `openspec/learnings/L-NNNN-<slug>.md`
portant un frontmatter TOML avec `id`, `title`, `kind`, `created`, `status`,
`scope`, `tags` et au moins une `evidence` composée d'une commande et d'un
résultat observable. Une entrée sans preuve, sans `scope` ou sans `tags` MUST
être refusée.

#### Scenario: Entrée sans preuve

- **WHEN** une entrée déclare `evidence = []`
- **THEN** `learnings.py --check` SHALL échouer avec un message nommant le
  fichier et le motif

#### Scenario: Portée globale

- **WHEN** une entrée déclare `scope = ["*"]`
- **THEN** le contrôle SHALL la refuser : une règle globale n'est jamais
  retrievée utilement et se contente de répéter AGENTS.md

### Requirement: Scoped Retrieval

Le registre MUST NOT être chargé en entier dans le contexte d'un agent. La
consultation SHALL se faire par requête (`--query`) ou par chemins (`--paths`),
et SHALL retourner au plus huit entrées actives, les plus pertinentes d'abord.

#### Scenario: Cadrage d'un change

- **WHEN** l'agent `spec` cadre un change touchant
  `.opencode/plugins/ai-sdlc-tracker`
- **THEN** `learnings.py --paths .opencode/plugins/ai-sdlc-tracker/...` SHALL
  retourner les entrées dont le `scope` couvre ce chemin
- **AND** les entrées d'un autre sous-système MUST NOT être retournées

#### Scenario: Entrée périmée ignorée

- **WHEN** une entrée porte `status = "retired"` ou `superseded`
- **THEN** elle MUST NOT apparaître dans les résultats de requête
- **AND** elle SHALL rester lisible dans l'historique du dépôt

### Requirement: Lifecycle Without Deletion

Une règle devenue fausse MUST NOT être supprimée : elle SHALL passer
`status = "retired"` avec un `retired_reason`, ou `superseded` avec un
`superseded_by` pointant vers une entrée existante.

#### Scenario: Règle invalidée par un correctif

- **WHEN** un correctif rend une règle active fausse
- **THEN** l'étape `learn` SHALL passer l'entrée en `retired` avec la preuve
  qui l'invalide
- **AND** un `superseded_by` pointant vers un identifiant inexistant SHALL être
  refusé

### Requirement: Learning Step In The Chain

La chaîne SHALL comporter une étape `learn` (`45-learn.md`) entre la revue et
la clôture. Elle SHALL produire entre zéro et trois entrées, et zéro est un
résultat valide.

#### Scenario: Aucune découverte

- **WHEN** un change n'apporte aucune règle réutilisable
- **THEN** `45-learn.md` SHALL porter `status = "ready"`, `learnings = []` et
  une preuve du contrôle effectué
- **AND** aucune entrée MUST NOT être créée pour « remplir »

#### Scenario: Référence d'apprentissage inexistante

- **WHEN** `45-learn.md` cite `learnings = ["L-0099"]` et que cette entrée
  n'existe pas
- **THEN** `handoff_check.py` SHALL refuser l'artefact

### Requirement: Enforced In Hook And CI

Le registre SHALL être validé par le hook de pre-commit et par la CI, avec le
même script, afin qu'une entrée malformée ne puisse pas être fusionnée.

#### Scenario: Commit avec une entrée invalide

- **WHEN** une entrée ne respecte pas le schéma
- **THEN** le pre-commit SHALL refuser le commit
- **AND** la CI SHALL échouer sur le même fichier

