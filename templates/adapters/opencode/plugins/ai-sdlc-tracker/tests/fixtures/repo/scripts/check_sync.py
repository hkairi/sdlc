#!/usr/bin/env python3
"""Vérifie que le suivi HTML et les cases de tasks.md sont SYNCHRONES.

COPIE VENDORÉE dans le dépôt (scripts/check_sync.py) pour que le hook git
(.githooks/pre-commit) et la CI (.github/workflows/openspec-tracking.yml)
utilisent EXACTEMENT le même contrôle, sans dépendre d'un chemin utilisateur.
L'original vit dans la skill `suivi-taches` (~/.config/opencode/skills/...) ;
quand l'un évolue, recopier l'autre.


La progression du fichier de suivi doit être le reflet exact du traitement des
tâches : une tâche `done` dans le suivi ⇔ case cochée dans `tasks.md` ; toute
autre tâche (`todo` / `doing` / `blocked`) ⇔ case décochée. `track.py` (mono) et
`track_multi.py` (multi) maintiennent cette équivalence ; ce script la contrôle.

Usage (mono) :
  check_sync.py --file docs/suivi-<id>.html --tasks openspec/changes/<id>/tasks.md

Usage (multi) :
  check_sync.py --file docs/suivi-multi.html          # lit le bloc feature-data

Usage (tous les changes ouverts — le mode utilisé par les gates git/CI) :
  check_sync.py --all [--require-evidence]

Usage (changes touchés par un commit ou une PR — le mode recommandé des gates) :
  check_sync.py --paths $(git diff --cached --name-only) [--no-require-evidence]

  --all               parcourt openspec/changes/*/ (hors archive) et exige, pour
                      CHAQUE change, son suivi docs/suivi-<id>.html ; un change
                      sans suivi est un problème (règle de la skill : un change
                      validé sans son suivi est un oubli).
  --paths             ne contrôle que les changes touchés par les chemins fournis
                      (fichiers de tasks.md, deltas, suivi HTML). C'est le mode
                      des gates : il ne punit pas la dette historique des changes
                      que le commit ne touche pas, et il exige des preuves pour
                      les tâches `done` des changes qu'il juge.
  --require-evidence  une tâche `done` doit porter une note de suivi contenant
                      une PREUVE chiffrée (N examples / 0 échec / make test /
                      exit=0 / vérifié) : un « done » affirmé sans preuve échoue.

Sortie : 0 si tout est synchrone ; 1 s'il y a une dérive (détail imprimé) ;
2 en cas d'erreur (fichier manquant, tâche absente d'un côté…).
"""
import argparse
import glob
import json
import os
import re
import sys

TASK_MD_RE = re.compile(r"^\s*-\s+\[([ xX])\]\s+(\d+[a-z]*\.\d+[a-z]*)\s")
TASK_HTML_RE = re.compile(r'<div class="task" data-id="([^"]+)"[^>]*data-status="([a-z]+)"')
FEATURE_DATA_RE = re.compile(r'<script type="application/json" id="feature-data">(\{.*?)</script>', re.S)
NOTE_RE = re.compile(r'<em class="note">(.*?)</em>', re.S)

# Motifs acceptés comme preuve de vérification dans une note de tâche `done`.
# Volontairement larges sur la forme, stricts sur le fond : une note sans aucun
# chiffre ni commande vérifiable ne prouve rien.
EVIDENCE_RE = re.compile(
    r"(make test|go test|rspec|bin/rails|exit\s*=\s*0|"
    r"\d+\s*(examples?|échec|échecs|failures?|offenses?|scénarios?|critères?|tests?)|"
    r"\d+\s*/\s*\d+|vérifié|explain)",
    re.I,
)


def read_tasks_md(path):
    """{id: coché?} depuis un tasks.md OpenSpec."""
    checkboxes = {}
    for line in open(path, encoding="utf-8"):
        m = TASK_MD_RE.match(line)
        if m:
            checkboxes[m.group(2)] = m.group(1).lower() == "x"
    return checkboxes


def read_suivi_tasks(path):
    """{id: statut} depuis le gabarit un chantier."""
    source = open(path, encoding="utf-8").read()
    return {task_id: status for task_id, status in TASK_HTML_RE.findall(source)}


def expected_checked(status):
    return status == "done"


def compare(label, suivi_tasks, tasks_md, problems):
    for task_id in sorted(set(suivi_tasks) | set(tasks_md), key=_sort_key):
        status = suivi_tasks.get(task_id)
        checked = tasks_md.get(task_id)
        if status is None:
            problems.append(f"  {label}{task_id} : présent dans tasks.md (case={'x' if checked else ' '}) mais absent du suivi")
            continue
        if checked is None:
            problems.append(f"  {label}{task_id} : présent dans le suivi (statut={status}) mais absent de tasks.md")
            continue
        if expected_checked(status) != checked:
            problems.append(
                f"  {label}{task_id} : suivi={status} mais tasks.md case={'x' if checked else ' '}"
            )


