#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contrôle de dérive de `sdlc.config.yaml` face au § 4 / § 13.3 de la spécification.

Signale les clés de premier niveau **non documentées** (ni dans le § 4 du framework,
ni dans les extensions documentées de la Console) et les clés `paths.*` manquantes.
C'est un contrôle statique, complémentaire du schéma JSON embarqué de la Console.

Usage :
    scripts/check_config.py [chemin-de-config]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Clés de premier niveau du framework (§ 4) + extensions documentées de la Console
# (apps/console/src/sdlc_console/config.schema.json).
KNOWN_TOP_KEYS = {
    "version", "workflow_version", "project", "agents", "orchestrator", "executors",
    "confidentiality", "providers_allowed", "ci", "deploy", "organisation", "gates",
    "dashboard", "paths",
    "database", "quality", "review", "process", "team", "retention", "ui",
}

REQUIRED_TOP_KEYS = [
    "version", "project", "agents", "orchestrator", "executors", "confidentiality",
    "ci", "deploy", "organisation", "gates", "dashboard", "paths",
]

# Clés `paths.*` du § 13.3.
PATHS_KEYS = [
    "templates", "spec", "docs", "cadrage", "architecture", "adr", "ops", "recette",
    "incidents", "retro", "client", "journal", "suivi", "metrics", "reports", "ci_script",
]


def extract_top_keys(text: str) -> set[str]:
    """Clés de premier niveau : lignes sans indentation de la forme `clé:`."""
    return {m.group(1) for m in re.finditer(r"^([A-Za-z_][A-Za-z0-9_-]*):", text, re.MULTILINE)}


def extract_paths_keys(text: str) -> set[str]:
    """Clés sous `paths:` (indentation de 2 espaces)."""
    in_paths = False
    out: set[str] = set()
    for line in text.splitlines():
        if re.match(r"^paths:", line):
            in_paths = True
            continue
        if in_paths:
            if re.match(r"^[A-Za-z_]", line):  # fin du bloc paths
                break
            m = re.match(r"^  ([A-Za-z_][A-Za-z0-9_-]*):", line)
            if m:
                out.add(m.group(1))
    return out


def extract_scalar(text: str, key: str) -> str | None:
    """Valeur scalaire d'une clé de premier niveau (`workflow_version: "0.1.0"`)."""
    m = re.search(rf"^{key}:\s*[\"']?([^\"'\n#]+?)[\"']?\s*(?:#.*)?$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def main() -> int:
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "sdlc.config.yaml"
    if not config_path.exists():
        print(f"config absente : {config_path}", file=sys.stderr)
        return 2
    text = config_path.read_text(encoding="utf-8")

    top = extract_top_keys(text)
    paths = extract_paths_keys(text)

    problems: list[str] = []
    unknown = sorted(top - KNOWN_TOP_KEYS)
    if unknown:
        problems.append(f"clé(s) de premier niveau non documentée(s) : {', '.join(unknown)}")
    missing = sorted(set(REQUIRED_TOP_KEYS) - top)
    if missing:
        problems.append(f"clé(s) requise(s) absente(s) : {', '.join(missing)}")
    missing_paths = sorted(set(PATHS_KEYS) - paths)
    if missing_paths:
        problems.append(f"clé(s) paths.* manquante(s) : {', '.join(missing_paths)}")

    # Cohérence de version : workflow_version doit suivre la version du framework.
    framework_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    workflow_version = extract_scalar(text, "workflow_version")
    if workflow_version and workflow_version != framework_version:
        problems.append(
            f"workflow_version ({workflow_version}) diffère de la version du framework "
            f"({framework_version}) — rejouer sdlc-init --upgrade."
        )

    if problems:
        print(f"config en échec — {len(problems)} problème(s) :")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("config OK — clés de premier niveau, paths.* et version conformes au § 4 / § 13.3.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
