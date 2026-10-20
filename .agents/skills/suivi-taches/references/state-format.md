# Format de `docs/suivi/state.json` — format commun `suivi-taches` / `suivi-projet`

`docs/suivi/state.json` est la **source de vérité partagée** de l'état des features, de leurs
phases et de leurs tâches. Il est écrit par la skill `suivi-taches` (scripts `generate.py`,
`track*.py`, `migrate_from_html.py`) et **lu** par la skill `suivi-projet` (`collect.py`).

Deux règles non négociables :

1. **L'état ne vit plus dans le HTML.** Le fichier de suivi HTML (`docs/suivi-*.html`) est un
   **rendu généré** qui embarque une copie de cet état **en lecture seule** ; il porte la mention
   « fichier généré par la skill suivi-taches, ne pas modifier ». On ne l'édite pas à la main.
2. **Rien n'est inventé.** Un champ inconnu vaut `null` (jamais une valeur fabriquée). Un champ
   absent s'affiche « non mesuré ».

Une description formelle (JSON Schema) est fournie dans
[`state.schema.json`](state.schema.json). `collect.py` de `suivi-projet` reste compatible avec les
états écrits avant ce format : il accepte aussi `features[].phases` sous forme de **six chaînes**
de statut (`todo|doing|done|blocked`), forme historique décrite plus bas.

## Structure

```json
{
  "schema": 1,
  "meta": {
    "title": "Suivi d'avancement — Authentification SSO · Atlas",
    "h1": "Authentification SSO — fichier de suivi",
    "eyebrow": "Atlas · Authentification · Suivi d'avancement",
    "subtitle": "5 tâches · 2 lots",
    "storage_key": "suivi-auth-sso-v1",
    "lang": "fr"
  },
  "file_updated": "2026-10-11",
  "features": [
    {
      "id": "auth-sso",
      "name": "Authentification SSO",
      "color": "#eb6834",
      "change": "auth-sso",
      "objective": "Permettre la connexion via le fournisseur d'identité de l'entreprise.",
      "tasks_file": "openspec/changes/auth-sso/tasks.md",
      "sources": {
        "proposal": "openspec/changes/auth-sso/proposal.md",
        "design": "openspec/changes/auth-sso/design.md",
        "tasks": "openspec/changes/auth-sso/tasks.md",
        "specs": "openspec/changes/auth-sso/specs/sso/spec.md"
      },
      "phases": [
        {
          "id": "cadrage",
          "name": "Cadrage",
          "color": "#5c6b7a",
          "order": 1,
          "status": "done",
          "items": [
            {"id": "proposal", "label": "Proposition rédigée (proposal.md : Why / What / Impact)", "status": "done", "updated": "2026-10-02", "note": ""}
          ]
        }
      ],
      "lots": [
        {"id": "L1", "name": "1 · Socle"}
      ],
      "tasks": [
        {
          "id": "1.1",
          "lot": "L1",
          "title": "Modèle de session",
          "text": "Modèle de session **SSO** (`code` inline conservé)",
          "status": "done",
          "updated": "2026-10-10",
          "note": "Fait : table `sessions` ; vérifié : 12 tests, 0 échec.",
          "history": [
            {"date": "2026-10-09", "status": "doing", "note": "Délégué à codex."},
            {"date": "2026-10-10", "status": "done", "note": "Fait : table `sessions`."}
          ],
          "executor": "codex",
          "reviewer": "claude",
          "review_iteration": 1,
          "escalated": false,
          "ready_to_commit": true,
          "commit_message": "feat(auth): table sessions pour le SSO",
          "files": ["app/models/session.rb"],
          "acceptance": "Une session est créée à la connexion.",
          "tests": "12 tests, 0 échec"
        }
      ],
      "recette": null,
      "version": null,
      "delivered": null,
      "blocked": 0
    }
  ],
  "actions": [
    {"icon": "⏳", "text": "Spec freeze « Notifications »", "who": "client-po", "age": "depuis 1 j"}
  ],
  "envs": [
    {"name": "préprod", "version": "v1.1.0-rc1", "health": "sain", "date": "2026-10-09 14:02", "by": "pipeline #42"}
  ]
}
```

## Champs de premier niveau

| Champ | Type | Description |
|---|---|---|
| `schema` | entier | Version du format. **1** pour ce format. |
| `meta` | objet ou `null` | Métadonnées d'affichage du fichier de suivi mono (titre, sous-titre, clé localStorage). Utilisées par `render.py`. |
| `file_updated` | date `AAAA-MM-JJ` ou `null` | Date de dernière mise à jour du fichier de suivi. |
| `features` | tableau | Une entrée par chantier / change OpenSpec. |
| `actions` | tableau | Actions requises (`{icon, text, who, age}`), affichées par `suivi-projet`. Tous les champs sont du texte libre. |
| `envs` | tableau | Environnements déployés (`{name, version, health, date, by}`), lus par `suivi-projet`. Si absent, `collect.py` déduit les environnements de `docs/journal/deploys.jsonl`. |

## `features[]`

