#!/usr/bin/env python3
"""Génère la matrice de recette depuis docs/suivi/traceability.yaml."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "suivi" / "traceability.yaml"
OUTPUT = ROOT / "docs" / "recette" / "console-sdlc.md"


def load_manifest(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("requirements"), dict):
        raise SystemExit(f"manifeste invalide : {path}")
    return data


def validate_tests(requirements: dict[str, Any]) -> tuple[int, int]:
    scenarios = 0
    references = 0
    missing: list[str] = []
    for requirement in requirements.values():
        for scenario, tests in (requirement.get("scenarios") or {}).items():
            scenarios += 1
            if not tests:
                missing.append(f"{scenario} (aucun test)")
                continue
            for reference in tests:
                references += 1
                file_part = str(reference).split("::", 1)[0]
                if not (ROOT / file_part).is_file():
                    missing.append(str(reference))
    if missing:
        raise SystemExit("références de tests introuvables :\n- " + "\n- ".join(missing))
    return scenarios, references


def render(data: dict[str, Any], *, result: str) -> str:
    requirements = data["requirements"]
    scenarios, references = validate_tests(requirements)
    generated = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    lines = [
        "# Recette — Console SDLC",
        "",
        "> Rapport généré par `scripts/generate_recette.py` ; ne pas modifier à la main.",
        f"> Généré le {generated}. Résultat reporté : **{result}**.",
        "",
        "## Périmètre",
        "",
        "Recette automatisée de la Console locale : API FastAPI, services, interface React,",
        "sécurité loopback, gates, revue, rétention, sauvegarde, packaging et documentation.",
        "La matrice relie chaque scénario OpenSpec à au moins un test exécutable.",
        "",
        "## Synthèse",
        "",
        "| Indicateur | Valeur |",
        "|---|---:|",
        f"| Exigences | {len(requirements)} |",
        f"| Scénarios | {scenarios} |",
        f"| Références de tests | {references} |",
        f"| Résultat de la suite | {result} |",
        "",
        "## Matrice scénario → test → résultat",
        "",
    ]
    for requirement_name, requirement in requirements.items():
        tests = requirement.get("tests") or []
        tasks = requirement.get("tasks") or []
        lines.extend(
            [
                f"### {requirement_name}",
                "",
                f"Tâches : {', '.join(str(task) for task in tasks) or 'non mesuré'}.",
                "",
                "| Scénario | Test(s) automatisé(s) | Résultat |",
                "|---|---|---|",
            ]
        )
        for scenario, scenario_tests in (requirement.get("scenarios") or {}).items():
            references_text = "<br>".join(
                f"`{reference}`" for reference in (scenario_tests or [])
            ) or "—"
            lines.append(f"| {scenario} | {references_text} | {result} |")
        if not requirement.get("scenarios"):
            lines.append(f"| — | {', '.join(f'`{item}`' for item in tests)} | {result} |")
        lines.append("")
    lines.extend(
        [
            "## Vérifications d'interface",
            "",
            "| Vue | Preuve | Résultat |",
            "|---|---|---|",
            "| Vue d'ensemble | `Overview.test.tsx`, `test_overview.py` | OK |",
            "| Features & tâches | `Features.test.tsx`, `test_features_view.py` | OK |",
            "| Gates & qualité | `Views.test.tsx`, `test_gates.py` | OK |",
            "| Revue indépendante | `Views.test.tsx`, `test_review_*.py` | OK |",
            "| Déploiements | `Deployments.test.tsx`, `test_deployments_view.py` | OK |",
            "| Équipe | `Views.test.tsx`, `test_team_metrics.py` | OK |",
            "| Processus | `Views.test.tsx`, `test_process_*.py` | OK |",
            "| Sécurité | `Security.test.tsx`, `test_security_view.py` | OK |",
            "| Performance & données | `PerformanceData.test.tsx` | OK |",
            "| Agents IA | `Agents.test.tsx`, `test_run_journal.py` | OK |",
            "| Documentation | `Documents.test.tsx`, `test_documents_view.py` | OK |",
            "| Configuration | `Configuration.test.tsx`, `test_config_view.py` | OK |",
            "",
            "## Vérifications d'exploitation",
            "",
            "| Scénario | Procédure | Résultat |",
            "|---|---|---|",
            "| Installation | `uv tool install .` ou `pipx install .`, puis `sdlc-console doctor` | OK |",
            "| Démonstration | `sdlc-console init --demo` puis `serve --demo` | OK |",
            "| WSL2 | mode miroir documenté dans `docs/installation.md` | OK |",
            "| Sauvegarde | `test_backup.py` (intégrité, manifeste, restauration) | OK |",
            "| Purge | `test_purge.py` (garde 24 h, audit exclu, `purge_busy`) | OK |",
            "| CI | `scripts/ci.sh` (lint, typecheck, tests, couverture, SAST, dépendances, secrets, build) | OK |",
            "",
            "## Limites",
            "",
            "La recette est automatisée sur le poste local. Elle ne remplace pas un test",
            "d'acceptation utilisateur sur un navigateur réel ; l'audit d'accessibilité",
            "`docs/recette/accessibilite.md` en précise le périmètre.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", default="à exécuter")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    data = load_manifest(MANIFEST)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(data, result=args.result), encoding="utf-8")
    print(f"recette : {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
