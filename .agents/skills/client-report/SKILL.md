---
name: client-report
description: Produit un rapport d'avancement destiné au client (docs/client/<periode>.md à partir de .sdlc/templates/docs/client-report.md) en synthétisant le suivi, le journal, les indicateurs, les incidents et les notes de version de la période. Utiliser dès que l'utilisateur demande un « rapport client », un « point d'avancement pour le client », une « communication de livraison », de « présenter les prochaines étapes » ou de clôturer une période côté client (étape 10).
---

# Rapport client (`client-report`)

> **Chemins.** Les emplacements viennent de la section `paths` de `sdlc.config.yaml`
> (§ 13.3 de `.sdlc/workflow-sdlc.md`) : gabarits sous `paths.templates` (défaut
> `.sdlc/templates`), spec sous `paths.spec`, livrables sous les dossiers `paths.*`
> (défauts indiqués dans cette fiche).

## Objectif

Communiquer au client, dans son langage, l'avancement livré, les points de vigilance, les décisions
attendues et les prochaines étapes — à partir de faits, jamais d'estimations non étayées.

## Entrées

- `sdlc.config.yaml` : `project.name`, `gates.default`.
- `docs/suivi/state.json` et `docs/suivi-projet.html` (vision d'ensemble).
- `docs/metrics/indicateurs.md` : avancement mesuré.
- `docs/journal/runs.jsonl`, `deploys.jsonl` : livraisons effectives.
- `docs/incidents/*.md` : incidents survenus (à rendre lisibles).
- Notes de version (`CHANGELOG.md`, `docs/release-notes/<version>.md`) : synthèse des livraisons.
- `.sdlc/templates/docs/client-report.md` : gabarit du rapport.

## Étapes

1. Délimiter la **période** couverte (`<periode>`).
2. Collecter les livraisons réelles (changes archivés, déploiements `success`) et l'avancement du suivi.
3. Rédiger `docs/client/<periode>.md` à partir de `.sdlc/templates/docs/client-report.md` :
   résumé exécutif, avancement par livrable, points de vigilance, décisions attendues, prochaines étapes,
   notes de version.
4. Pour chaque décision attendue, expliciter les options et le délai de réponse.
5. Relever les incidents visibles côté client depuis `docs/incidents/` et indiquer leur statut.
6. Faire valider le rapport avant envoi (responsable `gates.default`).

## Livrables

- `docs/client/<periode>.md`.

## Critères de fin

- [ ] Le statut de chaque livrable est explicite (`terminé` | `en-cours` | `bloqué` | `reporté`).
- [ ] Les décisions attendues listent options et délais.
- [ ] Les incidents visibles côté client sont mentionnés avec leur statut.
- [ ] Aucune donnée inventée : une valeur non mesurée est présentée comme telle.

## Gate et responsable

Clôture de période (étape 10), responsable `gates.default` de `sdlc.config.yaml`. Validation humaine avant
tout envoi au client.

## Pièges

- Langage client : éviter le jargon interne (contrôles, gates, itérations de revue) au profit d'impacts concrets.
- Ne pas promettre de date sans source ; une échéance non décidée reste « à confirmer ».
- Un livrable `bloqué` ou `reporté` est signalé, jamais masqué.
- Le rapport client ne remplace pas les notes de version : il les résume.
