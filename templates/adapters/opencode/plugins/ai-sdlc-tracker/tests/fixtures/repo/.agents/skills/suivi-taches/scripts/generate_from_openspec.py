#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# Copie vendorisée — source : skill suivi-taches (/Users/hkairi/.claude/skills/suivi-taches/scripts/generate_from_openspec.py)
# Copiée le 2026-10-19. Ne pas éditer ici : éditer la source, puis re-générer la copie
# avec `python3 scripts/suivi/sync_from_skill.py --write`.
# Contrôle de dérive : `python3 scripts/suivi/sync_from_skill.py --check`.
# ---------------------------------------------------------------------------
"""Génère (toujours) le fichier de suivi dès qu'une proposition OpenSpec est validée.

Une seule commande, idempotente et sans perte :

    python3 ~/.claude/skills/suivi-taches/scripts/generate_from_openspec.py [<change-id>]

Étapes :
  1. résout le change (argument, sinon l'unique change en cours de `openspec list`) ;
  2. exécute `openspec validate <id> --strict` — si la validation échoue, RIEN n'est généré ;
  3. génère (ou régénère sans perte) `docs/suivi-<id>.html` via `generate.py`, en déduisant
     titre, sous-titre, sources et objectif de `proposal.md` / `design.md` / `tasks.md` ;
  4. ajoute la ligne manquante du suivi dans `docs/README.md`.

Prérequis : `openspec/changes/<id>/tasks.md` doit exister (le suivi se lit depuis `tasks.md`).
Si `tasks.md` porte des tâches dépourvues de « Technique » ou « Acceptation », la génération
retombe sur un mode non strict (le fichier est quand même produit) et le signale ; on
régénère ensuite avec les détails une fois `tasks.md` complété.

Options : --repo, --out, --title, --h1, --eyebrow, --objective, --badge, --decisions,
--no-readme, --no-strict-details.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys


def _load_generate():
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location("suivi_generate", os.path.join(here, "generate.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def resolve_change(repo, explicit):
    if explicit:
        return explicit
    proc = run(["openspec", "list", "--json"], repo)
    if proc.returncode != 0:
        raise SystemExit(f"openspec list --json a échoué :\n{proc.stderr.strip()}")
    changes = json.loads(proc.stdout or "{}").get("changes", [])
    in_progress = [c["name"] for c in changes if c.get("status") != "complete"]
    if len(in_progress) == 1:
        return in_progress[0]
    if not in_progress:
        raise SystemExit("Aucun change OpenSpec en cours : préciser <change-id>.")
    listing = "\n".join(f"  - {name}" for name in in_progress)
    raise SystemExit(
        f"Plusieurs changes en cours : préciser <change-id>.\n{listing}"
    )


def change_title(proposal_path, fallback):
    if not os.path.isfile(proposal_path):
        return fallback
    for line in open(proposal_path, encoding="utf-8"):
        m = re.match(r"^#\s+Change\s*:\s*(.*\S)\s*$", line, re.IGNORECASE)
        if m:
            return m.group(1)
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def proposal_objective(proposal_path):
    """Premier paragraphe (non vide, hors titre) de la section « Why » / « ## Why »."""
    if not os.path.isfile(proposal_path):
        return None
    lines = open(proposal_path, encoding="utf-8").read().splitlines()
    collecting, buffer = False, []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^#+\s*Why\b", stripped, re.IGNORECASE):
            collecting = True
            continue
        if collecting:
            if stripped.startswith("#"):
                break
            if not stripped:
                if buffer:
                    break
                continue
            buffer.append(stripped)
    text = " ".join(buffer).strip()
    return text or None


def rel_link(from_dir, target_abs):
    return os.path.relpath(target_abs, from_dir)


