#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# Copie vendorisée — source : skill suivi-taches (/Users/hkairi/.claude/skills/suivi-taches/scripts/track_multi.py)
# Copiée le 2026-10-19. Ne pas éditer ici : éditer la source, puis re-générer la copie
# avec `python3 scripts/suivi/sync_from_skill.py --write`.
# Contrôle de dérive : `python3 scripts/suivi/sync_from_skill.py --check`.
# ---------------------------------------------------------------------------
"""Met à jour l'état de référence d'une tâche dans un fichier de suivi MULTI-CHANTIERS.

Usage :
  track_multi.py --file docs/suivi-multi.html [--tasks <tasks.md>] <feature:task | task> <todo|doing|blocked|done> ["note html"]

- met à jour, dans le bloc <script id="feature-data"> du fichier :
  le statut, data-updated (aujourd'hui), la note, et ajoute une entrée d'historique datée ;
- renseigne la date de mise à jour du fichier (data-file-updated sur <body>) et la date du chantier ;
- si la tâche est désignée par son seul identifiant et qu'il est ambigu, liste les chantiers candidats ;
- si --tasks n'est pas fourni, la case est cochée/décochée dans le tasks.md du chantier (chemin
  enregistré à la génération dans le champ « tasks_file »), si ce fichier existe.
À lancer après CHAQUE progression : tâche commencée (doing), terminée (done) ou bloquée (blocked).
"""
import argparse
import datetime
import json
import os
import re
import sys

BLOCK_RE = re.compile(r'(<script type="application/json" id="feature-data">)(.*?)(</script>)', re.S)
LABELS = {"todo": "À faire", "doing": "En cours", "blocked": "Bloqué", "done": "Terminé"}


def resolve(data, ident):
    """Retourne (feature, task) à partir de 'feature:task' ou 'task'."""
    if ":" in ident:
        fid, tid = ident.split(":", 1)
        feat = next((f for f in data["features"] if f.get("id") == fid), None)
        if not feat:
            sys.exit(f"Chantier '{fid}' introuvable.")
        task = next((t for t in feat.get("tasks", []) if t.get("id") == tid), None)
        if not task:
            sys.exit(f"Tâche '{tid}' introuvable dans le chantier '{fid}'.")
        return feat, task
    hits = [(f, t) for f in data["features"] for t in f.get("tasks", []) if t.get("id") == ident]
    if not hits:
        sys.exit(f"Tâche '{ident}' introuvable.")
    if len(hits) > 1:
        ids = ", ".join(f"{f['id']}:{t['id']}" for f, t in hits)
        sys.exit(f"Identifiant '{ident}' ambigu — préciser le chantier : {ids}")
    return hits[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", required=True)
    ap.add_argument("--tasks", help="tasks.md à cocher (sinon : tasks_file du chantier)")
    ap.add_argument("ident")
    ap.add_argument("status", choices=["todo", "doing", "blocked", "done"])
    ap.add_argument("note", nargs="?")
    args = ap.parse_args()
    today = datetime.date.today().isoformat()

    src = open(args.file, encoding="utf-8").read()
    m = BLOCK_RE.search(src)
    if not m:
        sys.exit(f"Bloc feature-data introuvable dans {args.file}")
    data = json.loads(m.group(2).replace("\\u003c", "<"))
    feat, task = resolve(data, args.ident)
    key = f"{feat['id']}:{task['id']}"

    changed = task.get("status") != args.status
    task["status"] = args.status
    task["updated"] = today
    if args.note is not None:
        task["note"] = args.note

    note = args.note if args.note is not None else f"{LABELS[args.status]}."
    history = task.setdefault("history", [])
    last = history[-1] if history else None
    if changed or not last or last.get("note") != note or last.get("status") != args.status:
        history.append({"date": today, "status": args.status, "note": note})

    feat["updated"] = today
    payload = json.dumps(data, ensure_ascii=False, indent=2).replace("<", "\\u003c")
    src = src[:m.start(2)] + payload + src[m.end(2):]
    src = re.sub(r'data-file-updated="[^"]*"', f'data-file-updated="{today}"', src, count=1)
    open(args.file, "w", encoding="utf-8").write(src)

    tasks_md = args.tasks or feat.get("tasks_file")
    if tasks_md and os.path.exists(tasks_md):
        t = open(tasks_md, encoding="utf-8").read()
        mark = "x" if args.status == "done" else " "
        t2, n = re.subn(rf"^(\s*-\s+)\[[ xX]\](\s+{re.escape(task['id'])}\s)", rf"\1[{mark}]\2", t, count=1, flags=re.M)
        if n:
            open(tasks_md, "w", encoding="utf-8").write(t2)
        else:
            print(f"(avertissement) {task['id']} absent de {tasks_md}", file=sys.stderr)
    elif args.tasks:
        print(f"(avertissement) {args.tasks} introuvable", file=sys.stderr)

    print(f"{key} -> {args.status}")


if __name__ == "__main__":
    main()
