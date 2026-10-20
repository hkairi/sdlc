---
name: recette
description: Dérive les scénarios GIVEN/WHEN/THEN d'un change OpenSpec en tests de bout en bout, les exécute en préproduction et produit la matrice scénario → test → résultat dans docs/recette/<feature>.md à partir de .sdlc/templates/docs/recette.md. Fournit une table de correspondance d'outils de bout en bout par type d'application (web, API, mobile) sans en imposer un. Utiliser dès que l'utilisateur demande une « recette », des « tests de bout en bout », de « valider en préproduction », de « remplir la matrice de recette », d'« exécuter les scénarios » ou de préparer le gate « recette ».
---

# Recette en préproduction (`recette`)

> **Chemins.** Les emplacements viennent de la section `paths` de `sdlc.config.yaml`
> (§ 13.3 de `.sdlc/workflow-sdlc.md`) : gabarits sous `paths.templates` (défaut
> `.sdlc/templates`), spec sous `paths.spec`, livrables sous les dossiers `paths.*`
> (défauts indiqués dans cette fiche).

## Objectif

Partir des **scénarios de la spécification** (exigences et scénarios GIVEN/WHEN/THEN des changes
OpenSpec), écrire ou lier les tests de bout en bout correspondants, les exécuter en **préproduction**,
et consigner le résultat dans une matrice **scénario → test → résultat**.

## Entrées

- `sdlc.config.yaml` : `gates.recette` (responsable du gate), `deploy.targets` (environnements/ composants), `project.stack`.
- `openspec/changes/<id>/` : `proposal.md`, `design.md`, deltas de spec (exigences et scénarios GIVEN/WHEN/THEN).
- `.sdlc/templates/docs/recette.md` : gabarit de la matrice.
- Les procédures `docs/ops/deploy-<composant>.md` pour connaître l'environnement de préproduction.

## Table de correspondance des outils de bout en bout

Liste **d'exemples** — aucun outil n'est imposé ; choisir selon `project.stack` et les ADR.

| Type d'application | Exemples d'outils de bout en bout | Ce que le test doit couvrir |
|---|---|---|
| Web / interface | Playwright, Cypress, Selenium, Testing Library + navigateur | parcours utilisateur, formulaires, navigation, accessibilité de base |
| API / service | newman, Supertest, REST Assured, pytest + httpx/requests, Schemathesis | contrat d'API, codes et erreurs, idempotence, authentification |
| Mobile | Appium, Maestro, Espresso, XCUITest, Detox | parcours sur émulateur/appareil, permissions, stockage local |

## Étapes

1. Lire `sdlc.config.yaml` et le change OpenSpec ciblé ; extraire chaque **exigence** et chaque **scénario**
   (GIVEN/WHEN/THEN) avec un identifiant stable.
2. Pour chaque scénario, écrire le test de bout en bout ou lier le test existant : établir le mapping
   **ID de scénario → test** (nom de fichier, cas de test).
3. Construire ou préparer l'environnement de **préproduction** conformément aux `deploy.targets`
   (jamais en production).
4. Exécuter les tests et consigner pour chaque scénario : résultat attendu, résultat observé, statut
   (`ok` | `ko` | `bloqué` | `non-testé`), observateur, date.
5. Remplir `docs/recette/<feature>.md` à partir de `.sdlc/templates/docs/recette.md` : objectif, environnement,
   matrice, anomalies, bilan.
6. Soumettre le résultat au **responsable du gate recette**.

## Livrables

- Tests de bout en bout du projet (emplacement selon `project.stack`).
- `docs/recette/<feature>.md` : matrice complète au format de `.sdlc/templates/docs/recette.md`.

## Critères de fin

- [ ] Chaque scénario OpenSpec dispose d'une ligne dans la matrice (aucun scénario omis).
- [ ] Un scénario sans test est marqué `non-testé`, jamais `ok`.
- [ ] Les anomalies sont listées avec sévérité et ticket.
- [ ] Le bilan indique la décision `go` | `no-go` | `à-reprendre`.

## Gate et responsable

Gate **recette**. Le responsable est `gates.recette` de `sdlc.config.yaml` (à défaut `gates.default`).
Ce gate est franchi **avant** le déploiement (étape 8) : un `no-go` bloque la mise en production.

## Pièges

- Ne jamais inventer un résultat : un scénario non joué est `non-testé`, une mesure absente est « non mesuré ».
- Recette en préproduction uniquement ; les données de test sont isolées de la production.
- Un scénario d'exigence peut donner plusieurs lignes (variantes) ; l'ID d'exigence reste tracé.
- La matrice est un document Markdown source, pas un rendu généré.
