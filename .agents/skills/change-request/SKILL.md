---
name: change-request
description: Voie transverse d'évolution après le spec freeze — documente une demande de changement, analyse son impact (spécification, architecture, planification, tests), ouvre un nouveau change OpenSpec lié, replanifie et le soumet au gate « spec freeze ». Utiliser dès qu'une demande arrive après le gel des specs : « ajouter cette fonctionnalité », « changer ce comportement », « le client demande autre chose », « modifier la spec validée », ou quand un besoin nouveau apparaît en cours de réalisation.
---

# Demande de changement (`change-request`)

> **Chemins.** Les emplacements viennent de la section `paths` de `sdlc.config.yaml`
> (§ 13.3 de `.sdlc/workflow-sdlc.md`) : gabarits sous `paths.templates` (défaut
> `.sdlc/templates`), spec sous `paths.spec`, livrables sous les dossiers `paths.*`
> (défauts indiqués dans cette fiche).

## Objectif

Traiter toute évolution survenant **après le spec freeze** : on ne modifie pas une spec gelée en
silence. On documente la demande, on mesure son impact, on ouvre un **nouveau change OpenSpec lié**,
on replanifie, puis on repasse le gate **spec freeze**.

## Entrées

- `sdlc.config.yaml` : `gates.spec_freeze` (responsable), `organisation.parallelism`.
- `.sdlc/templates/docs/change-request.md` : gabarit d'analyse.
- Le change OpenSpec d'origine et les ADR concernés (sous `openspec/changes/` et `docs/architecture/adr/`).
- `openspec/changes/<id>/` : convention OpenSpec (proposal, design, deltas de spec, tasks).

## Étapes

1. Qualifier la demande : est-elle **postérieure** au spec freeze ? Sinon, la traiter dans le change en cours.
2. Créer le répertoire du nouveau change lié sous `openspec/changes/<nouveau-id>/`.
3. Remplir `openspec/changes/<nouveau-id>/change-request.md` à partir de `.sdlc/templates/docs/change-request.md` :
   résumé, motivation, change(s) d'origine, **impact** sur la spécification, l'architecture, la planification
   et les tests/recette, options envisagées, recommandation, décision.
4. Produire les deltas de spec du nouveau change avec les commandes OpenSpec (proposal, design, deltas,
   `tasks.md`).
5. Replanifier : mettre à jour `tasks.md` et le suivi (`suivi-taches`, `suivi-projet`) avec les nouvelles
   tâches, leurs dépendances, l'exécutant et le **relecteur ≠ auteur**.
6. Faire **contester** le nouveau change par un agent ≠ auteur (skill `spec-review`).
7. Soumettre au gate **spec freeze**.

## Livrables

- `openspec/changes/<nouveau-id>/change-request.md` (analyse d'impact).
- `openspec/changes/<nouveau-id>/` complet (proposal, design, deltas de spec, `tasks.md`).
- `tasks.md` et suivi mis à jour.

## Critères de fin

- [ ] La demande est reliée explicitement au(x) change(s) d'origine.
- [ ] L'impact est analysé sur les quatre axes du gabarit (spec, architecture, planification, tests).
- [ ] Un relecteur ≠ auteur a contesté le nouveau change.
- [ ] Le gate spec freeze est repassé **avant** toute implémentation.

## Gate et responsable

Gate **spec freeze**, responsable `gates.spec_freeze` de `sdlc.config.yaml`. Principe non négociable :
**pas de code sans spec validée**. Tant que le nouveau change n'est pas gelé, aucune implémentation ne démarre.

## Pièges

- Ne jamais modifier une spec gelée : passer par un nouveau change lié.
- Si la décision est `rejeté`, le documenter et **arrêter** — ne pas implémenter en contournant le gate.
- L'analyse d'impact est la clé : sans elle, le coût et le risque sont sous-estimés.
- Une replanification sans mise à jour du relecteur (≠ auteur) des nouvelles tâches est incomplète.
