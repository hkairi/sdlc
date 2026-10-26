#!/usr/bin/env python3
"""Vérifie que `docs/suivi/state.json` et les cases de `tasks.md` sont SYNCHRONES.

La progression de `state.json` doit être le reflet exact du traitement des tâches :
une tâche `done` dans `state.json` ⇔ case cochée dans `tasks.md` ; toute autre tâche
(`todo` / `doing` / `blocked`) ⇔ case décochée. `track.py` maintient cette équivalence ;
ce script la contrôle.

Usage (une feature) :
  check_sync.py --state docs/suivi/state.json --tasks openspec/changes/<id>/tasks.md

Usage (tous les changes ouverts — le mode des gates git/CI) :
  check_sync.py --all [--require-evidence]

Usage (changes touchés par un commit ou une PR — le mode recommandé des gates) :
  check_sync.py --paths $(git diff --cached --name-only) [--no-require-evidence]

  --all               parcourt state.json et exige, pour CHAQUE change ouvert, une feature ;
                      un change sans feature est un problème (règle de la skill : un change
                      validé sans son suivi est un oubli).
  --paths             ne contrôle que les changes touchés par les chemins fournis. Un chemin
                      `docs/suivi/state.json` est un suivi global : tous les changes sont
                      contrôlés.
  --require-evidence  une tâche `done` doit porter une note contenant une PREUVE chiffrée.

Sortie : 0 si tout est synchrone ; 1 s'il y a une dérive (détail imprimé) ;
2 en cas d'erreur (state.json absent, schéma non reconnu, JSON illisible).
"""
import argparse
import json
import os
import re
import sys

TASK_MD_RE = re.compile(r"^\s*-\s+\[([ xX])\]\s+(\d+[a-z]*\.\d+[a-z]*)\s")

# Motifs acceptés comme preuve de vérification dans une note de tâche `done`.
EVIDENCE_RE = re.compile(
    r"(make test|go test|rspec|bin/rails|exit\s*=\s*0|"
    r"\d+\s*(examples?|échec|échecs|failures?|offenses?|scénarios?|critères?|tests?)|"
    r"\d+\s*/\s*\d+|vérifié|explain)",
    re.I,
)

DEFAULT_STATE = "docs/suivi/state.json"


def read_tasks_md(path):
    """{id: coché?} depuis un tasks.md OpenSpec."""
    checkboxes = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = TASK_MD_RE.match(line)
            if m:
                checkboxes[m.group(2)] = m.group(1).lower() == "x"
    return checkboxes


def load_state(state_path):
    """Lit `state.json` (schéma 1). Erreur explicite (code 2) sinon."""
    if not os.path.isfile(state_path):
        sys.exit(
            f"state.json introuvable : {state_path} — générer (generate.py) "
            f"ou migrer un ancien suivi HTML (migrate_from_html.py).",
        )
    try:
        with open(state_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError) as exc:
        sys.exit(f"state.json illisible : {exc}")
    schema = data.get("schema") if isinstance(data, dict) else None
    if schema != 1:
        sys.exit(f"schéma de state.json non reconnu : {schema} (attendu 1)")
    return data


def feature_of_change(features, change):
    """Feature qui suit `change` : par `change`, `id`, sinon par `tasks_file`."""
    for feature in features or []:
        if feature.get("change") == change or feature.get("id") == change:
            return feature
        tasks_rel = (feature.get("tasks_file") or "").replace(os.sep, "/")
        if f"/{change}/" in tasks_rel:
            return feature
    return None


def suivi_tasks(feature):
    return {t["id"]: t.get("status", "todo") for t in feature.get("tasks", [])}


def suivi_notes(feature):
    return {t["id"]: (t.get("note") or "") for t in feature.get("tasks", [])}


def expected_checked(status):
    return status == "done"


def _sort_key(task_id):
    m = re.match(r"(\d+)[a-z]*\.(\d+)", task_id)
    return (int(m.group(1)), int(m.group(2))) if m else (999, 999)


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
            problems.append(f"  {label}{task_id} : suivi={status} mais tasks.md case={'x' if checked else ' '}")


def evidence_problems(label, suivi_tasks, notes, problems):
    for task_id in sorted(suivi_tasks, key=_sort_key):
        if suivi_tasks[task_id] != "done":
            continue
        note = notes.get(task_id, "")
        if not note:
            problems.append(f"  {label}{task_id} : tâche done SANS note de suivi (aucune preuve)")
        elif not EVIDENCE_RE.search(note):
            problems.append(f"  {label}{task_id} : tâche done sans preuve chiffrée dans sa note — « {note[:90]} »")


def check_feature(feature, tasks_path, require_evidence=False):
    """Contrôle une feature de state.json contre son tasks.md."""
    suivi = suivi_tasks(feature)
    problems = []
    compare("", suivi, read_tasks_md(tasks_path), problems)
    if require_evidence:
        evidence_problems("", suivi, suivi_notes(feature), problems)
    return len(suivi), problems


