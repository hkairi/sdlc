#!/usr/bin/env python3
"""Contrôle le contrat de handoff entre agents (`.opencode/handoff/README.md`).

Un change « opt-in » est un change qui possède `openspec/changes/<id>/handoff/`.
Les autres ne sont pas contrôlés : le mécanisme s'active change par change,
sans bloquer la dette historique.

Ce qui est vérifié :

  R2  aucune étape ne suit un artefact qui n'est pas `ready` (sauf reprise
      après `rejected`/`blocked`, qui doit rester sur la même étape) ;
  R3  `ready` exige au moins une preuve exécutée (cmd + résultat chiffré) ;
      pour `impl`/`test`, la cmd doit correspondre au champ `Tests :` d'une des
      tâches couvertes ;
  R4  `rejected` exige au moins un finding ;
  R5  toute tâche cochée dans `tasks.md` doit être couverte par un artefact
      `ready` (une tâche « cadrage » ne peut être couverte que par `spec`) ;
  R6  `review` est en lecture seule et n'annonce aucun fichier modifié ;
  +   cohérence du nom de fichier, de l'étape, de l'agent émetteur, et
      existence des tâches citées.

Sortie : 0 si tout est cohérent, 1 si au moins un problème, 2 en cas d'erreur
d'usage ou de fichier illisible (même convention que `check_sync.py`).
Aucune écriture : ce script est en lecture seule.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import tomllib

STAGES = ["spec", "impl", "test", "review", "learn", "close"]
STAGE_INDEX = {name: index for index, name in enumerate(STAGES)}
FILE_STAGE = {"10": "spec", "20": "impl", "30": "test", "40": "review", "45": "learn", "50": "close"}
AGENT_FOR_STAGE = {
    "spec": "spec",
    "impl": "impl",
    "test": "test",
    "review": "review",
    "learn": "learn",
    "close": "docs",
}
ALLOWED_TO = set(STAGES) | {"docs", "user"}
STATUSES = {"ready", "blocked", "rejected"}

# Un résultat de preuve doit être observable : un chiffre, ou un verdict
# explicite (« valid », « passed », « OK », « ✓ »). Une affirmation nue ne passe pas.
PROOF_RESULT_RE = re.compile(r"\d|✓|\b(valid|passed|ok|vert|green|réussi)\b", re.I)

REQUIRED = [    "change",
    "stage",
    "revision",
    "from",
    "to",
    "status",
    "created",
    "tasks",
    "files",
    "evidence",
]

HANDOFF_NAME_RE = re.compile(r"^(\d{2})-([a-z]+)(?:-r(\d+))?\.md$")
TASK_LINE_RE = re.compile(r"^\s*-\s+\[([ xX])\]\s+(\d+[a-z]*\.\d+[a-z]*)\s+(.+)$")
TESTS_LINE_RE = re.compile(r"^\s*-\s+Tests\s*:\s*(.+)$")
SECTION_RE = re.compile(r"^##\s+(.+)$")


def normalize(command: str) -> str:
    """Comparaison tolérante : espaces, backticks, ponctuation finale."""
    value = command.strip().strip("`").strip()
    value = re.sub(r"\s+", " ", value)
    return value.rstrip(" .;,")


def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_tasks(tasks_path: str) -> dict[str, dict]:
    """{id: {checked, title, section, tests[]}} depuis un tasks.md OpenSpec."""
    tasks: dict[str, dict] = {}
    current = None
    section = ""
    with open(tasks_path, encoding="utf-8") as handle:
        for line in handle:
            section_match = SECTION_RE.match(line)
            if section_match:
                section = section_match.group(1).strip()
                continue
            task_match = TASK_LINE_RE.match(line)
            if task_match:
                current = task_match.group(2)
                tasks[current] = {
                    "checked": task_match.group(1).lower() == "x",
                    "title": task_match.group(3).strip(),
                    "section": section,
                    "tests": [],
                }
                continue
            if current is None:
                continue
            tests_match = TESTS_LINE_RE.match(line)
            if tests_match:
                tasks[current]["tests"].append(normalize(tests_match.group(1)))
    return tasks


def parse_handoff(path: str) -> tuple[dict, str]:
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    if not text.startswith("+++"):
        raise ValueError("frontmatter TOML absent : le fichier doit commencer par +++")
    end = text.find("\n+++", 3)
    if end == -1:
        raise ValueError("frontmatter TOML non fermé (+++ manquant en fin d'en-tête)")
    meta = tomllib.loads(text[3:end])
    return meta, text[end + 4 :]


def evidence_matches(evidence_command: str, tests_line: str) -> bool:
    left, right = normalize(evidence_command), normalize(tests_line)
    return bool(left) and bool(right) and (left.startswith(right) or right.startswith(left))


def learning_ids(root: str) -> set[str]:
    """Identifiants du registre d'apprentissages (voir scripts/learnings.py)."""
    ids: set[str] = set()
    directory = os.path.join(root, "openspec", "learnings")
    if not os.path.isdir(directory):
        return ids
    for path in glob.glob(os.path.join(directory, "L-*.md")):
        match = re.match(r"^(L-\d{4})-", os.path.basename(path))
        if match:
            ids.add(match.group(1))
    return ids


