#!/usr/bin/env python3
"""track_phase.py — met à jour un item de checklist de phase dans `state.json` puis régénère le HTML.

Usage :
  track_phase.py --file docs/suivi-multi.html [--feature <id>] \
      <phase>.<item> <todo|doing|blocked|done> ["note"]
  track_phase.py --file docs/suivi-<id>.html validation.tests done "36 runs, 0 échec."
  track_phase.py --file docs/suivi-multi.html bpay:deploy.migrations doing "Migration en écriture."

- pose le statut, la date et, si fournie, la note de l'item dans `state.json` (écriture atomique) ;
- recalcule le statut dérivé de chaque phase ;
- régénère le HTML.

Phases : cadrage, plan, impl (dérivée des tâches, non modifiable via ce script), validation,
deploy, cloture.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import tracking  # noqa: E402

if __name__ == "__main__":
    sys.exit(tracking.phase_update_main(__doc__))
