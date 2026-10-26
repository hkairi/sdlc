# Registre des apprentissages

Un apprentissage répond à **une** question : *qu'est-ce qu'on a appris ici qu'on
ne veut pas réapprendre ?* Ce n'est ni une doc, ni un journal, ni un backlog.
C'est une règle locale, falsifiable, révocable.

## Ce qui entre

| Oui | Non |
|---|---|
| « Pour `internal/server`, Faktory doit tourner, sinon 4 tests échouent en 500 » | « écrire des tests » |
| « `after-validate` prend `2>&1` pour un id de change » | « faire attention au parsing » |
| « La base Go est `engagement_backend_go_test`, jamais celle de Rails » | « bien séparer les environnements » |

Trois conditions, sinon l'entrée est refusée par `learnings.py --check` :

1. **Falsifiable** — au moins une preuve `cmd` + `result` observable.
2. **Localisée** — un `scope` de chemins (jamais `*`).
3. **Révocable** — un `status` et, le jour où la règle devient fausse, un
   `retired_reason`. Une mémoire qui ne se périme pas se trompe en silence.

## Format

`openspec/learnings/L-NNNN-<slug>.md`, frontmatter TOML entre `+++` :

```toml
+++
id = "L-0007"
title = "Faktory requis pour internal/server"
kind = "pitfall"              # pitfall | practice | convention | tooling
created = "2026-10-26"
status = "active"             # active | superseded | retired
scope = ["engagement-api/internal/server"]
tags = ["faktory", "tests", "webhooks"]
source_change = "harden-faktory-job-reliability"

[[evidence]]
cmd = "go test ./internal/server/..."
result = "sans Faktory : 4 échecs ; avec : 0"
+++

## Règle
Une phrase, à l'impératif.

## Pourquoi
Le mécanisme, pas l'anecdote.

## Comment vérifier
La commande exacte qui reproduit, ou qui prouve que la règle tient encore.
```

## Cycle de vie

- `active` — la règle s'applique.
- `superseded` — remplacée, `superseded_by = "L-00xx"`.
- `retired` — devenue fausse, `retired_reason` obligatoire. **On ne supprime
  jamais** : l'historique d'une erreur est ce qui empêche de la refaire.

## Comment elle est utilisée

| Moment | Commande |
|---|---|
| Cadrage d'un change | `python3 scripts/learnings.py --query "<capacité>" --paths <chemins>` |
| Avant d'implémenter une tâche | `python3 scripts/learnings.py --paths <fichiers de la tâche>` |
| Revue | l'agent `review` cite `L-00xx` comme finding si une règle active est violée |
| Clôture | l'agent `learn` ajoute 0 à 3 entrées, ou en retire une devenue fausse |

Le registre n'est **pas** chargé en entier dans le contexte : on interroge, on
n'obtient que les entrées du scope, plafonnées à 8 par défaut.
