# Revue de spec — `check-sync-state-json`

> Avis de contestation avant le gate `spec_freeze`. Réserve d'indépendance : revue faite dans la même
> session que la rédaction — une confirmation par un agent/modèle différent reste recommandée
> (`review.independence: different_agent_and_model`).

## 0. Identification

| Champ | Valeur |
|---|---|
| Change | `check-sync-state-json` |
| Auteur | orchestrateur (OpenCode) |
| Contradicteur (≠ auteur) | agent de revue — même session (réserve) |
| Date | 2026-10-26 |

## 1. Scénarios manquants

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Aucun scénario ne couvre le **projet existant non migré** : `docs/suivi-*.html` présent mais `docs/suivi/state.json` **absent**. Le gate (hook git + CI) appellerait `check_sync.py` sur un état manquant : refuse-t-il, ou laisse-t-il passer silencieusement (faux « synchrone ») ? C'est le cas de tout projet qui migre vers le framework. | proposal « Why » ; design « Compatibilité » | **majeure** | Ajouter une exigence/scénario : `state.json` absent → `check_sync.py` échoue (code 2) avec « migrer via `migrate_from_html.py` », jamais un passage silencieux. |
| Aucun scénario ne fixe comment `sdlc_check <change>` cible **une feature** dans le fichier unique `state.json` (l'ancien `--file docs/suivi-<id>.html` n'existe plus). | « Synchronisation appliquée » ; design « Modes conservés » | mineure | Préciser l'argument : `--state docs/suivi/state.json --tasks <tasks.md>` (une feature) vs `--all`. |

## 2. Cas limites

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Un change ouvert sans feature dans `state.json` (pas encore généré) : l'ancien `check_all` le signalait (« tasks.md présent mais suivi manquant »). Le nouveau doit conserver ce signal, sinon un change non suivi passe inaperçu. | « Synchronisation appliquée » | mineure | Ajouter un scénario « change sans feature → problème ». |
| `state.json` avec `schema` ≠ 1 (version future) : `check_sync.py` risque de mal lire. | design « Lecture » | mineure | Refuser `schema` ≠ 1 avec un message explicite (cohérent avec `parseStateJson` du plugin). |

## 3. Gestion des erreurs

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| `state.json` illisible (JSON invalide) : code de sortie attendu ? Doit être 2 (erreur), pas 0 (sync OK) ni 1 (dérive). | design « Lecture » | mineure | Préciser : JSON invalide → code 2, message clair. |

## 4. Sécurité

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Conforme : lecture locale de `state.json` et `tasks.md`, aucune donnée sortante, aucun secret. | — | conforme | — |

## 5. Accessibilité (RGAA / WCAG)

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Conforme / sans objet : sortie texte d'un script CLI, pas d'interface. | — | conforme | — |

## 6. Cohérence avec les ADR

| Constat | Référence (ADR) | Gravité | Proposition |
|---|---|---|---|
| Conforme : aucun ADR ne fixe le format du contrôle de synchronisation. | ADR-001 à ADR-006 | conforme | — |

## 7. Cohérence avec les exigences non fonctionnelles

| Constat | Référence (exigence NF) | Gravité | Proposition |
|---|---|---|---|
| Conforme : aligné sur « revue croisée relecteur ≠ auteur » et « couverture de tests ≥ 80 % » (le contrôle de sync est un test de non-régression). | `exigences-nf.md` §7 | conforme | — |

## 8. Traçabilité et testabilité

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Les scénarios ajoutés sont testables ; la correspondance tâches ↔ exigences est absente de `tasks.md` (usage `console-sdlc`). | `tasks.md` | mineure | Ajouter la table de traçabilité exigence ↔ tâche. |

## 9. Impacts recette, déploiement, exploitation

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Le hook git (`.githooks/pre-commit`) et la CI appellent `check_sync.py` : le change doit vérifier que ces appels restent compatibles (mêmes modes `--all`/`--paths`), sinon le gate casse en production. | design « Non-Goals » | mineure | Ajouter une tâche : rejouer le hook git et la CI avec le nouveau `check_sync.py`. |

## Verdict

- Contestations bloquantes : 0
- Contestations majeures : 1
- Contestations mineures : 6

**Verdict** : **non prêt** — une contestation majeure à lever avant `spec_freeze` :
**la migration d'un projet existant** (`state.json` absent, HTML présent) : `check_sync.py` doit
échouer explicitement (code 2) et orienter vers `migrate_from_html.py`, jamais passer en silence.

Les mineures (ciblage d'une feature, change sans feature, `schema` ≠ 1, JSON invalide, traçabilité,
compatibilité hook/CI) se traitent avec la majeure sans bloquer l'essentiel.
