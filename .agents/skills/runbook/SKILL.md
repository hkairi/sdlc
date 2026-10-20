---
name: runbook
description: Crée et maintient docs/ops/runbook.md et ses fiches opérationnelles (symptôme → diagnostic → remédiation → escalade) à partir de .sdlc/templates/docs/runbook.md et .sdlc/templates/docs/runbook-fiche.md, en y intégrant les fiches de .sdlc/templates/deploy/<profil>/runbook-sections.md des cibles de déploiement. Utiliser dès que l'utilisateur demande le « runbook », une « fiche d'exploitation », de « documenter un symptôme », de « préparer la supervision », de « savoir qui escalader » ou l'« étape 9 ».
---

# Runbook et supervision (`runbook`)

> **Chemins.** Les emplacements viennent de la section `paths` de `sdlc.config.yaml`
> (§ 13.3 de `.sdlc/workflow-sdlc.md`) : gabarits sous `paths.templates` (défaut
> `.sdlc/templates`), spec sous `paths.spec`, livrables sous les dossiers `paths.*`
> (défauts indiqués dans cette fiche).

## Objectif

Constituer et tenir à jour le runbook du projet : un document de référence
**symptôme → diagnostic → remédiation → escalade** qui permet à l'exploitant d'agir sans lire le code.

## Entrées

- `sdlc.config.yaml` : `deploy.targets[]` (profils), `gates.default`, `project.name`, et les identifiants de contact définis avec l'humain.
- `.sdlc/templates/docs/runbook.md` : gabarit du runbook (index, accès, procédures transverses, références).
- `.sdlc/templates/docs/runbook-fiche.md` : gabarit d'une fiche détaillée.
- `.sdlc/templates/deploy/<profil>/runbook-sections.md` : fiches propres à chaque profil de déploiement.
- Les procédures `docs/ops/deploy-<composant>.md` (rollback, sauvegarde).

## Étapes

1. Lire `sdlc.config.yaml` pour connaître les profils de `deploy.targets` et `project.name`.
2. Créer ou mettre à jour `docs/ops/runbook.md` à partir de `.sdlc/templates/docs/runbook.md` (informations
   générales, accès et prérequis, index des fiches, procédures transverses, références).
3. Pour **chaque** profil de `deploy.targets`, intégrer les fiches de
   `.sdlc/templates/deploy/<profil>/runbook-sections.md` (conserver le format fiche du gabarit).
4. Pour les fiches qui méritent un détail complet, créer `docs/ops/runbook-fiche-<slug>.md` à partir de
   `.sdlc/templates/docs/runbook-fiche.md` et y faire pointer l'index. `slug` : symptôme en minuscules et tirets.
5. Renseigner l'**index** du runbook : colonnes symptôme → fiche → priorité.
6. Renseigner les procédures transverses : montée en charge d'astreinte, rollback d'urgence, communication
   interne, et le contact d'escalade de chaque fiche.

## Livrables

- `docs/ops/runbook.md`.
- `docs/ops/runbook-fiche-<slug>.md` (une fiche détaillée par symptôme qui le nécessite).
- Les fiches de profil de `.sdlc/templates/deploy/<profil>/runbook-sections.md` intégrées.

## Critères de fin

- [ ] Chaque profil de `deploy.targets` a ses fiches reprises dans le runbook.
- [ ] Chaque fiche suit l'ordre symptôme → diagnostic → remédiation → escalade.
- [ ] Chaque fiche indique une priorité et un contact d'escalade.
- [ ] L'index du runbook pointe vers les fiches existantes.

## Gate et responsable

Validation par le responsable `gates.default` de `sdlc.config.yaml` (ou l'identifiant défini avec
l'humain). Le runbook est un document **Markdown source** ; il n'est pas généré depuis le HTML.

## Pièges

- Ne pas recopier deux fois la même fiche : un symptôme, une fiche, référencée depuis l'index.
- Toute fiche se termine par une condition et un contact d'escalade explicites.
- Ne pas inventer de seuils d'alerte : reprendre ceux des gabarits de profil ou des mesures du projet.
- La procédure de **rollback** d'une fiche renvoie à la section rollback de `docs/ops/deploy-<composant>.md`.
