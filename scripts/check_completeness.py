#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vérifie la complétude du framework face à sa spécification de référence.

Contrôle statique, sans dépendance externe : chaque skill citée au § 7 de la
spécification a son `SKILL.md`, chaque profil de déploiement et chaque outil de CI
référencés disposent de leurs fichiers. Échoue (code 1) et liste les manques si la
spec et l'arborescence divergent.

Usage :
    scripts/check_completeness.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Skills citées au § 7 de `.sdlc/workflow-sdlc.md`.
SKILLS = [
    "sdlc-init", "etat-des-lieux", "cadrage", "adr", "spec-review", "tdd",
    "ci-setup", "recette", "deploy-procedure", "runbook", "changelog",
    "change-request", "hotfix", "retro", "metrics", "client-report",
    "suivi-taches", "suivi-projet",
]

# Profils de déploiement (§ 10) et outils de CI (§ 10) et adaptateurs (§ 8).
DEPLOY_PROFILES = ["vps-compose", "kubernetes", "paas", "static", "serverless", "mobile", "package", "on-prem"]
CI_TOOLS = ["github-actions", "gitlab-ci", "forgejo-actions", "jenkins", "none"]
ADAPTERS = ["claude", "codex", "opencode"]

# Gabarits documentaires (§ 7) : chaque skill en produit un.
DOC_TEMPLATES = [
    "brief", "exigences-nf", "etat-des-lieux", "adr", "adr-index", "menaces",
    "runbook", "runbook-fiche", "recette", "change-request", "incident-post-mortem",
    "retro", "client-report", "release-notes",
]


def missing(paths: list[Path]) -> list[str]:
    return [str(p) for p in paths if not p.exists()]


def main() -> int:
    problems: list[str] = []

    problems.extend(missing([ROOT / ".agents" / "skills" / s / "SKILL.md" for s in SKILLS]))
    problems.extend(missing([ROOT / "templates" / "deploy" / p / "deploy.md" for p in DEPLOY_PROFILES]))
    problems.extend(missing([ROOT / "templates" / "deploy" / p / "runbook-sections.md" for p in DEPLOY_PROFILES]))
    problems.extend(missing([ROOT / "templates" / "ci" / t for t in CI_TOOLS]))
    problems.extend(missing([ROOT / "templates" / "adapters" / a for a in ADAPTERS]))
    problems.extend(missing([ROOT / "templates" / "docs" / f"{d}.md" for d in DOC_TEMPLATES]))
    problems.extend(missing([
        ROOT / "templates" / "scripts" / "ci.sh",
        ROOT / "templates" / "handoff" / "report.schema.json",
        ROOT / "templates" / "handoff" / "input.md",
        ROOT / "scripts" / "check_sync.py",
        ROOT / "bin" / "sdlc-install",
    ]))

    if problems:
        print(f"complétude en échec — {len(problems)} élément(s) manquant(s) :")
        for path in problems:
            print(f"  - {path}")
        return 1

    print(
        f"complétude OK — {len(SKILLS)} skills, {len(DEPLOY_PROFILES)} profils de déploiement, "
        f"{len(CI_TOOLS)} outils de CI, {len(ADAPTERS)} adaptateurs, {len(DOC_TEMPLATES)} gabarits docs."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