def update_readme(repo, change_id, tasks_count, lots_count):
    readme = os.path.join(repo, "docs", "README.md")
    if not os.path.isfile(readme):
        return False
    text = open(readme, encoding="utf-8").read()
    marker = f"`suivi-{change_id}.html`"
    if marker in text:
        return False
    entry = (
        f"- {marker} : Fichier de suivi du change OpenSpec `{change_id}` "
        f"({tasks_count} tâches, {lots_count} lots) — état de référence inscrit dans le fichier, "
        "mis à jour après chaque progression (`suivi-taches`)."
    )
    lines = text.splitlines(keepends=True)
    insert_at = None
    for index, line in enumerate(lines):
        if re.match(r"^- `suivi-[^`]+\.html`", line):
            insert_at = index + 1
    if insert_at is None:
        for index, line in enumerate(lines):
            if line.startswith("##") and "Rapports" in line:
                insert_at = index + 1
    if insert_at is None:
        insert_at = len(lines)
    lines.insert(insert_at, entry + "\n")
    open(readme, "w", encoding="utf-8").write("".join(lines))
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("change", nargs="?", help="change-id OpenSpec (sinon déduit si un seul en cours)")
    parser.add_argument("--repo", default=".", help="racine du dépôt (défaut : répertoire courant)")
    parser.add_argument("--out", help="chemin du suivi (défaut : docs/suivi-<id>.html)")
    parser.add_argument("--title")
    parser.add_argument("--h1")
    parser.add_argument("--eyebrow", default="Sahelium · Suivi d'avancement")
    parser.add_argument("--subtitle")
    parser.add_argument("--objective")
    parser.add_argument("--badge")
    parser.add_argument("--decisions")
    parser.add_argument("--no-readme", action="store_true", help="ne pas mettre à jour docs/README.md")
    parser.add_argument("--no-strict-details", action="store_true", help="forcer le mode non strict")
    args = parser.parse_args()

    repo = os.path.abspath(args.repo)
    if not os.path.isdir(os.path.join(repo, "openspec", "changes")):
        raise SystemExit(f"{repo} ne ressemble pas à un dépôt OpenSpec (openspec/changes absent).")

    change_id = resolve_change(repo, args.change)
    change_dir = os.path.join(repo, "openspec", "changes", change_id)
    if not os.path.isdir(change_dir):
        raise SystemExit(f"change introuvable : {change_id}")

    # 1. Validation OpenSpec (porte d'entrée : pas de validation, pas de génération).
    validation = run(["openspec", "validate", change_id, "--strict"], repo)
    if validation.returncode != 0:
        sys.stderr.write(
            f"openspec validate {change_id} --strict a échoué — suivi NON généré.\n"
            f"{validation.stdout.strip()}\n{validation.stderr.strip()}\n"
        )
        return 1

    tasks_abs = os.path.join(change_dir, "tasks.md")
    if not os.path.isfile(tasks_abs):
        sys.stderr.write(
            f"openspec/changes/{change_id}/tasks.md est absent : écrire le découpage "
            "(lots + tâches) avant de générer le suivi.\n"
        )
        return 2

    generate = _load_generate()
    lots = generate.parse_tasks(tasks_abs)
    tasks_count = sum(len(lot["tasks"]) for lot in lots)
    lots_count = len(lots)

    out_abs = os.path.abspath(os.path.join(repo, args.out)) if args.out else os.path.join(repo, "docs", f"suivi-{change_id}.html")
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)
    out_dir = os.path.dirname(out_abs)

    script = change_title(os.path.join(change_dir, "proposal.md"), change_id)
    title = args.title or f"Suivi d'avancement — {script} · Sahelium"
    h1 = args.h1 or f"{script} — fichier de suivi"
    subtitle = args.subtitle or f"Change OpenSpec <code>{change_id}</code> · {tasks_count} tâches · {lots_count} lots"
    objective = args.objective or proposal_objective(os.path.join(change_dir, "proposal.md"))

    cmd = [
        sys.executable,
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate.py"),
        "--tasks", os.path.relpath(tasks_abs, repo),
        "--out", os.path.relpath(out_abs, repo),
        "--title", title,
        "--h1", h1,
        "--eyebrow", args.eyebrow,
        "--subtitle", subtitle,
    ]
    for label, filename in (("proposal", "proposal.md"), ("design", "design.md"), ("tasks", "tasks.md")):
        source_abs = os.path.join(change_dir, filename)
        if os.path.isfile(source_abs):
            cmd += ["--source", f"{label}={rel_link(out_dir, source_abs)}"]
    if objective:
        cmd += ["--objective", objective]
    if args.badge:
        cmd += ["--badge", args.badge]
    if args.decisions:
        cmd += ["--decisions", args.decisions]

    strict = not args.no_strict_details
    if strict:
        cmd_strict = cmd + ["--strict-details"]
        result = run(cmd_strict, repo)
        if result.returncode != 0:
            missing = generate.missing_details(lots)
            details = "; ".join(f"{key}: {', '.join(ids)}" for key, ids in missing.items() if ids)
            sys.stderr.write(
                "— détails de tâche incomplets (mode non strict de repli). "
                f"Ajouter Technique/Acceptation puis régénérer. {details}\n"
            )
            strict = False
    if not strict:
        result = run(cmd, repo)

    if result.returncode != 0:
        sys.stderr.write(f"generate.py a échoué :\n{result.stdout.strip()}\n{result.stderr.strip()}\n")
        return result.returncode

    readme_updated = False
    if not args.no_readme:
        readme_updated = update_readme(repo, change_id, tasks_count, lots_count)

    print(result.stdout.strip())
    print(
        f"→ change {change_id} : {tasks_count} tâches / {lots_count} lots ; "
        f"suivi {'strict' if strict else 'NON strict'} : {os.path.relpath(out_abs, repo)}"
        + (" ; ligne ajoutée à docs/README.md" if readme_updated else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