def check_file(path: str, tasks: dict[str, dict], root: str) -> tuple[list[str], list[str], dict]:
    """Problèmes, avertissements et métadonnées utiles d'un artefact."""
    problems: list[str] = []
    warnings: list[str] = []
    label = os.path.basename(path)

    match = HANDOFF_NAME_RE.match(label)
    if not match:
        return [f"{label} : nom invalide (attendu NN-<stage>[-rN].md)"], warnings, {}

    prefix, file_stage, revision_in_name = match.group(1), match.group(2), match.group(3)
    if FILE_STAGE.get(prefix) != file_stage:
        problems.append(f"{label} : le préfixe {prefix} ne correspond pas à l'étape « {file_stage} »")

    try:
        meta, body = parse_handoff(path)
    except (ValueError, tomllib.TOMLDecodeError) as error:
        return [f"{label} : {error}"], warnings, {}

    missing = [field for field in REQUIRED if field not in meta]
    if missing:
        return [f"{label} : champs obligatoires absents — {', '.join(missing)}"], warnings, meta

    stage = meta.get("stage")
    status = meta.get("status")
    if stage not in STAGE_INDEX:
        problems.append(f"{label} : étape inconnue « {stage} »")
    if status not in STATUSES:
        problems.append(f"{label} : statut inconnu « {status} »")
    if meta.get("from") != AGENT_FOR_STAGE.get(str(stage)):
        problems.append(
            f"{label} : émetteur « {meta.get('from')} » incohérent (attendu « {AGENT_FOR_STAGE.get(str(stage))} »)"
        )
    if meta.get("to") not in ALLOWED_TO:
        problems.append(f"{label} : destinataire inconnu « {meta.get('to')} »")
    if not isinstance(meta.get("revision"), int) or meta["revision"] < 1:
        problems.append(f"{label} : « revision » doit être un entier ≥ 1")
    elif revision_in_name is not None and int(revision_in_name) != meta["revision"]:
        problems.append(
            f"{label} : suffixe -r{revision_in_name} mais revision = {meta['revision']}"
        )
    if meta.get("change") != os.path.basename(os.path.dirname(os.path.dirname(path))):
        problems.append(f"{label} : « change » ne correspond pas au dossier du change")

    for task_id in meta.get("tasks") or []:
        if task_id not in tasks:
            problems.append(f"{label} : tâche « {task_id} » absente de tasks.md")
    if not meta.get("tasks") and stage != "close":
        warnings.append(f"{label} : aucune tâche couverte")

    known_learnings = learning_ids(root)
    for reference in (meta.get("learnings") or []) + (meta.get("retired") or []):
        if reference not in known_learnings:
            problems.append(f"{label} : apprentissage « {reference} » introuvable dans openspec/learnings/")

    if stage == "review" and meta.get("files"):
        problems.append(f"{label} : review est en lecture seule, « files » doit être vide")
    for touched in meta.get("files") or []:
        if not os.path.exists(os.path.join(root, touched)):
            warnings.append(f"{label} : fichier annoncé introuvable — {touched}")
        if stage == "impl" and (
            touched.endswith("tasks.md") or touched.startswith("docs/suivi-")
        ):
            problems.append(f"{label} : impl ne peut pas modifier {touched} (réservé aux outils sdlc)")

    evidence = meta.get("evidence") or []
    if status == "ready" and not evidence:
        problems.append(f"{label} : status « ready » sans aucune preuve exécutée")
    if status == "rejected" and not meta.get("findings"):
        problems.append(f"{label} : status « rejected » sans findings")
    for index, entry in enumerate(evidence, start=1):
        if not isinstance(entry, dict) or not entry.get("cmd") or not entry.get("result"):
            problems.append(f"{label} : evidence #{index} incomplète (cmd et result obligatoires)")
            continue
        if not PROOF_RESULT_RE.search(str(entry["result"])):
            problems.append(f"{label} : evidence #{index} sans résultat observable — « {entry['result']} »")
        if stage in ("impl", "test"):
            covered_tests = [
                line
                for task_id in meta.get("tasks") or []
                for line in tasks.get(task_id, {}).get("tests", [])
            ]
            if not any(evidence_matches(entry["cmd"], line) for line in covered_tests):
                problems.append(
                    f"{label} : evidence « {entry['cmd']} » ne correspond à aucun champ Tests : "
                    "des tâches couvertes"
                )
    if not body.strip():
        warnings.append(f"{label} : corps Markdown vide (décisions non consignées)")

    return problems, warnings, meta


