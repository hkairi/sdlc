# Revue de spec — `ai-sdlc-tracker-state-json`

> Avis de contestation avant le gate `spec_freeze`. Le contradicteur est un agent **distinct de
> l'auteur du change** : le rôle est tenu par un autre agent en lecture seule. Ici, la revue est
> faite dans la même session que la rédaction — **réserve d'indépendance signalée** : conformément à
> `review.independence: different_agent_and_model`, une confirmation par un agent/modèle différent
> est recommandée avant de figer.

## 0. Identification

| Champ | Valeur |
|---|---|
| Change | `ai-sdlc-tracker-state-json` |
| Auteur | orchestrateur (OpenCode) |
| Contradicteur (≠ auteur) | agent de revue — même session (réserve ci-dessus) |
| Date | 2026-10-26 |

## 1. Scénarios manquants

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| La delta de spec ne modifie que **2 exigences** (« Cible résolue », « Mise à jour »), alors que la spec `sdlc-tracking` contient **d'autres exigences qui décrivent encore le modèle HTML** : « Génération du suivi après validation stricte » (génère un fichier HTML), « Signalement des écritures directes du suivi et des tâches » (« un fichier de suivi »), « Repli sûr hors périmètre » (« fichier de suivi reconnu »), « Scripts de référence uniques » (`scripts/suivi/` vendorisés depuis `engagements`). Après archivage, la spec serait **auto-contradictoire** (état JSON ici, HTML là). | `sdlc-tracking` § « Génération du suivi », « Signalement des écritures », « Repli sûr », « Scripts de référence » ; proposal « What Changes » | **majeure** | Étendre la delta : MODIFIER (ou REMOVED) ces exigences pour dire que la génération délègue à `suivi-taches` `generate.py` (lit `state.json`, écrit le HTML), que « le suivi » désigne `state.json`, et que les scripts de référence sont ceux de `suivi-taches` (plus ceux d'`engagements`). |
| Le proposal annonce « les 77 tests sont portés », mais aucun scénario ne fixe le **comportement de génération** après le passage à `state.json` (qui déclenche la génération, avec quel script). | proposal « What Changes » ; « Génération du suivi » | mineure | Ajouter un scénario « génération déléguée à `generate.py` » dans la delta. |

## 2. Cas limites

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| La règle « relecteur ≠ auteur » ne couvre que le cas `reviewer` **défini et égal à `executor`**. Le cas `reviewer` **absent/`null`** (relecteur non encore assigné) n'est pas tranché : la tâche `2.3` dit « ne peut passer `done` sans relecteur distinct assigné », mais aucun scénario ne le dit. Ambiguïté non tranchée en silence. | `sdlc-tracking` « Relecteur différent de l'auteur » ; `tasks.md` 2.3 | **majeure** | Ajouter un scénario : « relecteur absent → refus (ou signalement) à la clôture, avec indication d'assigner un relecteur distinct ». |
| Deux `features[].id` identiques dans `state.json` (état corrompu) : la résolution par `id` est indéterminée. | « Cible résolue » | mineure | Préciser : le premier `id` gagne, ou l'état est signalé incohérent (erreur interne). |
| `state.json` valide mais `schema` ≠ 1 (version future) : le plugin risque de mal lire les champs. | « Source de vérité unique » | mineure | Ajouter : `schema` non reconnu → inerte + signalement, jamais une lecture silencieuse. |

## 3. Gestion des erreurs

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| `state.json` illisible (JSON invalide, permissions) : l'exigence « Lecture » ne dit rien. C'est couvert en creux par « Un défaut interne ne fait jamais échouer un outil » (fail-open), mais le croisement n'est pas explicite. | « Source de vérité unique » ; « Défaut interne » | mineure | Citer explicitement : JSON invalide = erreur interne (fail-open, journalisée), pas un refus volontaire. |

## 4. Sécurité

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Le plugin invoque des scripts Python (`track.py`) via `pythonBin` et un chemin issu de la config. Une config malveillante pourrait pointer vers un script arbitraire. L'exigence « Scripts de référence uniques » le borne partiellement, mais le change devrait dire que **seuls** les scripts de `suivi-taches` sont appelés, avec chemin contrôlé. | « Scripts de référence uniques » ; `design.md` « Écriture » | mineure | Préciser l'invocation : chemin résolu sous le répertoire de la skill, refus de chemin absolu hors périmètre. |

## 5. Accessibilité (RGAA / WCAG)

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Conforme / sans objet : le plugin produit une sortie texte (outils CLI), pas d'interface. Le HTML généré relève de la skill `suivi-taches`, hors périmètre du change. | — | conforme | — |

## 6. Cohérence avec les ADR

| Constat | Référence (ADR) | Gravité | Proposition |
|---|---|---|---|
| Conforme : les ADR-001 à ADR-006 concernent la Console SDLC, pas le plugin. Aucune contradiction avec un ADR accepté. | ADR-001 à ADR-006 | conforme | — |

## 7. Cohérence avec les exigences non fonctionnelles

| Constat | Référence (exigence NF) | Gravité | Proposition |
|---|---|---|---|
| Cohérent : la règle « relecteur ≠ auteur » ajoutée est **alignée** sur l'exigence de maintenance « Revue croisée : relecteur ≠ auteur, autre modèle si disponible ». Les commandes bornées (10 s) restent conformes à la performance. | `exigences-nf.md` §7 « Revue croisée » | conforme | — |

## 8. Traçabilité et testabilité

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Les exigences ajoutées/modifiées ont des scénarios testables, mais `tasks.md` ne **trace pas** les tâches vers les exigences (pas de références `REQ-…` ou de correspondance exigence → tâche), contrairement à l'usage du dépôt (`console-sdlc`). | `tasks.md` ; pratique `console-sdlc` | mineure | Ajouter une colonne ou des références d'exigence dans `tasks.md` (ex. `2.1 → « Relecteur différent de l'auteur »`). |

## 9. Impacts recette, déploiement, exploitation

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| Le change réécrit les fichiers du gabarit : `bin/plugin-sync-check` (contrôle de dérive gabarit → installation) doit **continuer à passer** après la réécriture. Le change ne le mentionne pas. | `bin/plugin-sync-check` ; `design.md` | mineure | Ajouter une tâche : après réécriture, `plugin-sync-check` rc 0 sur une installation resynchronisée (déjà couvert par 4.4, mais explicite). |
| Le `GUIDE.md` actuel dit que le plugin est « inerte » : sa mise à jour est prévue (5.1), mais le change ne précise pas que la mention « limite connue » du `README.md` d'adaptateur doit être **retirée** (plus une « limite »). | `GUIDE.md` ; `templates/adapters/opencode/README.md` | mineure | Préciser en 5.2 : retirer l'encadré « limite connue », le remplacer par la description du modèle `state.json`. |

## Verdict

- Contestations bloquantes : 0
- Contestations majeures : 2
- Contestations mineures : 6

**Verdict** : **non prêt** — deux contestations majeures à lever avant le gate `spec_freeze` :
1. **Delta de spec incomplète** (des exigences `sdlc-tracking` décrivent encore le modèle HTML — « Génération du suivi », « Signalement des écritures », « Repli sûr », « Scripts de référence »).
2. **Cas `reviewer` absent/`null` non tranché** dans la règle « relecteur ≠ auteur ».

Les mineures (schema ≠ 1, JSON invalide, invocation de scripts, traçabilité, `plugin-sync-check`, retrait de la « limite connue ») peuvent être traitées avec les majeures sans bloquer l'essentiel.
