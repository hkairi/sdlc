#!/usr/bin/env python3
"""Fige la dette de suivi connue à une date, pour que le plugin ne crie que sur le neuf.

Pourquoi : un dépôt peut porter des changes sans suivi ou des tâches closes sans preuve
chiffrée. Un outil qui signale ces problèmes à chaque lecture est un outil qu'on apprend à
ignorer. La baseline les **date** et les **versionne** ; `sdlc_status` (plugin) distingue
ensuite « nouveau » et « connu ».

Format de `baseline.json` (écrit à la racine de la skill `suivi-taches`, là où le plugin
`sdlc_status` / `sdlc_doctor` le lit) :

    {
      "schema": 1,
      "generated": "AAAA-MM-JJ",
      "drifts": ["<problème de check_sync.py --all, sans indentation>", ...],
      "unproven": {"<change>": ["1.1", "2.3"], ...}
    }

`generated` date la dernière photographie **complète**. Retirer une dette résorbée
(`--check-ratchet`) ne change pas cette date : sinon l'âge affiché mentirait sur la
fraîcheur de l'inventaire.

Usage (depuis la racine du projet) :
    python3 .agents/skills/suivi-taches/scripts/baseline.py --write
    python3 .agents/skills/suivi-taches/scripts/baseline.py --dry-run
    python3 .agents/skills/suivi-taches/scripts/baseline.py --check-ratchet
"""
import argparse
import datetime
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.normpath(os.path.join(HERE, ".."))
CHECK_SYNC = os.path.join(HERE, "check_sync.py")
BASELINE = os.path.join(SKILL_ROOT, "baseline.json")
DEFAULT_STATE = "docs/suivi/state.json"

# Au-delà, la baseline n'est plus une photographie datée : c'est une amnistie.
MAX_AGE_DAYS = 30


