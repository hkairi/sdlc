# Résolution des constats — `console-sdlc`

> Réponse de l'auteur aux revues `review-1.md`, `review-2.md` et `review.md` (itération 3).
> Les trois itérations de revue sont terminées. Le change est soumis au gate humain
> `spec_freeze`.

## 1. Constats de l'itération 3

| Constat | Gravité | Statut | Correction |
|---|---|---|---|
| **M-9** — REQ-DOC-04 (mention « fichier généré, ne pas modifier ») sans SHALL, scénario ni critère | majeure | résolu | `console-ops` « Documentation et fraîcheur » : SHALL + scénario « Document généré » ; tâche 7.4 et critère du lot 7 |
| **m-27** — dernière page partielle et `offset ≥ total` non spécifiés | mineure | résolu | `console-core` « Pagination serveur » : scénarios « Dernière page partielle » et « Offset au-delà du total » |
| **m-31** — REQ-EQ-05 (chaîne de validation) sans scénario | mineure | résolu | `console-team-process` « Métriques d'équipe » : scénario « Chaîne de validation » |
| **m-32** — deux provenances de runs sans règle d'union/déduplication | mineure | résolu | `console-review` « Journal des runs et indépendance » : union `runs.jsonl` + runs lancés, origine et déduplication par `run_id`, scénario « Deux provenances de runs » |
| **m-33** — CORS désactivé et `Content-Type: application/json` non tracés | mineure | résolu | `console-ops` « Sécurité locale » : SHALL + scénario « Content-Type non JSON » ; tâche 1.5 |
| **m-34** — rétention configurable « par projet » absente | mineure | résolu | `console-ops` « Rétention et purge » : « configurable par projet et par table » |
| **m-35** — critères d'acceptation des lots 3 et 7 incomplets | mineure | résolu | `tasks.md` : lot 3 sans pagination, lot 7 avec Déploiements, pagination, dégradation gracieuse et mention générée |

## 2. Constats des itérations précédentes

- Itération 1 : 2 bloquantes, 21 majeures, 23 mineures.
- Itération 2 : 1 bloquante (B-1) et 7 majeures (M-1 à M-7), traitées par les exigences,
  scénarios et tâches ajoutés.
- Itération 3 : M-8 (Vue Déploiements) résolue ; M-9 et les mineures ci-dessus traitées.
- Aucun constat de l'itération 3 ne reste ouvert.

## 3. Vérifications

- `openspec validate console-sdlc --strict` : **valide**.
- 5 deltas de spec, 12 vues, 6 décisions du 2026-10-20, ouverture automatique du suivi.
- Aucune contradiction avec ADR-001 à ADR-006, les exigences NF ou le cahier des charges.
- Aucun lock-in IDE, agent ou SaaS introduit.

## 4. Ajout post-revue — suivi synchrone

Exigence utilisateur du 2026-10-20 : « le fichier de suivi doit être synchrone tâche par
tâche et doit être mis à jour régulièrement, idéalement dès qu'une tâche change de statut ».

- **Cahier des charges** : `REQ-OV-08`, §9.1 (synchronisation), API
  `PATCH /api/projects/{id}/tasks/{task_id}`, CLI `task set`, scénarios « Un changement de
  statut resynchronise les trois supports » et « Une modification externe est
  resynchronisée », NFR de synchronisation < 2 s.
- **Change OpenSpec** : exigence « Suivi synchrone tâche par tâche » (`console-core`),
  trois scénarios (changement de statut, modification externe, échec d'écriture), tâches
  3.9 à 3.11, design.
- Cette addition est postérieure aux trois itérations de revue ; elle est soumise au gate
  humain avec le reste du change.

## 5. Décision demandée

Le gate `spec_freeze` est un acte humain. La demande porte sur :

- le périmètre du change (12 vues, multi-dépôts, gates, revue, agents, suivi) ;
- les 6 décisions du 2026-10-20 ;
- le découpage en 8 lots et 67 tâches ;
- les réserves explicitement reportées en v1 (voir `proposal.md` « Hors périmètre MVP »).

---

*Auteur : orchestrateur — Date : 2026-10-20 — Statut : prêt pour le gate humain `spec_freeze`.*
