---
name: spec-review
description: Conteste un change OpenSpec avant le gate spec_freeze — vérifie les scénarios manquants, les cas limites, la gestion des erreurs, la sécurité, l'accessibilité (RGAA), la cohérence avec les ADR acceptés et les exigences non fonctionnelles, puis écrit un avis en Markdown dans openspec/changes/<id>/review.md. Utiliser à l'étape 3 quand l'utilisateur demande une « revue de spec », une « contestation de change OpenSpec », de « challenger une spec », de « vérifier les scénarios », ou juste avant de figer la spec (spec freeze) ; le contradicteur ne doit jamais être l'auteur du change.
---

# Contestation d'un change OpenSpec (`spec-review`)

> **Chemins.** Les emplacements viennent de la section `paths` de `sdlc.config.yaml`
> (§ 13.3 de `.sdlc/workflow-sdlc.md`) : gabarits sous `paths.templates` (défaut
> `.sdlc/templates`), spec sous `paths.spec`, livrables sous les dossiers `paths.*`
> (défauts indiqués dans cette fiche).

## Objectif

Chercher les failles d'un change OpenSpec **avant** de le figer : scénarios manquants, cas
limites, erreurs, sécurité, accessibilité, cohérence avec les ADR et les exigences non
fonctionnelles. La sortie est un avis écrit, pas une approbation de complaisance.

## Quand l'utiliser

- Étape 3, une fois le change OpenSpec rédigé et **avant** le gate `spec_freeze`.
- L'utilisateur demande une revue de spec, de contester un change, de challenger les scénarios,
  ou de vérifier la cohérence avec les ADR et les exigences non fonctionnelles.

## Entrées

1. `sdlc.config.yaml` : `gates.spec_freeze`, `confidentiality`, `ci.coverage_min`, `ci.block_on`.
2. Le change OpenSpec : `openspec/changes/<id>/proposal.md`, `design.md`, les deltas de spec
   (exigences + scénarios), `tasks.md`.
3. Les ADR acceptés : `docs/architecture/adr/ADR-NNN.md` et l'index `README.md`.
4. Les exigences non fonctionnelles : `docs/00-cadrage/exigences-nf.md` et le brief.
5. La grille : `references/grille-contestation.md` (dans ce dossier de skill).

## Étapes

1. **Vérifier l'indépendance.** Le contradicteur est différent de l'auteur du change. Si les
   rôles se confondent, s'arrêter et le signaler.
2. **Lire le change et ses références** : proposal, design, deltas, tasks ; ADR ; exigences NF.
3. **Parcourir la grille** de `references/grille-contestation.md`, section par section :
   - scénarios manquants (un besoin du proposal sans scénario Given/When/Then) ;
   - cas limites (vides, bornes, concurrence, volumes, dates, caractères spéciaux, états
     intermédiaires) ;
   - gestion des erreurs (échec d'un service, timeout, entrée invalide, reprise, message
     d'erreur) ;
   - sécurité (authentification, autorisation, journalisation, données sensibles, injection,
     conformité à `confidentiality`) ;
   - accessibilité RGAA/WCAG (contraste, clavier, libellés, alternatives, focus) ;
   - cohérence avec les ADR acceptés (citer l'ADR concerné) ;
   - cohérence avec les exigences non fonctionnelles (citer l'exigence concernée) ;
   - traçabilité et testabilité (chaque exigence vérifiable par un test) ;
   - impacts recette, déploiement, exploitation.
4. **Qualifier chaque constat** : gravité `bloquante`, `majeure` ou `mineure`, avec une référence
   précise (exigence, scénario, ADR) et une proposition. Ne pas trancher une ambiguïté en
   silence : la signaler.
5. **Écrire l'avis** dans `openspec/changes/<id>/review.md` à partir de
   `references/grille-contestation.md`, commentaires de consigne supprimés.
6. **Rendre le verdict** : `prêt pour spec_freeze` ou `non prêt`, avec le décompte des
   contestations par gravité. Le gate est passé par le responsable de `gates.spec_freeze`.

## Livrables et chemins exacts

- `openspec/changes/<id>/review.md` — l'avis de contestation, rédigé depuis
  `references/grille-contestation.md`.

**Lecture seule sur tout le reste** : `spec-review` ne modifie ni le change OpenSpec, ni le code,
ni la documentation. Toute correction passe par l'auteur du change (voie `change-request` si la
spec est déjà gelée).

## Critères de fin

- [ ] Le contradicteur est distinct de l'auteur.
- [ ] Les neuf sections de la grille sont parcourues (marquées « conforme » si sans objet).
- [ ] Chaque constat porte une référence, une gravité et une proposition.
- [ ] `openspec/changes/<id>/review.md` est écrit et se termine par un verdict explicite.
- [ ] Aucun fichier hors de `review.md` n'a été modifié.

## Gate et responsable

- Gate : **spec freeze** (§ 5, étape 3).
- Responsable : `gates.spec_freeze` dans `sdlc.config.yaml` (par défaut `client-po`).

## Correspondance des rôles

Le contradicteur est un agent en **lecture seule**, avec un autre modèle que l'auteur. Les
adaptateurs fournissent à cet effet un agent `spec-challenger` pour chaque outil :

| Outil | Agent | Levier de lecture seule |
|---|---|---|
| Claude Code | `spec-challenger` | `disallowedTools` (retire `Edit`, `Write`, `NotebookEdit`) |
| Codex | `spec-challenger` | `sandbox_mode = "read-only"` |
| OpenCode | `spec-challenger` | `permission.edit: deny` et `permission.write: deny` |

## Pièges

- **Contradicteur = auteur** : la revue n'a pas de valeur ; refuser et réassigner.
- **Approbation par défaut** : l'objectif est de contester, pas de valider ; « conforme » ne
  s'écrit qu'après vérification.
- **Constat sans référence** : une remarque sans exigence, scénario ou ADR cité n'est pas
  exploitable.
- **Modifier le change** : interdit ; proposer, l'auteur corrige. Après `spec_freeze`, passer par
  `change-request`.
- **Accessibilité et sécurité oubliées** : ce sont des sections obligatoires de la grille.
- **Ambiguïté tranchée en silence** : la signaler (gravité `majeure` au minimum).
- **Secrets et git** : ne rien lire de sensible ; aucune commande git en écriture.
