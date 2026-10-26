# Approbation — `spec_freeze`

| Champ | Valeur |
|---|---|
| Change | `ai-sdlc-tracker-state-json` |
| Gate | `spec_freeze` |
| Décision | **en attente de décision du responsable** (`gates.spec_freeze` = `hkairi`) |
| Approbateur | à compléter par le responsable humain |
| Date | 2026-10-26 |
| Portée | `proposal.md`, `design.md`, `tasks.md` (18 tâches), 1 delta (`sdlc-tracking`) — 8 exigences (6 MODIFIED + 2 ADDED), 25 scénarios |
| Conditions | Toute évolution après gel passe par `change-request` ; l'implémentation suit le TDD lot par lot ; `bin/plugin-sync-check` reste vert après la réécriture |
| Revue | `review.md` (non prêt), `review-2.md` (prêt pour spec_freeze) |
| Prochaine étape | Lot 1 — Lecture de l'état en `state.json` (tâche 1.1) |

## Objet du change

Adapter le plugin OpenCode `ai-sdlc-tracker` au modèle d'état du framework : la source de vérité
du suivi devient `docs/suivi/state.json` (plus le HTML), la génération délègue à la skill
`suivi-taches`, et la règle **« relecteur ≠ auteur »** est appliquée. Les 77 tests sont portés du
modèle HTML vers le modèle JSON.

## Réserves avant validation

1. **Indépendance de la revue** — les deux revues (`review.md`, `review-2.md`) ont été faites dans
   la même session que la rédaction, contrairement à `review.independence:
   different_agent_and_model`. Une **confirmation par un agent/modèle différent** est recommandée
   avant de figer.
2. **Point résiduel cosmétique** — « Synchronisation appliquée dans la session » emploie encore
   « fichier de suivi » au lieu de « `state.json` » (non bloquant).

## Historique

- `review.md` : verdict **non prêt** — 2 majeures (delta incomplète, `reviewer` absent non tranché)
  + 6 mineures.
- `review-2.md` : verdict **prêt pour spec_freeze** — 8 contestations levées, scénario « Génération
  en échec » restauré, 1 résiduel cosmétique.

---

*Support rédigé par : orchestrateur — Date : 2026-10-26. La décision est enregistrée par le
responsable `gates.spec_freeze` après confirmation de l'indépendance de la revue.*
