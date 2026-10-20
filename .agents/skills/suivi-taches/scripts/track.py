#!/usr/bin/env python3
"""track.py — met à jour une tâche du suivi dans `state.json` puis régénère le HTML.

Usage :
  track.py --file docs/suivi-<id>.html [--state docs/suivi/state.json] \
      [--tasks openspec/changes/<id>/tasks.md] \
      [--executor <agent>] [--reviewer <agent>] [--iteration <n>] \
      [--commit-message "…"] [--ready-to-commit] \
      <tâche> <todo|doing|blocked|done> ["note html"]

- écrit le statut, la date et la note dans `state.json` (écriture atomique) ;
- ajoute une entrée d'historique datée ;
- pose les rôles (exécutant, relecteur, itération de revue) — refuse un relecteur égal à
  l'exécutant ; au-delà de `organisation.max_review_iterations` (défaut 3), la tâche passe
  `blocked` avec `escalated=true` ;
- coche/décoche la case du `tasks.md` ;
- régénère le HTML (`render.py`).

À lancer après CHAQUE progression : tâche commencée (doing), terminée (done) ou bloquée (blocked).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import tracking  # noqa: E402

if __name__ == "__main__":
    sys.exit(tracking.task_update_main(__doc__))
