# Tasks — tracker-ui-reports

## 1. Coquille de rendu

- [x] 1.1 `assets/template.html` (mono) : barre latérale marine, barre supérieure, PAI/KPI, thème clair/sombre persistant.
- [x] 1.2 `assets/template-multi.html` (multi) : même coquille, rail des chantiers conservé.
- [x] 1.3 `tools/report-template.ts` (rapport de clôture) : cartes KPI, badges, bascule de thème.

## 2. Menu Rapport de clôture

- [x] 2.1 `render.py` : détection de `docs/rapport-<change>.html` par convention, placeholders `RAPPORT_NAV`/`RAPPORT_BTN`/`RAPPORT_SECTION`.
- [x] 2.2 Mono : lien conditionnel dans la barre latérale + bouton, panneau `<iframe>` + « ouvrir dans un onglet ».
- [x] 2.3 Multi : lien « Rapport » par chantier (nouvel onglet).
- [x] 2.4 `render.py` : `PROJECT`/`MARK`/`CHANGE` pour la coquille.

## 3. Sélection de phase

- [x] 3.1 Une seule phase ouverte à la fois (clic déterministe).
- [x] 3.2 Phase en cours ouverte par défaut (en l'absence de choix mémorisé).
- [x] 3.3 Sélection visible sur une phase terminée (anneau + bordure).

## 4. Baseline de dette

- [x] 4.1 `baseline.py` déplacé dans la skill, lecture de `docs/suivi/state.json`, écriture de `baseline.json` à la racine de la skill.
- [x] 4.2 Suppression de la copie legacy `scripts/suivi/` et réécriture de `test_baseline_ratchet.sh`.

## 5. Vérifications

- [x] 5.1 Tests `suivi-taches` verts (dont lien conditionnel du rapport, coquille mono).
- [x] 5.2 Tests plugin `ai-sdlc-tracker` verts (rapport autonome avec script en ligne minimal).
- [x] 5.3 Fixtures du plugin resynchronisées ; installations et suivi régénérés.
- [x] 5.4 `openspec validate tracker-ui-reports --strict` sans erreur.
