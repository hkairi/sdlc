# ai-sdlc-tracker — plugin OpenCode (copie distribuée)

Ce dossier est une **copie de travail** du plugin `ai-sdlc-tracker` du dépôt
`engagements`, distribué par `sdlc-init` vers `.opencode/plugins/ai-sdlc-tracker/`.

## Ce qu'il fait

Six outils typés (`sdlc_check`, `sdlc_track`, `sdlc_phase`, `sdlc_generate`, `sdlc_status`,
`sdlc_report`) et quatre points de contrôle (commit refusé en cas de dérive, génération après
`openspec validate <id> --strict`, signalement des écritures directes, alerte de fin de tour
désactivée par défaut).

## Limite connue — à lire avant de l'activer

Cette copie attend le **modèle d'état du dépôt d'origine** :

- un change OpenSpec dans `openspec/changes/<id>/tasks.md` ;
- un suivi HTML `docs/suivi-<id>.html` (ou `docs/suivi-multi.html`) ;
- les scripts vendorisés sous `scripts/suivi/` et `scripts/check_sync.py`.

Dans un projet installé par le framework, le suivi de la skill `suivi-taches` vit dans
`docs/suivi/state.json` et le HTML est un **rendu généré**. Le plugin n'y reconnaîtra donc pas son
périmètre et restera **inerte** (fail-open explicite : « outil inactif : aucun change OpenSpec ni
suivi reconnu »). Ce n'est pas un bug silencieux, mais ce n'est pas non plus une intégration.

L'adaptation au modèle `state.json` (lire/écrire l'état via les scripts du framework, typer les rôles
exécutant/relecteur et les itérations de revue) est un travail distinct, inscrit dans
`docs/conception/tasks.md`. En attendant :

- ne pas activer le plugin dans un projet du framework sans l'avoir testé ;
- les tests automatisés du plugin sont restés dans le dépôt d'origine (ils s'appuient sur ses
  fixtures) ; ils devront être portés avec l'adaptation.

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