def load_check_sync():
    spec = importlib.util.spec_from_file_location("check_sync", CHECK_SYNC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def drifts_from_script():
    """Problèmes connus, tels que les rapporte le script de contrôle de synchronisation."""
    result = subprocess.run(
        [sys.executable, CHECK_SYNC, "--all", "--json"],
        capture_output=True, text=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        sys.exit(f"check_sync.py --all --json illisible :\n{result.stdout}\n{result.stderr}")
    return sorted({problem.strip() for problem in payload.get("problems", [])})


def unproven_by_change(state_path, evidence_re):
    """{change: [tâches done sans indice de preuve]}, depuis la source de vérité `state.json`.

    La clé est le `change` de la feature (ou son `id`), comme le libellé utilisé par
    le plugin (`sdlc_status`) pour rapprocher la baseline des chantiers.
    """
    out = {}
    try:
        with open(state_path, encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return out
    for feature in state.get("features", []):
        change = str(feature.get("change") or feature.get("id") or "")
        if not change:
            continue
        tasks = []
        for task in feature.get("tasks", []):
            status = task.get("status")
            note = str(task.get("note") or "")
            if status != "done" or evidence_re.search(note):
                continue
            tasks.append(str(task.get("id")))
        if tasks:
            out[change] = sorted(set(tasks))
    return dict(sorted(out.items()))


def drift_key(problem):
    """Clé stable d'une dérive : le change visé, avant le séparateur « : ».

    Comparer les textes entiers serait fragile : une reformulation du message
    par `check_sync.py` ferait croire que des dettes ont été payées alors que
    le problème existe toujours. On compare donc le change ; une dette n'est
    « résorbée » que quand plus rien ne le concerne.
    """
    head, separator, _ = str(problem).partition(" :")
    return head.strip() if separator else str(problem).strip()


def ratchet_problems(baseline, drifts, unproven):
    """Compare la dette figée à la dette réelle.

    Pure (aucune I/O) pour être testable : renvoie
    `(resolved, new)` — deux listes de libellés triés.

    `resolved` = présent dans la baseline, absent de l'état courant : la dette a
    été payée mais la baseline la liste encore, donc elle ne décroît pas.
    `new` = apparu depuis : à traiter, jamais à figer en silence.
    """
    baseline_drifts = {drift_key(item) for item in (baseline.get("drifts") or [])}
    current_drifts = {drift_key(item) for item in (drifts or [])}
    baseline_unproven = {
        str(change): {str(task) for task in tasks}
        for change, tasks in (baseline.get("unproven") or {}).items()
    }
    current_unproven = {
        str(change): {str(task) for task in tasks} for change, tasks in (unproven or {}).items()
    }

    resolved = [
        f"dérive : {item}" for item in (baseline.get("drifts") or []) if drift_key(item) not in current_drifts
    ]
    for change, tasks in sorted(baseline_unproven.items()):
        for task in sorted(tasks - current_unproven.get(change, set())):
            resolved.append(f"tâche {change}:{task}")

    new = [f"dérive : {item}" for item in (drifts or []) if drift_key(item) not in baseline_drifts]
    for change, tasks in sorted(current_unproven.items()):
        for task in sorted(tasks - baseline_unproven.get(change, set())):
            new.append(f"tâche {change}:{task}")

    return resolved, new


def check_ratchet():
    """Audit : la dette figée doit décroître, jamais rester en l'état.

    Ne bloque aucun commit (appelé en CI, non bloquant). Sortie 0 si la
    baseline est cohérente, 1 si une dette résorbée y traîne encore.
    """
    if not os.path.exists(BASELINE):
        print(f"baseline introuvable : {os.path.relpath(BASELINE)}", file=sys.stderr)
        return 2
    with open(BASELINE, encoding="utf-8") as handle:
        baseline = json.load(handle)

    check = load_check_sync()
    drifts = drifts_from_script()
    unproven = unproven_by_change(DEFAULT_STATE, check.EVIDENCE_RE)
    resolved, new = ratchet_problems(baseline, drifts, unproven)

    total = sum(len(tasks) for tasks in (baseline.get("unproven") or {}).values())
    generated = baseline.get("generated") or "?"
    age = None
    try:
        age = (datetime.date.today() - datetime.date.fromisoformat(str(generated))).days
    except ValueError:
        pass

    print(
        f"baseline — {generated} ({age if age is not None else '?'} jour(s)) · "
        f"{len(baseline.get('drifts') or [])} dérive(s) · {total} tâche(s) sans preuve"
    )
    if age is not None and age > MAX_AGE_DAYS:
        print(
            f"  ⚠ baseline vieille de {age} jours (> {MAX_AGE_DAYS}) : la refiger masquerait la dette "
            f"au lieu de la résorber"
        )
    if resolved:
        print(f"  ✖ {len(resolved)} dette(s) résorbée(s) mais toujours listée(s) — retirer ces entrées :")
        for item in resolved:
            print(f"      - {item}")
    if new:
        print(f"  ⚠ {len(new)} nouvelle(s) dette(s) depuis la baseline (à traiter, pas à figer) :")
        for item in new[:10]:
            print(f"      - {item}")
        if len(new) > 10:
            print(f"      … et {len(new) - 10} autre(s)")
    if not resolved:
        print("  ✓ la baseline ne liste aucune dette déjà payée")
    return 1 if resolved else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="écrire la baseline (racine de la skill suivi-taches)")
    parser.add_argument("--dry-run", action="store_true", help="afficher le contenu sans écrire")
    parser.add_argument(
        "--check-ratchet",
        action="store_true",
        help="échouer si une dette résorbée est encore listée dans la baseline",
    )
    args = parser.parse_args()

    if args.check_ratchet:
        return check_ratchet()
    if not args.write and not args.dry_run:
        parser.error("préciser --write, --dry-run ou --check-ratchet")

    check = load_check_sync()
    baseline = {
        "schema": 1,
        "generated": datetime.date.today().isoformat(),
        "drifts": drifts_from_script(),
        "unproven": unproven_by_change(DEFAULT_STATE, check.EVIDENCE_RE),
    }
    text = json.dumps(baseline, indent=2, ensure_ascii=False, sort_keys=False) + "\n"

    if args.dry_run:
        print(text)
        return 0

    with open(BASELINE, "w", encoding="utf-8") as handle:
        handle.write(text)
    total_unproven = sum(len(tasks) for tasks in baseline["unproven"].values())
    print(
        f"{os.path.relpath(BASELINE)} : {len(baseline['drifts'])} dérive(s), "
        f"{total_unproven} tâche(s) sans preuve sur {len(baseline['unproven'])} change(s), "
        f"daté {baseline['generated']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
