# ai-sdlc-tracker — plugin OpenCode

Applique la règle de suivi d'avancement **dans la session** : six outils typés et quatre points de
contrôle. La méthode (phases, critères d'acceptation, pédagogie) reste dans la skill `suivi-taches` ;
ce plugin ne fait que l'exécuter et la contrôler.

## Ce qu'il fait

| Outil | Rôle |
|---|---|
| `sdlc_check` | Contrôle suivi ↔ `tasks.md` (un change, tous les changes, ou chemins touchés). Même verdict que le hook git et la CI. |
| `sdlc_track` | Statut + note + case de `tasks.md` en une opération. Refuse un `done` sans preuve et une deuxième tâche `doing` dans le même lot. |
| `sdlc_phase` | Coche un item de phase (`validation.tests`, `cloture.archive`…). La phase `impl` est dérivée : passer par `sdlc_track`. |
| `sdlc_generate` | Crée ou régénère un suivi sans perte (mono) ou le suivi multi. Jamais tous les suivis d'un coup. |
| `sdlc_status` | État en lecture seule : progression, tâches en cours depuis plus de 7 jours, `done` sans preuve, dérives. |
| `sdlc_report` | Rapport de clôture HTML autonome dans `docs/rapport-<change>.html`. |
| `sdlc_doctor` | Contrôle de santé en lecture seule : configuration, scripts, hook git, baseline, Python. Conclut « prêt » ou « à corriger ». |

Points de contrôle :

1. **Commit refusé** si le suivi des chemins touchés dérive (`git diff --cached`, sinon `git status`).
2. **Génération automatique** après `openspec validate <id> --strict` réussi — création si le suivi manque.
3. **Signalement** après toute écriture directe de `tasks.md` ou d'un suivi (jamais de refus).
4. **Alerte de fin de tour** si une dérive subsiste — **désactivée par défaut** (`alertOnIdle: true`).

**Le plugin n'ouvre jamais un fichier.** Après une génération, le message le rappelle : demander à
l'utilisateur s'il veut l'ouvrir (`open docs/suivi-<id>.html`), et n'ouvrir qu'après accord.

## Foyer de développement

Le code se développe **uniquement** dans
`AI-DRIVEN-SDLC/templates/adapters/opencode/plugins/ai-sdlc-tracker/` : c'est là que vivent
les tests, le typecheck et la CI. Une installation (par exemple
`engagements/.opencode/plugins/ai-sdlc-tracker/`) est une **copie non éditée** : elle se met à
jour par copie, jamais par modification sur place.

```bash
bin/plugin-sync-check --target /chemin/du/projet/.opencode/plugins/ai-sdlc-tracker
```

Sortie 0 = conforme ; 1 = dérive, avec le fichier nommé. Le contrôle ignore `node_modules/`,
`tests/`, `README.md` et `GUIDE.md`.

## Configuration

Une seule source : les options passées au plugin dans `opencode.json(c)` du dépôt.

```jsonc
{
  "plugins": [
    {
      "package": "./.opencode/plugins/ai-sdlc-tracker",
      "options": {
        "projectName": "MonProjet"
      }
    }
  ]
}
```

| Option | Défaut | Effet |
|---|---|---|
| `enabled` | `true` | Coupe tous les enregistrements. |
| `autoGenerate` | `true` | Génération après validation stricte. |
| `blockCommit` | `true` | Refus d'un commit en dérive. |
| `blockNextTask` | `true` | Une seule tâche `doing` par lot. |
| `requireEvidence` | `true` | Indice de vérification exigé pour `done`. |
| `alertOnIdle` | `false` | Alerte synthétique en fin de tour. |
| `strict` | `false` | Dépôt non reconnu = erreur au lieu de l'inactivité. |
| `projectName` | nom du dépôt | Titre et en-tête des suivis générés (déduit de `basename` s'il n'est pas fourni). |
| `checkScript` | `scripts/check_sync.py` | Script de contrôle (chemin relatif au dépôt). |
| `scriptsDir` | `scripts/suivi` | Racine de la vendorisation : `<scriptsDir>/scripts/*.py`, `<scriptsDir>/assets/*`. |
| `pythonBin` | `python3` (`python` sous Windows) | Binaire Python utilisé pour les scripts. |
| `commandTimeoutMs` | `10000` | Délai maximal d'une commande (`python3`, `git`) ; au-delà : code 124 et message explicite. |

**Interrupteur d'urgence** : `AI_SDLC_TRACKER=off git commit …` (ou dans l'environnement de la session)
désactive tous les blocages, sans retirer le plugin ni modifier la configuration.

## Où vivent les règles

Le plugin n'invente aucune règle : il appelle les scripts du dépôt (copie vendorisée de la skill
`suivi-taches`, `scripts/suivi/`). Le motif de preuve (`EVIDENCE_RE`) est **extrait** de
`scripts/check_sync.py`, et un test échoue si les deux règles divergent.

## Dépannage

| Symptôme | Cause probable / action |
|---|---|
| Aucun outil `sdlc_*` | Le plugin n'a pas chargé. Chercher `loading plugin` / `failed to load plugin` dans `~/.local/share/opencode/log/opencode.log`. |
| « outil inactif : aucun change OpenSpec ni suivi » | Dépôt hors périmètre : comportement fail-open voulu. `strict: true` pour en faire une erreur. |
| Commit refusé à tort | Lire le détail : il nomme la tâche et les deux fichiers. Corriger avec `sdlc_track`, ou `AI_SDLC_TRACKER=off` en urgence. |
| `scripts/suivi/… introuvable` | Vendorisation absente : `python3 scripts/suivi/sync_from_skill.py --write`. |
| Scripts modifiés à la main | `python3 scripts/suivi/sync_from_skill.py --check` : compare à la skill (local) ou au manifeste (CI). |

## Tests

```bash
cd .opencode/plugins/ai-sdlc-tracker
npm ci             # dépendances épinglées (package-lock)
npm test           # node --test sur les fichiers *.test.ts
npm run typecheck  # tsc --noEmit (strict)
```

La CI exécute exactement ces commandes sur Node 22, 24 et 26 (`.github/workflows/ai-sdlc-tracker.yml`).

Les tests n'écrivent pas dans le dépôt : exécuteur de scripts et git simulés, répertoires temporaires.

## Compatibilité et montée de version

| Élément | Version |
|---|---|
| OpenCode | 2.0.32 (API V2 des plugins) |
| Node | ≥ 22.18 (exécution native des `.ts`) ; testé en 22, 24, 26 |
| Python | ≥ 3.9 |
| `@opencode/plugin` | 2.0.32 (épinglé) |

Une montée d'`@opencode/plugin` n'est acceptée qu'après : `npm test`, `npm run typecheck`, et une
vérification réelle du chargement dans OpenCode (log `loading plugin` + outils `sdlc_*` dans le
catalogue). L'API V2 a déjà cassé un plugin de ce dépôt : la version se traite comme une dépendance
de production, pas comme un détail.

## Dette historique

`scripts/suivi/baseline.json` (généré par `python3 scripts/suivi/baseline.py --write`) fige les
problèmes connus à une date. `sdlc_status` les distingue du neuf. On régénère la baseline **après**
avoir résorbé la dette, jamais pour faire taire un problème nouveau.
