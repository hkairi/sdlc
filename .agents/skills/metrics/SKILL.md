---
name: metrics
description: Calcule les indicateurs du projet depuis les journaux (docs/journal/runs.jsonl, deploys.jsonl et docs/metrics/history.jsonl) et produit docs/metrics/indicateurs.md : tâches par agent, part validée dès la 1re revue, escalades, délai spec → production si calculable, nombre de rollbacks. Toute valeur non mesurable s'affiche « non mesuré ». Utiliser dès que l'utilisateur demande les « indicateurs », les « métriques projet », un « bilan chiffré », la « part validée en revue », les « escalades », le « délai de mise en production » ou de préparer la rétrospective et le rapport client (étape 10).
---

# Indicateurs projet (`metrics`)

> **Chemins.** Les emplacements viennent de la section `paths` de `sdlc.config.yaml`
> (§ 13.3 de `.sdlc/workflow-sdlc.md`) : gabarits sous `paths.templates` (défaut
> `.sdlc/templates`), spec sous `paths.spec`, livrables sous les dossiers `paths.*`
> (défauts indiqués dans cette fiche).

## Objectif

Extraire des **journaux** les indicateurs de pilotage du projet et les écrire dans un document
Markdown. Aucune donnée n'est inventée : une valeur non mesurable est affichée « non mesuré ».

## Entrées

- `sdlc.config.yaml` : `organisation.max_review_iterations`, `organisation.task_timeout_min` (seuils d'escalade).
- `docs/journal/runs.jsonl` : une ligne par délégation d'agent (format § 12).
- `docs/journal/deploys.jsonl` : une ligne par déploiement (format § 12).
- `docs/metrics/history.jsonl` : instantanés du tableau de bord (skill `suivi-projet`).
- Champs **optionnels** exploités : `runs[].review_iteration`, `runs[].spec_freeze_ts`, `deploys[].feature`.

## Commande

Depuis la racine du projet :

```bash
python3 .agents/skills/metrics/scripts/metrics.py . --out docs/metrics/indicateurs.md
```

- `RACINE` : racine du projet (défaut : répertoire courant).
- `--out FICHIER` : sortie (défaut : `<RACINE>/docs/metrics/indicateurs.md`).
- `--config FICHIER` : chemin de `sdlc.config.yaml` (défaut : `<RACINE>/sdlc.config.yaml`).
- `--stdout` : affiche le Markdown au lieu d'écrire le fichier.
- `--help` : aide.

## Indicateurs produits

| Indicateur | Calcul | Si non calculable |
|---|---|---|
| Tâches par agent | comptage des runs par champ `agent` | « non mesuré » (aucun run) |
| Part validée dès la 1re revue | runs `review_iteration == 1` et `status == "done"` ÷ runs ayant `review_iteration` renseigné | « non mesuré » (aucune revue) |
| Escalades | run `blocked`, ou `review_iteration >= max_review_iterations`, ou `duration_s > task_timeout_min × 60` | « non mesuré » (aucun run) |
| Délai spec → production | `deploys[].feature` (env de production) − `spec_freeze_ts` de la fonctionnalité | « non mesuré » (lien absent) |
| Nombre de rollbacks | déploiements avec `result == "rollback"` | « non mesuré » (aucun déploiement) |

Le document contient en outre des compteurs de contexte (runs par statut, déploiements par résultat et
par environnement) et les seuils d'escalade utilisés.

## Livrables

- `docs/metrics/indicateurs.md` (mention : fichier généré, ne pas modifier).

## Critères de fin

- [ ] Le document est produit sans erreur.
- [ ] Chaque indicateur non calculable porte la mention « non mesuré ».
- [ ] Les seuils d'escalade proviennent de `sdlc.config.yaml` (valeurs par défaut 3 et 30 sinon).

## Tests

```bash
python3 -m unittest discover -s .agents/skills/metrics/tests -v
```

Les jeux d'essai sont dans `.agents/skills/metrics/tests/fixtures/` : journaux minimaux couvrant revue 1,
revue multiple, escalade par blocage, par itérations et par durée, déploiement de rollback, et un délai
spec → production calculable.

## Gate et responsable

Étape 10 (clôture). Responsable `gates.default` de `sdlc.config.yaml`. Les indicateurs alimentent la
rétrospective (`retro`) et le rapport client (`client-report`).

## Pièges

- Sans fichier de journal, tout est « non mesuré » : ne pas « corriger » en écrivant des valeurs fictives.
- Le délai spec → production n'est calculable que si le lien fonctionnalité ↔ déploiement existe
  (`spec_freeze_ts` et `deploys[].feature`) ; sinon il reste « non mesuré ».
- Un même run peut relever de plusieurs motifs d'escalade : le total compte des runs uniques, le détail
  par motif peut donc sommer au-delà.
- `history.jsonl` n'est pas indispensable ; son absence n'empêche pas le calcul des autres indicateurs.
