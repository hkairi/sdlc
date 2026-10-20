#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# Copie vendorisée — source : skill suivi-taches (/Users/hkairi/.claude/skills/suivi-taches/scripts/track.py)
# Copiée le 2026-10-19. Ne pas éditer ici : éditer la source, puis re-générer la copie
# avec `python3 scripts/suivi/sync_from_skill.py --write`.
# Contrôle de dérive : `python3 scripts/suivi/sync_from_skill.py --check`.
# ---------------------------------------------------------------------------
"""Met à jour l'état de référence d'une tâche dans un fichier de suivi HTML.

Usage :
  track.py --file docs/suivi-<id>.html [--tasks openspec/changes/<id>/tasks.md] <id> <todo|doing|blocked|done> ["note html"]

- pose data-status, data-updated (aujourd'hui), la classe/option du sélecteur, la note (si fournie)
  et data-file-updated sur <body> ;
- si --tasks est fourni, coche (done) ou décoche la case correspondante de tasks.md ;
- relit les documents sources embarqués (lecteur Markdown de la page).
À lancer après CHAQUE progression : tâche commencée (doing), terminée (done) ou bloquée (blocked).
"""
import argparse
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sourcedocs  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", required=True)
    ap.add_argument("--tasks")
    ap.add_argument("id")
    ap.add_argument("status", choices=["todo", "doing", "blocked", "done"])
    ap.add_argument("note", nargs="?")
    args = ap.parse_args()
    today = datetime.date.today().isoformat()

    src = open(args.file, encoding="utf-8").read()
    marker = f'<div class="task" data-id="{args.id}"'
    start = src.find(marker)
    if start < 0:
        sys.exit(f"Tâche {args.id} introuvable dans {args.file}")
    end = src.find('<span class="draft-flag', start)
    block = src[start:end]
    block = re.sub(r'data-status="[a-z]+"', f'data-status="{args.status}"', block, count=1)
    block = re.sub(r'data-updated="[^"]*"', f'data-updated="{today}"', block, count=1)
    block = re.sub(r'class="status-sel st-[a-z]+"', f'class="status-sel st-{args.status}"', block, count=1)
    block = block.replace(" selected>", ">")
    block = block.replace(f'<option value="{args.status}">', f'<option value="{args.status}" selected>', 1)
    if args.note is not None:
        block = re.sub(r'<em class="note">.*?</em>', lambda _m: f'<em class="note">{args.note}</em>', block, count=1, flags=re.S)
    src = src[:start] + block + src[end:]
    src = re.sub(r'data-file-updated="[^"]*"', f'data-file-updated="{today}"', src, count=1)

    if args.tasks:
        t = open(args.tasks, encoding="utf-8").read()
        mark = "x" if args.status == "done" else " "
        t2, n = re.subn(rf"^(\s*-\s+)\[[ xX]\](\s+{re.escape(args.id)}\s)", rf"\1[{mark}]\2", t, count=1, flags=re.M)
        if n:
            open(args.tasks, "w", encoding="utf-8").write(t2)
        else:
            print(f"(avertissement) {args.id} absent de {args.tasks}", file=sys.stderr)
    # Les documents embarqués (dont tasks.md) sont relus après la mise à jour de la case.
    open(args.file, "w", encoding="utf-8").write(sourcedocs.refresh(src, args.file))
    print(f"{args.id} -> {args.status}")


if __name__ == "__main__":
    main()
