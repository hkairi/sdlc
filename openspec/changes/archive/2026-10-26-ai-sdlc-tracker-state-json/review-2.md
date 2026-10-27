# Revue de spec n°2 — `ai-sdlc-tracker-state-json`

> Seconde revue, après correction par l'auteur des contestations de `review.md`. Le contradicteur
> est un agent **distinct de l'auteur** : **réserve d'indépendance toujours signalée** — la revue est
> faite dans la même session que la rédaction, et une confirmation par un agent/modèle différent est
> recommandée avant de figer (`review.independence: different_agent_and_model`).

## 0. Identification

| Champ | Valeur |
|---|---|
| Change | `ai-sdlc-tracker-state-json` |
| Auteur | orchestrateur (OpenCode) |
| Contradicteur (≠ auteur) | agent de revue — même session (réserve ci-dessus) |
| Date | 2026-10-26 |

## Vérification des contestations de `review.md`

| # | Contestation (gravité) | Statut |
|---|---|---|
| 1 | Delta de spec incomplète (majeure) | ✅ **Levée** — 4 exigences MODIFIED ajoutées : « Génération du suivi », « Signalement des écritures », « Repli sûr », « Scripts de référence ». La spec `sdlc-tracking` ne décrit plus le modèle HTML comme source de vérité. |
| 2 | Cas `reviewer` absent/`null` non tranché (majeure) | ✅ **Levée** — scénario « Relecteur absent » ajouté : refus (ou signalement) si `reviewer` est `null`/absent. |
| 3 | `schema` ≠ 1 (mineure) | ✅ **Levée** — scénario « Version de schéma non reconnue » → inerte + signalement. |
| 4 | `state.json` invalide (mineure) | ✅ **Levée** — scénario « JSON illisible » → erreur interne (fail-open). |
| 5 | Invocation de scripts hors périmètre (mineure) | ✅ **Levée** — scénario « Chemin de script hors périmètre » + décision `design.md` « Sécurité de l'invocation ». |
| 6 | Traçabilité tâches ↔ exigences (mineure) | ✅ **Levée** — table de traçabilité ajoutée dans `tasks.md`. |
| 7 | `plugin-sync-check` (mineure) | ✅ **Levée** — tâche 4.4 explicite (rc 0 sur installation resynchronisée). |
| 8 | Retrait « limite connue » (mineure) | ✅ **Levée** — tâche 5.2 précisée (retirer l'encadré, remplacer par la description `state.json`). |

## Constat ajouté pendant la re-revue

| Constat | Référence | Gravité | Proposition | Statut |
|---|---|---|---|---|
| La correction de « Génération du suivi » avait **omis** le scénario « Génération en échec » (présent dans la spec d'origine). | « Génération du suivi » | mineure | Restaurer le scénario : la génération déléguée à `generate.py` en échec signale ce qui manque, sans faire échouer la validation. | ✅ **Corrigé** pendant la re-revue (scénario restauré). |

## Point résiduel non bloquant

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| L'exigence non modifiée « Synchronisation appliquée dans la session » emploie encore « le fichier de suivi » pour désigner ce qui diverge de `tasks.md` ; dans le nouveau modèle, il s'agit de `state.json`. Le terme reste générique et l'intent est clair (le contrôle `check_sync.py` compare `state.json` ↔ `tasks.md`). | « Synchronisation appliquée dans la session » | mineure (cosmétique) | Optionnel : préciser « `state.json` » dans cette exigence lors d'un prochain passage. |

## Verdict

- Contestations bloquantes : 0
- Contestations majeures : 0
- Contestations mineures résiduelles : 1 (cosmétique, non bloquante)

**Verdict** : **prêt pour spec_freeze** — les deux majeures et les six mineures sont levées ; le
scénario « Génération en échec » (omis puis restauré) est rétabli. Seul subsiste un point
cosmétique non bloquant (« fichier de suivi » → « `state.json` » dans « Synchronisation appliquée »).

> Rappel : le gate `spec_freeze` est passé par le responsable `gates.spec_freeze`
> (`sdlc.config.yaml` : `hkairi`), et la **confirmation d'indépendance** (agent/modèle ≠ auteur)
> reste recommandée avant de figer.