def _sort_key(task_id):
    m = re.match(r"(\d+)[a-z]*\.(\d+)", task_id)
    return (int(m.group(1)), int(m.group(2))) if m else (999, 999)


def read_suivi_task_notes(path):
    """{id: note texte} depuis un suivi un chantier.

    Chaque note est extraite DANS le bloc de sa tâche (découpage sur les
    `data-id` suivants), pour qu'une note ne soit jamais attribuée au mauvais
    identifiant.
    """
    source = open(path, encoding="utf-8").read()
    notes = {}
    for match in re.finditer(r'<div class="task" data-id="([^"]+)"', source):
        task_id = match.group(1)
        end = source.find('<div class="task" data-id="', match.end())
        block = source[match.start():end if end != -1 else len(source)]
        note = NOTE_RE.search(block)
        if note:
            notes[task_id] = re.sub(r"<[^>]+>", " ", note.group(1)).strip()
    return notes


def evidence_problems(label, suivi_tasks, notes, problems):
    """Ajoute un problème par tâche `done` dont la note ne prouve rien."""
    for task_id in sorted(suivi_tasks, key=_sort_key):
        if suivi_tasks[task_id] != "done":
            continue
        note = notes.get(task_id, "")
        if not note:
            problems.append(f"  {label}{task_id} : tâche done SANS note de suivi (aucune preuve)")
        elif not EVIDENCE_RE.search(note):
            problems.append(
                f"  {label}{task_id} : tâche done sans preuve chiffrée dans sa note — « {note[:90]} »"
            )


def check_mono(suivi_path, tasks_path, require_evidence=False):
    suivi_tasks = read_suivi_tasks(suivi_path)
    tasks_md = read_tasks_md(tasks_path)
    problems = []
    compare("", suivi_tasks, tasks_md, problems)
    if require_evidence:
        evidence_problems("", suivi_tasks, read_suivi_task_notes(suivi_path), problems)
    return len(suivi_tasks), problems


def check_multi(suivi_path, require_evidence=False):
    source = open(suivi_path, encoding="utf-8").read()
    m = FEATURE_DATA_RE.search(source)
    if not m:
        raise SystemExit(f"{suivi_path} ne contient ni bloc feature-data (multi) : préciser --tasks.")
    data = json.loads(m.group(1))
    problems, total = [], 0
    base = os.getcwd()
    for feature in data.get("features", []):
        suivi_tasks = {t["id"]: t.get("status", "todo") for t in feature.get("tasks", [])}
        total += len(suivi_tasks)
        tasks_rel = feature.get("tasks_file")
        if not tasks_rel:
            problems.append(f"  {feature.get('id')} : aucun tasks_file mémorisé (régénérer le suivi)")
            continue
        tasks_path = tasks_rel if os.path.isabs(tasks_rel) else os.path.join(base, tasks_rel)
        if not os.path.isfile(tasks_path):
            problems.append(f"  {feature.get('id')} : tasks.md introuvable ({tasks_rel})")
            continue
        compare(f"{feature.get('id')}:", suivi_tasks, read_tasks_md(tasks_path), problems)
        if require_evidence:
            notes = {t["id"]: (t.get("note") or "") for t in feature.get("tasks", [])}
            evidence_problems(f"{feature.get('id')}:", suivi_tasks, notes, problems)
    return total, problems


def check_all(changes_dir, docs_dir, require_evidence=False):
    """Parcourt tous les changes ouverts et exige le suivi correspondant.

    C'est le mode des gates (pre-commit, CI) : un change validé sans
    docs/suivi-<id>.html est traité comme un oubli, et une dérive de n'importe
    quel change fait échouer le contrôle.
    """
    problems, total = [], 0
    changes = sorted(
        name
        for name in os.listdir(changes_dir)
        if os.path.isdir(os.path.join(changes_dir, name)) and name != "archive"
    )
    if not changes:
        return 0, problems

    for change in changes:
        tasks_path = os.path.join(changes_dir, change, "tasks.md")
        if not os.path.isfile(tasks_path):
            continue
        suivi_path = os.path.join(docs_dir, f"suivi-{change}.html")
        if not os.path.isfile(suivi_path):
            problems.append(
                f"  {change} : tasks.md présent mais docs/suivi-{change}.html manquant "
                f"(générer le suivi : generate_from_openspec.py {change})"
            )
            continue
        count, change_problems = check_mono(suivi_path, tasks_path, require_evidence)
        total += count
        problems.extend(f"{change} :{p.strip()}" for p in change_problems)

    return total, problems


