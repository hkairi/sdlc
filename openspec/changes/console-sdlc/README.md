# console-sdlc

Console SDLC locale (SQLite) : tableau de bord, gates, revue indépendante, équipe et
processus.

## Artefacts

- [Proposal](proposal.md) — Why / What Changes / Capabilities / Impact.
- [Design](design.md) — architecture, multi-dépôts, gates, revue, agents, audit.
- [Specs](specs/) — cinq deltas : `console-core`, `console-quality`, `console-review`,
  `console-team-process`, `console-ops`.
- [Tasks](tasks.md) — 8 lots, 70 tâches, critères d'acceptation par lot.
- [Revue 1](review-1.md) — 2 bloquantes, 21 majeures, 23 mineures.
- [Revue 2](review-2.md) — B-1 et M-1 à M-7, mineures.
- [Revue 3](review.md) — M-8 résolue, M-9 et mineures résiduelles.
- [Résolution](review-resolution.md) — réponse de l'auteur aux trois revues.

## État

- `openspec validate console-sdlc --strict` : valide.
- `spec_freeze` : **approuvé le 2026-10-20** (voir [approval.md](approval.md)).
- Suivi généré : `docs/suivi-console.html` (état `docs/suivi/console.json`).
- Implémentation : lot L0 en cours.
