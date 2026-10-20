# Grille de contestation d'un change OpenSpec

<!-- Gabarit de la grille. Copier le résultat dans
     openspec/changes/<id>/review.md. Pour chaque item : constat, référence
     (exigence, scénario, ADR), gravité (bloquante | majeure | mineure),
     proposition. Un item vérifié sans problème est marqué « conforme ». -->

## 0. Identification

| Champ | Valeur |
|---|---|
| Change | {{identifiant-change}} |
| Auteur | {{auteur}} |
| Contradicteur (≠ auteur) | {{contradicteur}} |
| Date | {{date}} |

## 1. Scénarios manquants

<!-- Un besoin exprimé dans le proposal n'a pas de scénario Given/When/Then. -->

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| {{constat-1}} | {{référence-1}} | {{bloquante|majeure|mineure}} | {{proposition-1}} |

## 2. Cas limites

<!-- Valeurs vides, bornes, concurrence, gros volumes, dates, caractères spéciaux,
     états intermédiaires. -->

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| {{constat-2}} | {{référence-2}} | {{bloquante|majeure|mineure}} | {{proposition-2}} |

## 3. Gestion des erreurs

<!-- Échecs d'un service, timeouts, entrées invalides, reprise, messages d'erreur. -->

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| {{constat-3}} | {{référence-3}} | {{bloquante|majeure|mineure}} | {{proposition-3}} |

## 4. Sécurité

<!-- Authentification, autorisation, journalisation d'accès, données sensibles,
     injection, secrets, conformité à `confidentiality`. -->

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| {{constat-4}} | {{référence-4}} | {{bloquante|majeure|mineure}} | {{proposition-4}} |

## 5. Accessibilité (RGAA / WCAG)

<!-- Contraste, navigation clavier, libellés, alternatives textuelles, focus. -->

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| {{constat-5}} | {{référence-5}} | {{bloquante|majeure|mineure}} | {{proposition-5}} |

## 6. Cohérence avec les ADR

<!-- Le change contredit-il un ADR accepté ? Référencer l'ADR concerné. -->

| Constat | Référence (ADR) | Gravité | Proposition |
|---|---|---|---|
| {{constat-6}} | {{adr-6}} | {{bloquante|majeure|mineure}} | {{proposition-6}} |

## 7. Cohérence avec les exigences non fonctionnelles

<!-- `docs/00-cadrage/exigences-nf.md` : performance, sécurité, RGPD, exploitabilité,
     compatibilité. -->

| Constat | Référence (exigence NF) | Gravité | Proposition |
|---|---|---|---|
| {{constat-7}} | {{exigence-nf-7}} | {{bloquante|majeure|mineure}} | {{proposition-7}} |

## 8. Traçabilité et testabilité

<!-- Chaque exigence est-elle traçable et vérifiable par un test ? -->

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| {{constat-8}} | {{référence-8}} | {{bloquante|majeure|mineure}} | {{proposition-8}} |

## 9. Impacts recette, déploiement, exploitation

<!-- Effets sur la recette, la cible de déploiement, le runbook, la migration. -->

| Constat | Référence | Gravité | Proposition |
|---|---|---|---|
| {{constat-9}} | {{référence-9}} | {{bloquante|majeure|mineure}} | {{proposition-9}} |

## Verdict

- Contestations bloquantes : {{nombre-bloquantes}}
- Contestations majeures : {{nombre-majeures}}
- Contestations mineures : {{nombre-mineures}}

**Verdict** : {{prêt pour spec_freeze | non prêt}}
