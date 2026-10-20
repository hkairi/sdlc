"""Génération du fichier de suivi HTML/JSON depuis la base."""

# ruff: noqa: E501 — le template HTML/CSS contient des lignes volontairement longues.

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Feature, Project, Task, utc_now
from .providers.common import parse_datetime

STATUS_LABELS = {
    "todo": "À faire",
    "doing": "En cours",
    "done": "Terminé",
    "blocked": "Bloqué",
    "cancelled": "Annulé",
}


@dataclass(frozen=True)
class SuiviDocument:
    """Document de suivi généré et écrit sur disque."""

    data: dict[str, Any]
    html: str
    json_text: str
    html_path: Path
    json_path: Path
    generated_at: datetime


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _json_value(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return default


def _task_owner(task: Task) -> str | None:
    if task.owner is not None:
        return task.owner.display_name
    return task.executor_label


def _task_reviewer(task: Task) -> str | None:
    if task.reviewer is not None:
        return task.reviewer.display_name
    return task.reviewer_label


def _task_data(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "key": task.key,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "lot": task.lot,
        "owner": _task_owner(task),
        "reviewer": _task_reviewer(task),
        "files": _json_value(task.files_json, []),
        "acceptance": task.acceptance,
        "note": task.note,
        "updated_at": _iso(task.updated_at),
        "checked": task.status == "done",
    }


def _feature_data(feature: Feature) -> dict[str, Any]:
    tasks = sorted(feature.tasks, key=lambda task: task.key)
    repositories = sorted(feature.repository_links, key=lambda link: link.repository.name)
    done = sum(1 for task in tasks if task.status == "done")
    return {
        "id": feature.id,
        "key": feature.key,
        "name": feature.name,
        "status": feature.status,
        "objective": feature.objective,
        "change": feature.change,
        "spec_path": feature.spec_path,
        "tasks_file": feature.tasks_file,
        "sources": _json_value(feature.sources_json, {}),
        "version": feature.version,
        "delivered": feature.delivered,
        "blocked": feature.blocked,
        "updated_at": _iso(feature.updated_at),
        "repositories": [
            {
                "id": link.repository.id,
                "name": link.repository.name,
                "is_primary": link.repository.is_primary,
            }
            for link in repositories
        ],
        "summary": {
            "tasks": len(tasks),
            "done": done,
            "progress_percent": round(done * 100 / len(tasks)) if tasks else 0,
        },
        "tasks": [_task_data(task) for task in tasks],
    }


def build_suivi_data(
    session: Session,
    project: Project,
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Construit la représentation JSON du suivi, sans écrire de fichier."""
    moment = generated_at or utc_now()
    features = list(
        session.scalars(
            select(Feature)
            .where(Feature.project_id == project.id)
            .order_by(Feature.key)
        ).all()
    )
    features_data = [_feature_data(feature) for feature in features]
    tasks = [task for feature in features for task in feature.tasks]
    counts = {
        status: sum(1 for task in tasks if task.status == status)
        for status in STATUS_LABELS
    }
    done = counts["done"]
    return {
        "schema": 1,
        "generated_at": _iso(moment),
        "project": {
            "id": project.id,
            "name": project.name,
            "slug": project.slug,
            "timezone": project.timezone,
        },
        "summary": {
            "features": len(features),
            "tasks": len(tasks),
            **counts,
            "progress_percent": round(done * 100 / len(tasks)) if tasks else 0,
        },
        "features": features_data,
    }


def _status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def _status_class(status: str) -> str:
    return status if status in STATUS_LABELS else "todo"


def _render_task_rows(tasks: list[dict[str, Any]]) -> str:
    if not tasks:
        return '<tr><td colspan="6" class="empty">Aucune tâche.</td></tr>'
    rows: list[str] = []
    for task in tasks:
        title = html.escape(str(task["title"]))
        description = task.get("description")
        if description and description != task["title"]:
            title += f'<div class="muted">{html.escape(str(description))}</div>'
        rows.append(
            "<tr>"
            f'<td class="key">{html.escape(str(task["key"]))}</td>'
            f'<td class="task">{title}</td>'
            f'<td>{html.escape(str(task.get("lot") or "—"))}</td>'
            f'<td><span class="status status-{_status_class(str(task["status"]))}">'
            f'{html.escape(_status_label(str(task["status"])))}</span></td>'
            f'<td>{html.escape(str(task.get("owner") or "—"))}</td>'
            f'<td class="muted">{html.escape(str(task.get("updated_at") or "—"))}</td>'
            "</tr>"
        )
    return "".join(rows)


def _render_feature(feature: dict[str, Any]) -> str:
    title = html.escape(str(feature["name"]))
    progress = int(feature["summary"]["progress_percent"])
    tasks = feature.get("tasks", [])
    rows = _render_task_rows(tasks if isinstance(tasks, list) else [])
    objective = feature.get("objective")
    objective_html = (
        f'<p class="objective">{html.escape(str(objective))}</p>' if objective else ""
    )
    repositories = ", ".join(
        html.escape(str(repository["name"]))
        for repository in feature.get("repositories", [])
    ) or "—"
    return f"""
    <section class="feature" id="feature-{feature['id']}" aria-labelledby="feature-title-{feature['id']}">
      <div class="feature-head">
        <div>
          <p class="eyebrow">{html.escape(_status_label(str(feature['status'])))} · {html.escape(str(feature['key']))}</p>
          <h2 id="feature-title-{feature['id']}">{title}</h2>
          {objective_html}
          <p class="meta">Dépôts : {repositories}</p>
        </div>
        <div class="progress-box" aria-label="Avancement de {title}">
          <span class="progress-value">{progress}%</span>
          <progress value="{progress}" max="100">{progress}%</progress>
          <span class="muted">{feature['summary']['done']} / {feature['summary']['tasks']} tâches</span>
        </div>
      </div>
      <table>
        <caption>Tâches de la feature {title}</caption>
        <thead>
          <tr><th scope="col">Clé</th><th scope="col">Tâche</th><th scope="col">Lot</th><th scope="col">Statut</th><th scope="col">Exécutant</th><th scope="col">Mise à jour</th></tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
    """


def render_suivi_html(data: dict[str, Any]) -> str:
    """Rend un HTML autonome, accessible et sans ressource externe."""
    project = data["project"]
    summary = data["summary"]
    project_name = html.escape(str(project["name"]))
    features = data.get("features", [])
    feature_html = "".join(_render_feature(feature) for feature in features)
    if not features:
        feature_html = '<p class="empty">Aucune feature ingérée pour ce projet.</p>'
    generated = html.escape(str(data.get("generated_at") or ""))
    cards = [
        ("Features", summary["features"]),
        ("Tâches", summary["tasks"]),
        ("Terminées", summary["done"]),
        ("En cours", summary["doing"]),
        ("À faire", summary["todo"]),
        ("Bloquées", summary["blocked"]),
    ]
    cards_html = "".join(
        f'<div class="card"><span class="card-value">{value}</span><span class="card-label">{html.escape(label)}</span></div>'
        for label, value in cards
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="generator" content="Console SDLC">
  <title>Suivi — {project_name}</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f7f7f5;
      --surface: #ffffff;
      --text: #18212b;
      --muted: #5b6773;
      --line: #d9dee3;
      --accent: #1f5f8b;
      --done: #176b45;
      --doing: #8a5a00;
      --blocked: #a12a2a;
      --todo: #4a5560;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #12171c;
        --surface: #1b232b;
        --text: #eef3f7;
        --muted: #b3bec8;
        --line: #33414d;
        --accent: #8dc4e8;
        --done: #7fd6a8;
        --doing: #f0c46b;
        --blocked: #ff9b9b;
        --todo: #c0c8cf;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
    .wrap {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 56px; }}
    header {{ border-bottom: 2px solid var(--accent); padding-bottom: 18px; margin-bottom: 22px; }}
    h1 {{ margin: 0 0 6px; font-size: clamp(1.6rem, 3vw, 2.2rem); }}
    h2 {{ margin: 0; font-size: 1.15rem; }}
    .eyebrow {{ margin: 0 0 4px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; font-size: .75rem; }}
    .notice {{ background: var(--surface); border: 1px solid var(--line); border-left: 4px solid var(--accent); padding: 10px 14px; margin: 0 0 20px; color: var(--muted); }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; margin: 20px 0 28px; }}
    .card {{ background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; }}
    .card-value {{ display: block; font-size: 1.6rem; font-weight: 700; }}
    .card-label {{ color: var(--muted); font-size: .85rem; }}
    .feature {{ background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 18px; margin: 0 0 20px; }}
    .feature-head {{ display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; margin-bottom: 14px; }}
    .objective {{ margin: 8px 0 0; color: var(--muted); }}
    .meta {{ margin: 6px 0 0; color: var(--muted); font-size: .9rem; }}
    .progress-box {{ min-width: 170px; text-align: right; }}
    .progress-value {{ display: block; font-weight: 700; font-size: 1.2rem; }}
    progress {{ width: 100%; height: 10px; accent-color: var(--accent); }}
    table {{ width: 100%; border-collapse: collapse; font-size: .92rem; }}
    caption {{ text-align: left; color: var(--muted); padding: 0 0 8px; }}
    th, td {{ text-align: left; padding: 9px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }}
    th {{ font-size: .78rem; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); }}
    .key {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; white-space: nowrap; }}
    .task {{ min-width: 260px; }}
    .status {{ display: inline-block; border: 1px solid currentColor; border-radius: 999px; padding: 1px 9px; font-size: .78rem; font-weight: 600; white-space: nowrap; }}
    .status-done {{ color: var(--done); }}
    .status-doing {{ color: var(--doing); }}
    .status-blocked {{ color: var(--blocked); }}
    .status-todo, .status-cancelled {{ color: var(--todo); }}
    .muted {{ color: var(--muted); }}
    .empty {{ color: var(--muted); padding: 18px 8px; }}
    footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid var(--line); color: var(--muted); font-size: .85rem; }}
    @media (max-width: 720px) {{
      .feature-head {{ flex-direction: column; }}
      .progress-box {{ text-align: left; width: 100%; }}
      table {{ display: block; overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <header>
      <p class="eyebrow">Console SDLC · Suivi</p>
      <h1>{project_name}</h1>
      <p class="muted">Généré le <time datetime="{generated}">{generated}</time></p>
    </header>
    <p class="notice"><strong>Fichier généré, ne pas modifier.</strong> Régénérez-le depuis la Console SDLC.</p>
    <section class="cards" aria-label="Synthèse">{cards_html}</section>
    <p class="muted">Avancement global : {summary['progress_percent']}% ({summary['done']} / {summary['tasks']} tâches terminées).</p>
    {feature_html}
    <footer>Console SDLC — suivi généré depuis la base locale. Aucune ressource externe n'est chargée.</footer>
  </main>
</body>
</html>
"""


def default_suivi_paths(project: Project, docs_dir: str | Path | None = None) -> tuple[Path, Path]:
    """Chemins par défaut : `docs/suivi-<slug>.html` et JSON généré séparé.

    Le JSON généré ne doit pas écraser `docs/suivi/<slug>.json`, qui est la
    source `state.json` du suivi.
    """
    base = Path(docs_dir or "docs")
    return base / f"suivi-{project.slug}.html", base / "suivi" / f"{project.slug}.generated.json"


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def generate_suivi(
    session: Session,
    project: Project,
    *,
    html_path: str | Path | None = None,
    json_path: str | Path | None = None,
    docs_dir: str | Path | None = None,
    generated_at: datetime | None = None,
) -> SuiviDocument:
    """Construit, écrit et renvoie le suivi HTML/JSON."""
    moment = generated_at or utc_now()
    data = build_suivi_data(session, project, generated_at=moment)
    html_text = render_suivi_html(data)
    json_text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    default_html, default_json = default_suivi_paths(project, docs_dir)
    html_target = Path(html_path) if html_path is not None else default_html
    json_target = Path(json_path) if json_path is not None else default_json
    _write_atomic(html_target, html_text)
    _write_atomic(json_target, json_text)
    return SuiviDocument(
        data=data,
        html=html_text,
        json_text=json_text,
        html_path=html_target,
        json_path=json_target,
        generated_at=moment,
    )


def _latest_update(session: Session, project: Project) -> datetime | None:
    feature_latest = session.scalar(
        select(func.max(Feature.updated_at)).where(Feature.project_id == project.id)
    )
    task_latest = session.scalar(
        select(func.max(Task.updated_at)).join(Feature, Task.feature_id == Feature.id).where(
            Feature.project_id == project.id
        )
    )
    values = [value for value in (feature_latest, task_latest) if value is not None]
    if not values:
        return None
    latest = max(values)
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=UTC)
    return latest


def suivi_status(
    session: Session,
    project: Project,
    *,
    html_path: str | Path | None = None,
    json_path: str | Path | None = None,
    docs_dir: str | Path | None = None,
) -> dict[str, Any]:
    """État du suivi : prêt/non prêt, génération, chemins et fraîcheur."""
    default_html, default_json = default_suivi_paths(project, docs_dir)
    html_target = Path(html_path) if html_path is not None else default_html
    json_target = Path(json_path) if json_path is not None else default_json
    ready = html_target.is_file() and json_target.is_file()
    data: dict[str, Any] | None = None
    if json_target.is_file():
        try:
            loaded = json.loads(json_target.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, json.JSONDecodeError):
            data = None
    generated_at = data.get("generated_at") if data else None
    if generated_at is None and json_target.is_file():
        generated_at = _iso(datetime.fromtimestamp(json_target.stat().st_mtime, UTC))
    summary = data.get("summary") if data else build_suivi_data(session, project)["summary"]
    generated_dt = parse_datetime(generated_at) if generated_at else None
    latest = _latest_update(session, project)
    stale = bool(
        ready
        and generated_dt is not None
        and latest is not None
        and latest > generated_dt
    )
    return {
        "ready": ready,
        "generated_at": generated_at,
        "html_path": str(html_target),
        "json_path": str(json_target),
        "stale": stale,
        "summary": summary,
    }
