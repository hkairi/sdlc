# Change: Refonte de l'UI du tracker, menu Rapport et baseline rebranchée

## Why

Le suivi d'avancement (`suivi-*.html`) ne correspondait plus à la charte validée
(`docs/mockup-framework.html`) : en-tête mono-colonne, pas de thème clair/sombre, pas de barre
latérale. Le rapport de clôture (`sdlc_report`) n'était accessible par aucun lien : il fallait
connaître son chemin. Enfin, la **baseline de dette** (`baseline.py`) vivait dans une copie legacy
`scripts/suivi/`, divergente de la skill, et écrivait `baseline.json` à un endroit où le plugin ne
le lisait pas — la fonctionnalité était donc découplée.

## What Changes

- **Coquille de rendu commune** aux suivis mono, multi et au rapport de clôture : barre latérale
  marine, barre supérieure, cartes/KPI, **thème clair/sombre** persistant.
- **Menu « Rapport de clôture »** dans le suivi : lien conditionnel (affiché seulement si
  `docs/rapport-<change>.html` existe) qui ouvre le rapport **dans le tracker** (panneau `<iframe>`,
  avec un bouton « ouvrir dans un onglet »).
- **Sélection des phases** : une seule phase ouverte à la fois, phase en cours ouverte par défaut,
  et sélection nettement visible quel que soit le statut de la phase.
- **Baseline de dette rebranchée** : `baseline.py` déplacé dans la skill
  (`scripts/baseline.py`), lit `docs/suivi/state.json`, écrit `baseline.json` à la racine de la
  skill ; suppression de la copie legacy `scripts/suivi/`.
- Le **rapport de clôture** adopte la même charte (KPI, badges, bascule de thème).

## Impact

- Spec affectée : `sdlc-tracking` (coquille de rendu, menu rapport, sélection de phase, baseline).
- Fichiers : `.agents/skills/suivi-taches/assets/template.html`,
  `template-multi.html`, `scripts/render.py`, `scripts/baseline.py` ;
  `templates/adapters/opencode/plugins/ai-sdlc-tracker/tools/report-template.ts`.
- Aucune rupture d'API : `state.json` reste la source de vérité, le format ne change pas.