| Champ | Type | Description |
|---|---|---|
| `id` | chaîne | Identifiant de la feature, aligné sur `openspec/changes/<id>/`. |
| `name` | chaîne | Nom affiché. |
| `color` | chaîne ou `null` | Couleur CSS (pastille). Absent → couleur de la palette. |
| `change` | chaîne ou `null` | Identifiant du change OpenSpec (par défaut : `id`). |
| `objective` | chaîne ou `null` | Objectif du chantier (markdown inline). Affiché en carte réductible. |
| `decisions` | tableau de chaînes | Décisions consignées (markdown inline), affichées en carte réductible. Vide si inconnues. |
| `tasks_file` | chaîne ou `null` | Chemin du `tasks.md`, relatif à la racine. |
| `sources` | objet | Sources documentaires : `proposal`, `design`, `tasks`, `specs`, toute autre clé libre → chemin relatif. Affiché en carte « Sources ». Vides si inconnues. |
| `phases` | tableau | Les **six phases** (voir ci-dessous), dans l'ordre `cadrage`, `plan`, `impl`, `validation`, `deploy`, `cloture`. |
| `lots` | tableau | Lots : `{id, name}` (`id` = `L<n>`). |
| `tasks` | tableau | Tâches (voir ci-dessous). |
| `recette` | `[ok, total]` ou `null` | Scénarios de recette réussis / total (lu par `suivi-projet`). `null` → « — ». |
| `version` | chaîne ou `null` | Version livrée (lu par `suivi-projet`). |
| `delivered` | date ou `null` | Date de livraison (lu par `suivi-projet`). |
| `blocked` | entier | Nombre de tâches bloquées. Absent → `0`. Recalculé à chaque écriture. |

### `features[].phases[]` — les six phases

Chaque phase est un objet :

| Champ | Type | Description |
|---|---|---|
| `id` | chaîne | `cadrage`, `plan`, `impl`, `validation`, `deploy`, `cloture`. |
| `name` | chaîne | Nom affiché (`Cadrage`, `Planification`, `Implémentation`, `Validation`, `Déploiement`, `Clôture`). |
| `color` | chaîne | Couleur CSS du segment de bandeau. |
| `order` | entier | Position (1 à 6). |
| `status` | chaîne | `todo` \| `doing` \| `blocked` \| `done` — **statut dérivé** (voir ci-dessous). |
| `items` | tableau | Items de checklist : `{id, label, status, updated, note}`. La phase `impl` n'a pas d'items (état dérivé des tâches). |

**Statut dérivé** (calculé par les scripts, jamais saisi à la main) :

- phase `impl` : `done` si toutes les tâches sont `done`, sinon `blocked` si une tâche est
  `blocked`, sinon `doing` s'il y a une tâche en cours ou terminée, sinon `todo` ;
- autres phases : `done` si tous les items sont `done`, sinon `blocked` si un item est `blocked`,
  sinon `doing` si un item est `doing` ou `done`, sinon `todo`.

### `features[].tasks[]`

| Champ | Type | Description |
|---|---|---|
| `id` | chaîne | Identifiant de la tâche (`1.1`, `6bis.2`…). |
| `lot` | chaîne | Identifiant du lot (`L<n>`). |
| `title` | chaîne | Titre court. |
| `text` | chaîne | Texte complet (markdown inline : `` `code` ``, `**gras**`). |
| `status` | chaîne | `todo` \| `doing` \| `blocked` \| `done`. |
| `updated` | date ou `""` | Date de dernière mise à jour de la tâche. |
| `note` | chaîne | Note courte (HTML court toléré), remplacée à chaque `track*.py` avec note. |
| `history` | tableau | `{date, status, note}` — journal daté des changements. |
| `executor` | chaîne ou `null` | Agent / personne exécutante. |
| `reviewer` | chaîne ou `null` | Relecteur — toujours **différent** de l'exécutant. |
| `review_iteration` | entier ou `null` | Numéro d'itération de revue (1 = première revue). |
| `escalated` | booléen | `true` quand l'itération dépasse `organisation.max_review_iterations` : la tâche passe `blocked` et est signalée « escalade ». |
| `ready_to_commit` | booléen | `true` quand la tâche est prête à commiter (message proposé ci-dessous). |
| `commit_message` | chaîne ou `null` | Message de commit proposé (Conventional Commits). Affiché dans le panneau de détail. |
| `files` | tableau de chaînes | Fichiers concernés. |
| `acceptance` | chaîne ou `null` | Critères d'acceptation. |
| `tests` | chaîne ou `null` | Validation / tests. |

## Compatibilité avec `suivi-projet`

`collect.py` lit `features[].phases` et attend **six statuts**. Le format commun stocke les phases
comme des objets (voir ci-dessus) ; `collect.py` accepte les deux formes :

- **forme historique** : `"phases": ["done", "done", "doing", "todo", "todo", "todo"]` (six chaînes) ;
- **forme courante** : `"phases": [ {"id": "cadrage", "status": "done", "items": [...] }, … ]` —
  `collect.py` en déduit les six statuts à partir de `phase.status`.

Les autres champs lus par `collect.py` (`id`, `name`, `color`, `recette`, `version`, `delivered`,
`blocked`, `actions`, `envs`) gardent leur place et leur type. Les champs supplémentaires (`tasks`,
`lots`, `change`, `objective`, `sources`, rôles, historique) sont ignorés par `collect.py` sans
erreur : ils enrichissent le suivi détaillé sans le casser.

## Notes

- Le nombre de tâches n'est **pas** stocké comme compteur : `collect.py` le déduit du `tasks.md` du
  change. `suivi-taches` en revanche conserve la liste complète des tâches, indispensable au suivi
  détaillé.
- L'écriture est **atomique** : un fichier temporaire dans le même répertoire, puis un renommage.
- `migrate_from_html.py` reconstruit cet état depuis un fichier de suivi HTML antérieur (gabarit mono
  ou multi) sans rien perdre.
