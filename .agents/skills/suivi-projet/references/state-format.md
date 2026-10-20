# Format de `docs/suivi/state.json`

> **Le format complet et canonique est documenté dans
> [`../../suivi-taches/references/state-format.md`](../../suivi-taches/references/state-format.md)**
> (schéma JSON : `../../suivi-taches/references/state.schema.json`). Ce document ne décrit que ce
> dont `collect.py` a besoin pour le tableau de bord, et rappelle la rétrocompatibilité.

`docs/suivi/state.json` est la **source de vérité partagée** de l'état des features. Il est écrit
par la skill `suivi-taches` et **lu** par `collect.py` (lecture seule). Une donnée absente ou nulle
s'affiche « non mesuré » : **rien n'est inventé**.

Les nombres de tâches ne figurent **pas** dans ce fichier de façon comptable : `collect.py` les
déduit du `tasks.md` du change OpenSpec dont l'`id` correspond à celui de la feature (les changes
archivés comptent toutes leurs tâches comme terminées).

## Ce que `collect.py` lit

```json
{
  "features": [
    {
      "id": "auth-sso",
      "name": "Authentification SSO",
      "color": "#eb6834",
      "phases": ["done", "done", "doing", "todo", "todo", "todo"],
      "blocked": 1,
      "recette": null,
      "version": null,
      "delivered": null
    }
  ],
  "actions": [
    { "icon": "⏳", "text": "Spec freeze « Notifications »", "who": "client-po", "age": "depuis 1 j" }
  ],
  "envs": [
    { "name": "préprod", "version": "v1.1.0-rc1", "health": "sain", "date": "2026-10-09 14:02", "by": "pipeline #42" }
  ]
}
```

### `features[]`

| Champ | Type lu par `collect.py` | Description |
|---|---|---|
| `id` | chaîne | Aligné sur `openspec/changes/<id>/`. |
| `name` | chaîne | Nom affiché. |
| `color` | chaîne | Couleur CSS (pastille). Absent → palette. |
| `phases` | 6 statuts | `todo` \| `doing` \| `done` \| `blocked`. **Deux formes acceptées** (voir plus bas). |
| `blocked` | entier | Nombre de tâches bloquées. Absent → `0`. |
| `recette` | `[ok, total]` ou `null` | Scénarios de recette réussis / total. `null` → « — ». |
| `version` | chaîne ou `null` | Version livrée. |
| `delivered` | date ou `null` | Date de livraison. |

Les champs **supplémentaires** du format commun (`change`, `objective`, `tasks_file`, `sources`,
`lots`, `tasks`, rôles, historique, `escalated`, `ready_to_commit`, `commit_message`, `meta`,
`file_updated`…) sont ignorés par `collect.py` sans erreur.

### Formes de `phases` acceptées

1. **forme courante** (écrite par `suivi-taches`) : un tableau de six **objets** de phase
   `{id, name, color, order, status, items}` ; `collect.py` lit `phase.status` via
   `normalize_phases` :
   ```json
   "phases": [
     {"id": "cadrage", "status": "done", "items": [ … ]},
     …
   ]
   ```
2. **forme historique** : un tableau de six **chaînes** de statut
   `["done", "done", "doing", "todo", "todo", "todo"]`.

Toute autre valeur retombe sur six `todo` (non mesuré), sans erreur.

### `actions[]`

Actions requises de l'onglet « Vue d'ensemble » : `{ "icon", "text", "who", "age" }` (texte libre).

### `envs[]`

Environnements déployés : `{ "name", "version", "health", "date", "by" }`. `health` = `sain` ou
autre (affiché en alerte). Si `envs` est absent, `collect.py` déduit les environnements du dernier
déploiement de chaque environnement dans `docs/journal/deploys.jsonl`.

Un change OpenSpec **en cours** absent de `features` est ajouté automatiquement comme feature
(phase `Implémentation` en cours) : c'est une dérivation de source, pas une invention.

## Incidents (`docs/incidents/*.md`)

En-tête simple lu par `collect.py` :

```markdown
# INC-001 — Échec de migration en préproduction

- Statut : ouvert
- Date : 2026-09-28
```

- Le titre suit `#` ; l'identifiant `INC-NNN` en tête (sinon le nom du fichier).
- `Statut` : `ouvert` (défaut) ou `clos` / `résolu`.
- `Date` : date affichée.