def _feature_tasks_path(feature):
    rel = feature.get("tasks_file")
    if not rel:
        return None
    return rel if os.path.isabs(rel) else os.path.join(os.getcwd(), rel)


def check_all(state, changes_dir, require_evidence=False):
    """Toutes les features de state.json + les changes ouverts sans feature."""
    problems, total = [], 0
    features = state.get("features") or []
    for feature in features:
        fid = feature.get("id", "?")
        tasks_path = _feature_tasks_path(feature)
        if not tasks_path:
            problems.append(f"  {fid} : aucun tasks_file mémorisé (régénérer le suivi)")
            continue
        if not os.path.isfile(tasks_path):
            problems.append(f"  {fid} : tasks.md introuvable ({tasks_path})")
            continue
        count, fp = check_feature(feature, tasks_path, require_evidence)
        total += count
        problems.extend(f"{fid} :{p.strip()}" for p in fp)

    if os.path.isdir(changes_dir):
        for change in sorted(os.listdir(changes_dir)):
            if change == "archive" or not os.path.isdir(os.path.join(changes_dir, change)):
                continue
            tasks_path = os.path.join(changes_dir, change, "tasks.md")
            if not os.path.isfile(tasks_path):
                continue
            if feature_of_change(features, change) is None:
                problems.append(f"  {change} : tasks.md présent mais feature absente de state.json (générer : generate.py)")
    return total, problems


def changes_touched_by(paths):
    """Déduit les identifiants de changes des chemins touchés par un commit/PR."""
    changes = set()
    for path in paths:
        path = path.strip()
        if not path:
            continue
        m = re.match(r"openspec/changes/([^/]+)/", path)
        if m and m.group(1) != "archive":
            changes.add(m.group(1))
            continue
    return sorted(changes)


def check_changes(change_ids, state, changes_dir, require_evidence=True):
    problems, total = [], 0
    features = state.get("features") or []
    for change in change_ids:
        feature = feature_of_change(features, change)
        if feature is None:
            tasks_path = os.path.join(changes_dir, change, "tasks.md")
            if os.path.isfile(tasks_path):
                problems.append(f"  {change} : tasks.md modifié mais feature absente de state.json")
            continue
        tasks_path = _feature_tasks_path(feature)
        if not tasks_path or not os.path.isfile(tasks_path):
            continue
        count, fp = check_feature(feature, tasks_path, require_evidence)
        total += count
        problems.extend(f"{change} :{p.strip()}" for p in fp)
    return total, problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", default=DEFAULT_STATE, help="chemin de state.json")
    ap.add_argument("--tasks", help="tasks.md (une seule feature : celle qui référence ce tasks.md)")
    ap.add_argument("--all", action="store_true", help="toutes les features + changes ouverts")
    ap.add_argument("--paths", nargs="*", default=None, help="chemins touchés (git diff --cached --name-only)")
    ap.add_argument("--changes-dir", default="openspec/changes", help="répertoire des changes (avec --all)")
    ap.add_argument("--require-evidence", action="store_true", help="preuve chiffrée exigée pour chaque tâche done")
    ap.add_argument("--no-require-evidence", action="store_true", help="désactive l'exigence de preuve en mode --paths")
    ap.add_argument("--json", action="store_true", help="sortie JSON")
    args = ap.parse_args()

    state = load_state(args.state)

    if args.paths is not None:
        # state.json touché → suivi global : tous les changes.
        if any(os.path.basename(p.strip()) == "state.json" for p in args.paths):
            total, problems = check_all(state, args.changes_dir, args.require_evidence)
            label = "tous les changes (state.json touché)"
        else:
            change_ids = changes_touched_by(args.paths)
            if not change_ids:
                print("sync OK : aucun change touché — rien à contrôler.")
                return 0
            require_evidence = not args.no_require_evidence
            total, problems = check_changes(change_ids, state, args.changes_dir, require_evidence)
            label = ", ".join(change_ids)
    elif args.all:
        total, problems = check_all(state, args.changes_dir, args.require_evidence)
        label = f"{args.changes_dir}/*"
    elif args.tasks:
        target = os.path.realpath(args.tasks)
        feature = None
        for candidate in state.get("features") or []:
            rel = candidate.get("tasks_file") or ""
            if not rel:
                continue
            path = rel if os.path.isabs(rel) else os.path.join(os.getcwd(), rel)
            if os.path.realpath(path) == target:
                feature = candidate
                break
        if feature is None:
            sys.exit(f"{args.state} ne suit pas {args.tasks} (aucune feature ne référence ce tasks.md)")
        total, problems = check_feature(feature, args.tasks, args.require_evidence)
        label = args.tasks
    else:
        sys.exit("préciser --tasks (une feature), --all, ou --paths")

    if args.json:
        print(json.dumps({"file": label, "tasks": total, "problems": problems}, ensure_ascii=False, indent=2))
    elif problems:
        print(f"DÉSYNCHRONISATION state.json ↔ tasks.md ({len(problems)} problème(s)) :")
        print("\n".join(problems))
    else:
        print(f"sync OK : {total} tâche(s) — state.json ↔ tasks.md cohérents.")

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
