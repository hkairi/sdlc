---
name: retro
description: Produit la rétrospective d'une période (docs/retro/<periode>.md à partir de .sdlc/templates/docs/retro.md) à partir du suivi, du journal des runs, des indicateurs et des écarts à la spec. Utiliser dès que l'utilisateur demande une « rétrospective », un « bilan de fin de période / de sprint », de « faire le point sur ce qui a marché », de « lister les actions d'amélioration » ou de clôturer une période (étape 10).
---

# Rétrospective (`retro`)

> **Chemins.** Les emplacements viennent de la section `paths` de `sdlc.config.yaml`
> (§ 13.3 de `.sdlc/workflow-sdlc.md`) : gabarits sous `paths.templates` (défaut
> `.sdlc/templates`), spec sous `paths.spec`, livrables sous les dossiers `paths.*`
> (défauts indiqués dans cette fiche).

## Objectif

Tirer les enseignements d'une période à partir de **données réelles** : ce qui a fonctionné, ce qui a
été difficile, les résultats mesurés, et des actions d'amélioration tracées.

## Entrées

- `sdlc.config.yaml` : `project.name`, `organisation.*`, `gates.default`.
- `docs/suivi/state.json` : état des fonctionnalités et des phases.
- `docs/journal/runs.jsonl` et `docs/metrics/indicateurs.md` : activité, revues, escalades, délais.
- `openspec/changes/` (en cours et archivés) : écarts entre la spec et ce qui a été livré.
- `docs/incidents/*.md` : incidents de la période.
- `.sdlc/templates/docs/retro.md` : gabarit de la rétrospective.

## Étapes

1. Délimiter la **période** couverte (`<periode>`, par exemple `sprint-3`).
2. Rassembler les faits : état du suivi, runs, déploiements, indicateurs, incidents, écarts à la spec.
3. Calculer ou reprendre les **métriques** de la période depuis `docs/metrics/indicateurs.md`
   (skill `metrics`) ; afficher « non mesuré » pour toute valeur absente.
4. Remplir `docs/retro/<periode>.md` à partir de `.sdlc/templates/docs/retro.md` : contexte, réussites,
   difficultés, métriques, actions d'amélioration, feedbacks.
5. Donner à chaque action d'amélioration un responsable, une échéance et un statut.

## Livrables

- `docs/retro/<periode>.md`.

## Critères de fin

- [ ] Chaque métrique citée a une source identifiée (suivi, journal, indicateurs).
- [ ] Les écarts à la spec sont explicitement mentionnés (ou « aucun »).
- [ ] Chaque action d'amélioration a un responsable et une échéance.
- [ ] Aucune valeur inventée : les données absentes sont « non mesuré ».

## Gate et responsable

Clôture de période (étape 10), responsable `gates.default` de `sdlc.config.yaml`. La rétrospective est un
document Markdown source.

## Pièges

- Ne pas inventer de chiffre : une métrique non mesurée s'affiche « non mesuré ».
- Distinguer le **résultat** (donnée) de l'**opinion** (feedback) — les deux sont utiles, mais séparés.
- Les écarts à la spec sont une matière première d'amélioration : ne pas les gommer.
- Une rétrospective sans actions attribuées ne change rien.
