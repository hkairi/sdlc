---
name: cadrage
description: Produit le cadrage d'un projet à l'étape 1 — brief (problème à résoudre, objectifs mesurables, périmètre inclus et exclu, parties prenantes, risques, contraintes) et exigences non fonctionnelles (performance, sécurité, accessibilité RGAA, confidentialité RGPD, exploitabilité, compatibilité, maintenance). Utiliser quand l'utilisateur demande un « cadrage », un « brief », les « exigences non fonctionnelles », une « définition du besoin », ou de « poser le périmètre » avant la conception ; déclenché après l'initialisation (et, pour un projet existant, après l'état des lieux).
---

# Cadrage (`cadrage`)

> **Chemins.** Les emplacements viennent de la section `paths` de `sdlc.config.yaml`
> (§ 13.3 de `.sdlc/workflow-sdlc.md`) : gabarits sous `paths.templates` (défaut
> `.sdlc/templates`), spec sous `paths.spec`, livrables sous les dossiers `paths.*`
> (défauts indiqués dans cette fiche).

## Objectif

Transformer un besoin exprimé en deux documents de référence validés : le **brief** (quoi, pour
qui, pourquoi, avec quelles limites) et les **exigences non fonctionnelles** (avec quels niveaux
de performance, de sécurité, d'accessibilité, de conformité). C'est l'étape 1 ; elle conditionne
la conception et la spec.

## Quand l'utiliser

- Étape 1 du workflow, une fois `sdlc.config.yaml` en place (et l'état des lieux fait si le
  projet est existant).
- L'utilisateur demande un cadrage, un brief, une expression de besoin, des exigences non
  fonctionnelles, ou de définir le périmètre.

## Entrées

1. `sdlc.config.yaml` : `project.name`, `project.kind`, `project.stack`, `confidentiality`,
   `providers_allowed`, `ci.coverage_min`, `deploy.targets`, `gates`.
2. `docs/00-cadrage/etat-des-lieux.md` si le projet est existant.
3. Les entretiens / informations fournis par l'humain (besoin, utilisateurs, contraintes).
4. Les gabarits :
   - `.sdlc/templates/docs/brief.md`
   - `.sdlc/templates/docs/exigences-nf.md`

## Étapes

1. **Recueillir le besoin** auprès de l'humain : problème à résoudre (sans solution technique),
   utilisateurs et parties prenantes, contraintes (budget, délai, réglementation, stack
   existante), hypothèses.
2. **Formuler des objectifs mesurables** : 1 à 5 objectifs, chacun avec un indicateur, une cible
   et une échéance. Un objectif sans indicateur ni cible n'est pas un objectif mesurable.
3. **Délimiter le périmètre** : lister explicitement le « dans le périmètre » et le « hors
   périmètre ».
4. **Identifier les risques** : probabilité, impact, mitigation. Ne pas classer un risque sans
   mitigation proposée.
5. **Rédiger le brief** depuis `.sdlc/templates/docs/brief.md` (commentaires de consigne supprimés),
   puis le soumettre à validation.
6. **Rédiger les exigences non fonctionnelles** depuis `.sdlc/templates/docs/exigences-nf.md` :
   - performance (temps de réponse, débit, disponibilité) ;
   - sécurité (authentification, autorisation, chiffrement, audit) ;
   - accessibilité (référentiel RGAA/WCAG, niveau cible, périmètre) ;
   - confidentialité et conformité (données traitées, base légale, conservation, mesures) ;
   - exploitabilité (surveillance, logs, sauvegarde, reprise) ;
   - compatibilité (navigateurs, appareils, versions) ;
   - maintenance (couverture minimale cohérente avec `ci.coverage_min`, documentation, dette
     acceptable).
7. **Relier au reste** : les exigences de performance et de couverture doivent être compatibles
   avec `ci.coverage_min` et les cibles de déploiement de `sdlc.config.yaml` ; signaler toute
   contradiction au lieu de la trancher.
8. **Faire valider** le brief (gate) avant de passer à la conception.

## Livrables et chemins exacts

- `docs/00-cadrage/brief.md` — rédigé depuis `.sdlc/templates/docs/brief.md`.
- `docs/00-cadrage/exigences-nf.md` — rédigé depuis `.sdlc/templates/docs/exigences-nf.md`.

## Critères de fin

- [ ] `brief.md` contient problème, objectifs mesurables (indicateur + cible + échéance),
      périmètre inclus/exclu, parties prenantes, risques et contraintes.
- [ ] `exigences-nf.md` couvre performance, sécurité, accessibilité, confidentialité,
      exploitabilité, compatibilité et maintenance.
- [ ] Chaque exigence est vérifiable (une méthode de mesure est indiquée).
- [ ] Aucune donnée n'est inventée : une valeur inconnue est « non mesuré ».
- [ ] Le brief est validé par le responsable du gate.

## Gate et responsable

- Gate : **brief validé** (§ 5, étape 1).
- Responsable : `gates.default` dans `sdlc.config.yaml` (par défaut `toi`).

## Pièges

- **Pas de solution technique dans le brief** : le brief décrit le problème et le résultat
  attendu ; les choix techniques relèvent des ADR (étape 2).
- **Objectif non mesurable** : sans indicateur, cible et échéance, ce n'est pas un objectif.
- **Périmètre flou** : le « hors périmètre » est aussi important que le « dans le périmètre ».
- **Accessibilité et RGPD oubliés** : les exigences non fonctionnelles sont obligatoires, pas
  optionnelles ; `restreint` (confidentialité) contraint fortement les solutions.
- **Incohérence avec la config** : une couverture cible inférieure à `ci.coverage_min` bloque la
  CI ; le signaler.
- **Ne pas franchir le gate en silence** : un brief non validé ne passe pas à l'étape 2.
