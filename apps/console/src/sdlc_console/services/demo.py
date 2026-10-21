"""Jeu de démonstration local, idempotent et sans dépendance réseau."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Deployment, Project, TaskRun
from .audit import append_audit
from .features import create_feature, create_task
from .gates import ControlResult, Evidence, run_gate
from .projects import add_repository, create_project

DEMO_SLUG = "atlas-demo"


def seed_demo(session: Session, *, root: str | Path | None = None) -> dict[str, Any]:
    """Crée un projet de démonstration complet, rejouable sans doublon."""
    root_path = Path(root or Path.cwd()).resolve()
    existing = session.scalar(select(Project).where(Project.slug == DEMO_SLUG))
    if existing is not None:
        return {
            "project": {"id": existing.id, "name": existing.name, "slug": existing.slug},
            "seeded": False,
            "detail": "projet de démonstration déjà présent",
        }
    project = create_project(session, name="Atlas Démo", slug=DEMO_SLUG)
    repositories = []
    for index, name in enumerate(("atlas-api", "atlas-web")):
        path = root_path / "demo" / name
        path.mkdir(parents=True, exist_ok=True)
        (path / ".git").mkdir(exist_ok=True)
        repositories.append(
            add_repository(
                session,
                project,
                name=name,
                provider="github",
                url=f"https://github.com/hm/{name}",
                local_path=path,
                is_primary=index == 0,
            )
        )
    feature = create_feature(
        session,
        project,
        key="demo",
        name="Console de démonstration",
        status="doing",
        primary_repository=repositories[0],
        repository_ids=[repository.id for repository in repositories],
        objective="Montrer les vues avec des données réelles et des preuves.",
        version="0.1.0-demo",
    )
    tasks = [
        ("1.1", "Initialiser la démo", "done", "Première tâche terminée."),
        ("1.2", "Brancher la sécurité", "done", "Findings et dérogations visibles."),
        ("1.3", "Préparer la recette", "doing", "Recette en cours."),
        ("1.4", "Déployer en préprod", "todo", None),
        ("1.5", "Décision go/no-go", "blocked", "Décision humaine requise."),
    ]
    for key, title, status, note in tasks:
        create_task(
            session,
            feature,
            key=key,
            title=title,
            status=status,
            primary_repository=repositories[0],
            executor_label="opencode",
            reviewer_label="claude",
            note=note,
            lot="démo",
            acceptance="La vue correspondante est alimentée.",
        )
    now = datetime.now(UTC)
    for index, status in enumerate(("done", "done", "running", "failed", "timeout")):
        session.add(
            TaskRun(
                project_id=project.id,
                run_id=f"demo-run-{index + 1}",
                task_key=tasks[index][0],
                agent_id="opencode" if index % 2 == 0 else "claude",
                model="deepseek-v4.1-flash" if index % 2 == 0 else "sonnet",
                role="reviewer" if index == 1 else "executor",
                status=status,
                origin="lancée",
                cost_eur=0.42 + index * 0.1,
                tokens_in=1200 + index * 100,
                tokens_out=300 + index * 50,
                started_at=now - timedelta(hours=6 - index),
                ended_at=now - timedelta(hours=5 - index) if status != "running" else None,
                imported_at=now,
            )
        )
    for index, (env, status, rollback) in enumerate(
        (
            ("dev", "success", False),
            ("preprod", "success", False),
            ("prod", "success", False),
            ("prod", "rollback", True),
            ("dev", "in_progress", False),
        )
    ):
        session.add(
            Deployment(
                project_id=project.id,
                deploy_id=f"demo-deploy-{index + 1}",
                env=env,
                version=f"0.1.{index}",
                status=status,
                is_rollback=rollback,
                rollback_of_version="0.1.2" if rollback else None,
                started_at=now - timedelta(days=index + 1),
                by_label="équipe démo",
                feature_id=feature.id,
                feature_key=feature.key,
                imported_at=now,
            )
        )
    evidence_dir = root_path / "reports" / "demo"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence = evidence_dir / "evidence.txt"
    evidence.write_text("Preuve de démonstration.\n", encoding="utf-8")
    for key, label in (
        ("tests", "Tests"),
        ("coverage", "Couverture"),
        ("security", "Sécurité"),
        ("performance", "Performance"),
        ("data", "Données"),
        ("recette", "Recette"),
        ("go_no_go", "Go / no-go"),
    ):
        run_gate(
            session,
            project,
            key,
            [
                ControlResult(
                    key="demo",
                    verdict="pass",
                    reason=f"preuve de démonstration — {label}",
                    evidence=(Evidence(path="reports/demo/evidence.txt", kind="demo"),),
                )
            ],
            gate_name=label,
            root=root_path,
        )
    append_audit(
        session,
        project_id=project.id,
        action="demo.seeded",
        object_type="project",
        object_id=project.id,
        payload={"tasks": len(tasks), "repositories": len(repositories)},
    )
    session.commit()
    return {
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "seeded": True,
        "repositories": len(repositories),
        "tasks": len(tasks),
        "runs": 5,
        "deployments": 5,
        "gates": 7,
        "detail": "jeu de démonstration créé",
    }
