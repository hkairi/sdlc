#!/usr/bin/env python3
"""track_multi.py — met à jour une tâche d'un suivi multi-chantiers dans `state.json`.

Usage :
  track_multi.py --file docs/suivi-multi.html [--state docs/suivi/state.json] \
      [--tasks <tasks.md>] [--feature <id>] \
      [--executor <agent>] [--reviewer <agent>] [--iteration <n>] \
      [--commit-message "…"] [--ready-to-commit] \
      <chantier:tâche | tâche> <todo|doing|blocked|done> ["note html"]

Identique à `track.py` (mêmes arguments), avec résolution multi-chantiers : `chantier:tâche`,
ou `tâche` seule si l'identifiant est unique. Écrit `state.json` (atomique), synchronise la case
du `tasks.md`, applique les rôles et l'escalade, puis régénère le HTML.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import tracking  # noqa: E402

if __name__ == "__main__":
    sys.exit(tracking.task_update_main(__doc__))
