---
name: adr
description: Crée et maintient les Architecture Decision Records (ADR) à l'étape 2 — numérotation ADR-NNN automatique depuis docs/architecture/adr/, création du fichier depuis .sdlc/templates/docs/adr.md, statuts (proposé, accepté, rejeté, déprécié, remplacé) et mise à jour de l'index docs/architecture/adr/README.md. Utiliser dès que l'utilisateur demande un « ADR », un « Architecture Decision Record », de « documenter une décision d'architecture », de « choisir la cible de déploiement et la CI », de « tracer les alternatives rejetées » ou de passer le gate « ADR acceptés ».
---

# Architecture Decision Records (`adr`)

> **Chemins.** Les emplacements viennent de la section `paths` de `sdlc.config.yaml`
> (§ 13.3 de `.sdlc/workflow-sdlc.md`) : gabarits sous `paths.templates` (défaut
> `.sdlc/templates`), spec sous `paths.spec`, livrables sous les dossiers `paths.*`
> (défauts indiqués dans cette fiche).

## Objectif

Tracer chaque décision d'architecture dans un ADR daté, numéroté et indexé, avec son contexte,
sa décision, ses conséquences et les alternatives rejetées. C'est l'étape 2 : les ADR acceptés
contraignent ensuite la spec et l'implémentation.

## Quand l'utiliser

- Étape 2, après validation du brief (étape 1).
- L'utilisateur demande un ADR, de documenter un choix technique, de comparer des alternatives,
  ou de décider la cible de déploiement et la CI.
- Un ADR doit être remplacé ou déprécié (nouvel ADR lié, statut mis à jour).

## Entrées

1. `sdlc.config.yaml` : `project.name`, `deploy.decided_at`, `deploy.targets`, `ci.tool`,
   `confidentiality`, `gates`.
2. `docs/00-cadrage/brief.md` et `docs/00-cadrage/exigences-nf.md`.
3. `docs/00-cadrage/etat-des-lieux.md` si le projet est existant.
4. Les gabarits :
   - `.sdlc/templates/docs/adr.md` (format statut, contexte, décision, conséquences, alternatives) ;
   - `.sdlc/templates/docs/adr-index.md` (index) ;
   - `.sdlc/templates/docs/menaces.md` (analyse STRIDE légère, à joindre à la conception).

## Étapes

1. **Identifier les décisions à tracer.** Au minimum : la ou les décisions structurantes du
   projet, la **cible de déploiement et la CI** (obligatoire si
   `deploy.decided_at: conception`), et tout choix contraint par la confidentialité
   (`confidentiality: restreint`).
2. **Créer l'ADR** :
   ```sh
   python3 .agents/skills/adr/scripts/new_adr.py . --titre "Titre de la décision"
   ```
   Le script attribue le numéro suivant, crée `docs/architecture/adr/ADR-NNN.md` depuis
   `.sdlc/templates/docs/adr.md` et met à jour `docs/architecture/adr/README.md`. Options :
   `--statut` (`proposé` par défaut), `--date AAAA-MM-JJ`, `--dry-run`.
3. **Rédiger le contenu** : contexte, décision explicitement vérifiable, conséquences positives
   et négatives, alternatives sérieusement envisagées et raison du rejet. Supprimer les
   commentaires de consigne au profit du contenu définitif ; laisser les marqueurs `{{…}}`
   non renseignés visibles plutôt que d'inventer.
4. **Statuer** : passer le statut de `proposé` à `accepté` après revue, ou à `rejeté`. Un ADR
   `remplacé` renvoie à l'ADR de remplacement (champ « Remplacé par ») et l'index est mis à jour.
5. **Index** : `docs/architecture/adr/README.md` liste chaque ADR (numéro, titre, statut, date
   d'acceptation) et, dans « ADR remplacés », les remplacements.
6. **Analyse des menaces** : produire `docs/architecture/menaces.md` depuis
   `.sdlc/templates/docs/menaces.md` pour les composants exposés (STRIDE léger), avec mitigation et
   plan de traitement pour les risques critiques ou hauts.
7. **Faire accepter les ADR** (gate) avant de passer aux specs (étape 3).

## Livrables et chemins exacts

- `docs/architecture/adr/ADR-NNN.md` — un fichier par décision, depuis `.sdlc/templates/docs/adr.md`.
- `docs/architecture/adr/README.md` — index, depuis `.sdlc/templates/docs/adr-index.md`.
- `docs/architecture/menaces.md` — analyse des menaces, depuis `.sdlc/templates/docs/menaces.md`.
- Schémas d'architecture dans `docs/architecture/` (générés, HTML/SVG + PNG).

## Critères de fin

- [ ] Chaque ADR a un numéro unique, un titre, un statut et une date.
- [ ] Le contenu distingue contexte, décision, conséquences (positives et négatives) et
      alternatives rejetées.
- [ ] Un ADR « Cible de déploiement et CI » existe si `deploy.decided_at: conception`.
- [ ] L'index `README.md` reflète tous les ADR et les remplacements.
- [ ] Les ADR sont acceptés par le responsable du gate.

## Gate et responsable

- Gate : **ADR acceptés** (§ 5, étape 2).
- Responsable : `gates.default` dans `sdlc.config.yaml` (par défaut `toi`).

## Pièges

- **Décision non vérifiable** : une décision qui n'indique pas de critère observable n'est pas un
  ADR.
- **Alternatives absentes** : un ADR sans alternatives rejetées ne documente pas le choix.
- **Statut oublié** : un ADR laissé `proposé` ne contraint rien ; il ne passe pas le gate.
- **Numérotation manuelle** : toujours passer par `new_adr.py` pour éviter les collisions.
- **Incohérence avec la config** : un ADR de déploiement doit citer un profil autorisé (§ 4) ;
  sinon le signaler.
- **Marqueurs inventés** : ne jamais remplir un `{{…}}` par une valeur sans source ; laisser
  visible et signaler.
- **Git** : aucune commande git en écriture ; proposer un message de commit pour les fichiers
  ajoutés.
