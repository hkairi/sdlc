## Context

Le plugin applique la règle de synchronisation `tasks.md` ↔ suivi. Dans le dépôt d'origine, le suivi
est un **HTML** (`docs/suivi-<id>.html` mono ou `docs/suivi-multi.html` multi) qui embarque l'état.
Le framework a migré vers `docs/suivi/state.json` (schéma 1) comme source de vérité ; le HTML est un
rendu généré par la skill `suivi-taches`.

Le plugin est aujourd'hui copié tel quel : dans un projet du framework, il ne trouve ni
`docs/suivi-*.html` ni `scripts/suivi/`, donc `detectScope` renvoie `none` et il reste inerte
(fail-open). Il ignore aussi les champs de rôles (`executor`, `reviewer`, `review_iteration`,
`escalated`, `ready_to_commit`, `commit_message`) du format commun.

## Goals / Non-Goals

**Goals:**

- Le plugin lit l'état dans `docs/suivi/state.json` et y écrit via les scripts de `suivi-taches`.
- Le HTML n'est plus une source de vérité : il n'est ni lu ni écrit par le plugin.
- La règle « relecteur ≠ auteur » est appliquée, avec les itérations et l'escalade.
- Les 77 tests passent dans un projet du framework, sans accès au dépôt d'origine.

**Non-Goals:**

- Réécrire les scripts `track*.py` / `state_io.py` de la skill `suivi-taches` (le plugin les appelle,
  il ne les réimplémente pas — cohérent avec « scripts de référence uniques »).
- Générer le HTML (c'est la skill `suivi-taches` qui le fait).
- Supporter le modèle HTML historique en parallèle (le plugin lit `state.json`, point).

## Decisions

- **Lecture** : `state.json` est lu par le plugin (JSON natif, `node:fs`, `JSON.parse`). Les champs
  `features[].tasks[]` portent `id`, `lot`, `status`, `updated`, `note`, `title`, `executor`,
  `reviewer`, `review_iteration`, `escalated`, `ready_to_commit`, `commit_message`.
- **Écriture** : le plugin appelle les scripts de la skill `suivi-taches` (`track.py` pour une tâche,
  `track_phase.py` pour une phase, `generate.py` pour la génération) avec les mêmes arguments ; il ne
  réécrit pas le JSON lui-même (l'atomicité est garantie par les scripts).
- **Sécurité de l'invocation** : le chemin de chaque script est résolu **sous** le répertoire de la
  skill `suivi-taches` ; tout chemin hors périmètre est refusé (erreur interne journalisée, jamais
  exécutée). Cela borne la surface d'exécution à des scripts connus du framework.
- **Cible** : `docs/suivi/state.json` est la cible unique ; la feature est résolue par
  `features[].id` aligné sur `openspec/changes/<id>/`.
- **Détection du périmètre** : `detectScope` détecte `docs/suivi/state.json` (et/ou des changes
  OpenSpec) ; sinon `none` (inerte).
- **Règle « relecteur ≠ auteur »** : à la clôture (`done`) d'une tâche, si `reviewer` est défini et
  égal à `executor`, l'opération est refusée (ou signalée en mode non strict). L'escalade suit
  `organisation.max_review_iterations` lu dans `sdlc.config.yaml`.
- **Dépassement** : inchangé (commandes externes bornées à 10 s par défaut).

## Risks / Trade-offs

- Le format `state.json` est plus riche que le HTML : le plugin ne lit que les champs utiles et
  ignore le reste (« rien n'est inventé »).
- Le port des 77 tests est le principal effort ; les fixtures du dépôt d'origine sont remplacées par
  des fixtures `state.json` autonomes.
