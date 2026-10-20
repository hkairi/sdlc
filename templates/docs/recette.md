# Recette — {{nom-de-la-fonctionnalité}}

<!-- Remplacer {{nom-de-la-fonctionnalité}} par le nom de la fonctionnalité testée. -->

## 1. Objectif

<!-- Décrire le périmètre de cette recette. -->

{{objectif}}

## 2. Environnement de recette

<!-- Décrire l'environnement utilisé pour la recette. -->

| Élément | Valeur |
|---|---|
| Environnement | {{environnement}} |
| Version testée | {{version}} |
| Données de test | {{données-de-test}} |
| Navigateur / client | {{client}} |

## 3. Matrice scénario → test → résultat

<!-- Pour chaque scénario, indiquer le test associé et le résultat observé. -->

| ID | Scénario | Test | Résultat attendu | Résultat observé | Statut | Observateur | Date |
|---|---|---|---|---|---|---|---|
| R-001 | {{scénario-1}} | {{test-1}} | {{attendu-1}} | {{observé-1}} | {{ok|ko|bloqué|non-testé}} | {{observateur-1}} | {{date-1}} |
| R-002 | {{scénario-2}} | {{test-2}} | {{attendu-2}} | {{observé-2}} | {{ok|ko|bloqué|non-testé}} | {{observateur-2}} | {{date-2}} |

## 4. Anomalies

<!-- Lister les anomalies rencontrées. -->

| ID | Scénario | Description | Sévérité | Statut | Ticket |
|---|---|---|---|---|---|
| {{id-anomalie-1}} | {{scénario-1}} | {{description-1}} | {{critique|majeure|mineure|cosmétique}} | {{ouvert|corrigé|validé}} | {{ticket-1}} |

## 5. Bilan

<!-- Synthétiser le résultat global de la recette. -->

- Nombre de scénarios : {{nombre-scénarios}}
- Nombre de scénarios OK : {{nombre-ok}}
- Nombre de scénarios KO : {{nombre-ko}}
- Nombre de scénarios bloqués : {{nombre-bloqués}}
- Décision : {{go|no-go|à-reprendre}}

---

*Responsable recette : {{responsable}} — Date : {{date}}*
