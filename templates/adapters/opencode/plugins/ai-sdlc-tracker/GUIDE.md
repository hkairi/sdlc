# ai-sdlc-tracker — plugin OpenCode (copie distribuée)

Ce dossier est le **foyer de développement** du plugin `ai-sdlc-tracker` (tests, typecheck, CI).
`render_adapters.py` en distribue les fichiers — hors `tests/`, `node_modules/` et `README.md` —
vers `.opencode/plugins/ai-sdlc-tracker/` du projet cible. Une installation est une **copie non
éditée** : on la met à jour par copie, et on vérifie avec
`bin/plugin-sync-check --target <installation>`.

## Ce qu'il fait

Six outils typés (`sdlc_check`, `sdlc_track`, `sdlc_phase`, `sdlc_generate`, `sdlc_status`,
`sdlc_report`) et quatre points de contrôle (commit refusé en cas de dérive, génération après
`openspec validate <id> --strict`, signalement des écritures directes, alerte de fin de tour
désactivée par défaut).

## Modèle d'état

Le plugin lit la **source de vérité** `docs/suivi/state.json` (schéma 1) et considère le HTML
(`docs/suivi-*.html`) comme un rendu généré, jamais comme une source. Il :

- détecte le périmètre (`docs/suivi/state.json` ou un change OpenSpec) ;
- résout la feature par `features[].id` aligné sur `openspec/changes/<id>/` ;
- lit les rôles (`executor`, `reviewer`, `review_iteration`, `escalated`, `ready_to_commit`,
  `commit_message`) et signale un relecteur absent ou égal à l'exécutant ;
- délègue l'écriture et la génération aux scripts de la skill `suivi-taches` (`track.py`,
  `track_phase.py`, `generate.py`) — la règle « relecteur ≠ auteur » et l'escalade y sont appliquées.

Les tests (81) sont autonomes : ils ne dépendent d'aucun dépôt hôte.

## Configuration

```jsonc
{
  "plugins": [
    {
      "package": ".opencode/plugins/ai-sdlc-tracker",
      "options": { "projectName": "{{nom-du-projet}}" }
    }
  ]
}
```

Options : `enabled`, `autoGenerate`, `blockCommit`, `blockNextTask`, `requireEvidence`,
`alertOnIdle`, `strict`, `projectName`, `checkScript`, `scriptsDir`. Interrupteur d'urgence :
`AI_SDLC_TRACKER=off`.

## Vérifier qu'il charge

```bash
rg "failed to load plugin|loading plugin" ~/.local/share/opencode/log/opencode.log | tail -5
```

Un plugin présent mais non chargé est exactement le piège que ce plugin remplace : ne jamais
considérer l'installation comme faite sans cette vérification (et sans les outils `sdlc_*` dans le
catalogue).