def changes_touched_by(paths):
    """Déduit les identifiants de changes des chemins touchés par un commit/PR.

    Reconnaît `openspec/changes/<id>/…` et `docs/suivi-<id>.html` ; ignore tout
    le reste (un commit de code applicatif ne déclenche aucun contrôle).
    """
    changes = set()
    for path in paths:
        path = path.strip()
        if not path:
            continue
        m = re.match(r"openspec/changes/([^/]+)/", path)
        if m and m.group(1) != "archive":
            changes.add(m.group(1))
            continue
        m = re.match(r"docs/suivi-(.+)\.html$", path)
        if m:
            changes.add(m.group(1))
    return sorted(changes)


def check_changes(change_ids, changes_dir, docs_dir, require_evidence=True):
    """Contrôle les changes nommés (mode --paths des gates)."""
    problems, total = [], 0
    for change in change_ids:
        tasks_path = os.path.join(changes_dir, change, "tasks.md")
        if not os.path.isfile(tasks_path):
            # Un change sans tasks.md n'a rien à synchroniser (spec seule).
            continue
        suivi_path = os.path.join(docs_dir, f"suivi-{change}.html")
        if not os.path.isfile(suivi_path):
            problems.append(
                f"  {change} : tasks.md modifié mais docs/suivi-{change}.html manquant "
                f"(générer le suivi : generate_from_openspec.py {change})"
            )
            continue
        count, change_problems = check_mono(suivi_path, tasks_path, require_evidence)
        total += count
        problems.extend(f"{change} :{p.strip()}" for p in change_problems)

    return total, problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", help="fichier de suivi HTML")
    ap.add_argument("--tasks", help="tasks.md (mono ; déduit du feature-data en multi)")
    ap.add_argument("--all", action="store_true", help="parcourt tous les changes ouverts (openspec/changes/*)")
    ap.add_argument(
        "--paths",
        nargs="*",
        default=None,
        help="chemins touchés (ex. git diff --cached --name-only) : ne contrôle que leurs changes",
    )
    ap.add_argument("--changes-dir", default="openspec/changes", help="répertoire des changes (avec --all)")
    ap.add_argument("--docs-dir", default="docs", help="répertoire des suivis (avec --all)")
    ap.add_argument(
        "--require-evidence",
        action="store_true",
        help="une tâche done doit porter une note contenant une preuve chiffrée",
    )
    ap.add_argument(
        "--no-require-evidence",
        action="store_true",
        help="désactive l'exigence de preuve en mode --paths (défaut : exigée)",
    )
    ap.add_argument("--json", action="store_true", help="sortie JSON")
    args = ap.parse_args()

    if args.paths is not None:
        change_ids = changes_touched_by(args.paths)
        if not change_ids:
            print("sync OK : aucun change touché — rien à contrôler.")
            return 0
        require_evidence = not args.no_require_evidence
        total, problems = check_changes(change_ids, args.changes_dir, args.docs_dir, require_evidence)
        label = ", ".join(change_ids)
    elif args.all:
        if not os.path.isdir(args.changes_dir):
            sys.exit(f"répertoire des changes introuvable : {args.changes_dir}")
        total, problems = check_all(args.changes_dir, args.docs_dir, args.require_evidence)
        label = f"{args.changes_dir}/*"
    else:
        if not args.file:
            sys.exit("préciser --file (ou --all pour tous les changes ouverts)")
        if not os.path.isfile(args.file):
            sys.exit(f"fichier de suivi introuvable : {args.file}")

        source = open(args.file, encoding="utf-8").read()
        is_multi = bool(FEATURE_DATA_RE.search(source)) and not args.tasks

        if args.tasks:
            if not os.path.isfile(args.tasks):
                sys.exit(f"tasks.md introuvable : {args.tasks}")
            total, problems = check_mono(args.file, args.tasks, args.require_evidence)
        elif is_multi:
            total, problems = check_multi(args.file, args.require_evidence)
        else:
            sys.exit("mode indéterminé : passer --tasks (mono) ou un fichier multi (feature-data).")
        label = args.file

    if args.json:
        print(json.dumps({"file": label, "tasks": total, "problems": problems}, ensure_ascii=False, indent=2))
    elif problems:
        print(f"DÉSYNCHRONISATION suivi ↔ tasks.md ({len(problems)} problème(s)) :")
        print("\n".join(problems))
    else:
        print(f"sync OK : {total} tâche(s) — suivi ↔ tasks.md cohérents.")

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