def check_change(change_dir: str, require: bool, root: str) -> dict:
    change = os.path.basename(change_dir)
    handoff_dir = os.path.join(change_dir, "handoff")
    result = {
        "change": change,
        "enabled": os.path.isdir(handoff_dir),
        "artifacts": 0,
        "problems": [],
        "warnings": [],
        "covered": 0,
        "tasks": 0,
    }
    if not result["enabled"]:
        if require:
            result["problems"].append(f"{change} : aucun dossier handoff/ (mécanisme non configuré)")
        return result

    files = sorted(glob.glob(os.path.join(handoff_dir, "*.md")))
    files = [path for path in files if not os.path.basename(path).upper().startswith("README")]
    if not files:
        result["problems"].append(f"{change} : handoff/ présent mais vide")
        return result

    tasks_path = os.path.join(change_dir, "tasks.md")
    tasks = read_tasks(tasks_path) if os.path.exists(tasks_path) else {}
    result["tasks"] = len(tasks)

    ordered = []
    for path in files:
        problems, warnings, meta = check_file(path, tasks, root)
        result["problems"].extend(problems)
        result["warnings"].extend(warnings)
        result["artifacts"] += 1
        if meta:
            ordered.append((path, meta))

    labeled = sorted(
        ordered,
        key=lambda item: (
            STAGE_INDEX.get(str(item[1].get("stage")), 99),
            item[1].get("revision") if isinstance(item[1].get("revision"), int) else 0,
        ),
    )

    previous = None
    for path, meta in labeled:
        label = os.path.basename(path)
        if previous is not None:
            previous_path, previous_meta = previous
            previous_label = os.path.basename(previous_path)
            previous_status = previous_meta.get("status")
            if previous_status == "ready" and meta.get("from") != previous_meta.get("to"):
                result["problems"].append(
                    f"{change} : {label} émet « {meta.get('from')} » alors que {previous_label} "
                    f"annonçait « {previous_meta.get('to')} » (R2)"
                )
            if previous_status in ("rejected", "blocked") and meta.get("stage") != previous_meta.get("stage"):
                result["problems"].append(
                    f"{change} : {previous_label} est « {previous_status} » mais {label} passe à "
                    f"l'étape « {meta.get('stage')} » au lieu de reprendre « {previous_meta.get('stage')} » (R2)"
                )
        previous = (path, meta)

    covered: set[str] = set()
    for _, meta in labeled:
        if meta.get("status") != "ready":
            continue
        for task_id in meta.get("tasks") or []:
            task = tasks.get(task_id)
            if not task:
                continue
            if meta.get("stage") == "spec" and "cadrage" not in task["section"].lower():
                continue
            covered.add(task_id)
    result["covered"] = len(covered)

    for task_id, task in tasks.items():
        if task["checked"] and task_id not in covered:
            result["problems"].append(
                f"{change} : tâche {task_id} cochée dans tasks.md mais couverte par aucun artefact "
                "« ready » du handoff (R5)"
            )

    return result


def changes_from_paths(paths: list[str]) -> list[str]:
    found: list[str] = []
    for path in paths:
        normalized = path.replace(os.sep, "/")
        if normalized.startswith("openspec/changes/archive/"):
            continue
        if normalized.startswith("openspec/changes/"):
            parts = normalized.split("/")
            if len(parts) >= 3 and parts[2]:
                found.append(parts[2])
            continue
        match = re.match(r"docs/suivi-(.+)\.html$", normalized)
        if match:
            found.append(match.group(1))
    return sorted(set(found))


def main() -> int:
    parser = argparse.ArgumentParser(description="Contrôle le contrat de handoff entre agents.")
    parser.add_argument("--change", action="append", default=[], help="identifiant de change (répétable)")
    parser.add_argument("--paths", nargs="*", default=None, help="chemins touchés (mappe vers les changes)")
    parser.add_argument("--all", action="store_true", help="tous les changes ouverts")
    parser.add_argument("--require", action="store_true", help="échouer si un change n'a pas de handoff/")
    parser.add_argument("--json", action="store_true", help="sortie JSON")
    parser.add_argument("--root", default=None, help="racine du dépôt (défaut : celle du script)")
    args = parser.parse_args()

    root = os.path.abspath(args.root) if args.root else repo_root()
    changes_dir = os.path.join(root, "openspec", "changes")
    if not os.path.isdir(changes_dir):
        print(f"handoff_check : aucun dossier {changes_dir}", file=sys.stderr)
        return 2
    selected = list(args.change)
    if args.paths is not None:
        selected.extend(changes_from_paths(args.paths))
    if args.all or (not selected and args.paths is None):
        selected = sorted(
            name
            for name in os.listdir(changes_dir)
            if os.path.isdir(os.path.join(changes_dir, name)) and name != "archive"
        )
    selected = sorted(set(selected))

    results = []
    for change in selected:
        change_dir = os.path.join(changes_dir, change)
        if not os.path.isdir(change_dir):
            results.append(
                {
                    "change": change,
                    "enabled": False,
                    "artifacts": 0,
                    "problems": [f"{change} : change introuvable"],
                    "warnings": [],
                    "covered": 0,
                    "tasks": 0,
                }
            )
            continue
        results.append(check_change(change_dir, args.require, root))

    active = [item for item in results if item["enabled"]]
    problem_count = sum(len(item["problems"]) for item in results)

    if args.json:
        print(json.dumps({"results": results, "problems": problem_count}, ensure_ascii=False, indent=2))
    else:
        print(f"handoff_check — {len(results)} change(s), {len(active)} avec handoff")
        for item in results:
            if not item["enabled"]:
                continue
            status = "✖" if item["problems"] else "✓"
            print(
                f"{status} {item['change']} : {item['artifacts']} artefact(s), "
                f"{item['covered']}/{item['tasks']} tâche(s) couverte(s)"
            )
            for problem in item["problems"]:
                print(f"    ✖ {problem}")
            for warning in item["warnings"]:
                print(f"    ⚠ {warning}")
        if not active:
            print("aucun change configuré pour le handoff (mécanisme opt-in)")

    return 1 if problem_count else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except FileNotFoundError as error:
        print(f"handoff_check : fichier introuvable — {error}", file=sys.stderr)
        sys.exit(2)
