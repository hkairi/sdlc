"""Point d'entrée CLI de la Console SDLC.

Usage :
    sdlc-console --version
    sdlc-console init [--database sqlite:///data/sdlc.sqlite3]
    sdlc-console doctor [--config sdlc.config.yaml] [--database ...]
    sdlc-console schema status|migrate [--database ...]
    sdlc-console task set <id> <statut> [--note "..."] [--project ...]
    sdlc-console serve [--host 127.0.0.2] [--port 8765] [--config ...] [--database ...]

L'écoute par défaut est strictement locale. Aucune authentification n'est
implémentée dans le MVP ; le bind hors boucle locale est refusé.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, cast

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from . import __version__
from .db import DEFAULT_DATABASE_URL

DEFAULT_HOST = "127.0.0.2"
DEFAULT_PORT = 8765
DEFAULT_CONFIG = "sdlc.config.yaml"


def _console_root() -> Path:
    """Racine de `apps/console` (dossier de `alembic.ini`)."""
    return Path(__file__).resolve().parents[2]


def _alembic_config(database_url: str) -> Config:
    """Construit la configuration Alembic pour une base donnée."""
    ini = _console_root() / "alembic.ini"
    if not ini.exists():
        raise RuntimeError(f"alembic.ini introuvable : {ini}")
    config = Config(str(ini))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _schema_state(database_url: str) -> tuple[str | None, str | None]:
    """Renvoie (révision actuelle, révision cible)."""
    from .db import make_engine

    config = _alembic_config(database_url)
    head = ScriptDirectory.from_config(config).get_current_head()
    engine = make_engine(database_url)
    try:
        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()
    return current, head


def _run_migrations(database_url: str) -> None:
    """Applique les migrations jusqu'à head."""
    command.upgrade(_alembic_config(database_url), "head")


def _resolve_database_url(explicit: str | None, config: object | None = None) -> str:
    """Priorité : option CLI, puis `database.url` de la config, puis défaut."""
    if explicit:
        return explicit
    if config is not None:
        data = getattr(config, "data", {})
        database = data.get("database") if isinstance(data, dict) else None
        if isinstance(database, dict) and database.get("url"):
            return str(database["url"])
    return DEFAULT_DATABASE_URL


def _print_schema(database_url: str) -> int:
    """Affiche l'état du schéma et renvoie 0 si à jour, 1 sinon."""
    current, head = _schema_state(database_url)
    print(f"base : {database_url}")
    print(f"révision actuelle : {current or '(aucune)'}")
    print(f"révision cible : {head or '(aucune)'}")
    if current == head:
        print("schéma : à jour")
        return 0
    print("schéma : migration requise (sdlc-console schema migrate)")
    return 1


def build_parser() -> argparse.ArgumentParser:
    """Construit le parseur de commandes."""
    parser = argparse.ArgumentParser(
        prog="sdlc-console",
        description="Console SDLC locale — tableau de bord, gates, revue, équipe et processus.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init", help="Créer la base et appliquer les migrations")
    init.add_argument("--database", default=None, help="URL SQLAlchemy de la base")

    serve = sub.add_parser("serve", help="Lancer le serveur local")
    serve.add_argument("--host", default=DEFAULT_HOST, help=f"Adresse d'écoute (défaut : {DEFAULT_HOST})")
    serve.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port (défaut : {DEFAULT_PORT})")
    serve.add_argument("--config", default=DEFAULT_CONFIG, help="Chemin de sdlc.config.yaml")
    serve.add_argument("--database", default=None, help="URL SQLAlchemy de la base")
    serve.add_argument("--open-suivi", action="store_true", help="Ouvrir la vue Suivi dès qu'elle est prête")

    doctor = sub.add_parser("doctor", help="Diagnostic local")
    doctor.add_argument("--config", default=DEFAULT_CONFIG, help="Chemin de sdlc.config.yaml")
    doctor.add_argument("--database", default=None, help="URL SQLAlchemy de la base")
    doctor.add_argument("--with-tokens", action="store_true", help="Vérifier les jetons GitHub/GitLab")

    schema = sub.add_parser("schema", help="Gérer le schéma de la base")
    schema_sub = schema.add_subparsers(dest="schema_command")
    for name, help_text in (("status", "Afficher l'état du schéma"), ("migrate", "Appliquer les migrations")):
        command = schema_sub.add_parser(name, help=help_text)
        command.add_argument("--database", default=None, help="URL SQLAlchemy de la base")

    task = sub.add_parser("task", help="Gérer une tâche")
    task_sub = task.add_subparsers(dest="task_command")
    task_set = task_sub.add_parser("set", help="Changer le statut d'une tâche")
    task_set.add_argument("task", help="ID numérique ou clé de tâche")
    task_set.add_argument(
        "status",
        choices=["todo", "doing", "done", "blocked", "cancelled"],
        help="Nouveau statut",
    )
    task_set.add_argument("--note", default=None, help="Note de fin de tâche")
    task_set.add_argument("--project", default=None, help="Slug du projet")
    task_set.add_argument("--config", default=DEFAULT_CONFIG, help="Chemin de sdlc.config.yaml")
    task_set.add_argument("--database", default=None, help="URL SQLAlchemy de la base")
    task_set.add_argument("--state", default=None, help="Chemin de state.json")
    task_set.add_argument("--tasks", default=None, help="Chemin de tasks.md")
    task_set.add_argument("--html", default=None, help="Chemin du suivi HTML")
    task_set.add_argument("--json", default=None, help="Chemin du JSON généré")
    task_set.add_argument("--root", default=None, help="Racine du projet (défaut : cwd)")

    return parser


def _task_set(args: argparse.Namespace) -> int:
    """Commande `task set` : met à jour les trois supports et la base."""
    from sqlalchemy import select

    from .config import ConfigError, load_config
    from .db import make_engine, make_session_factory
    from .models import Feature, Project, Task
    from .services.task_update import TaskUpdateError, update_task_status

    root = Path(args.root).resolve() if args.root else Path.cwd().resolve()
    config = None
    try:
        config = load_config(args.config)
    except ConfigError:
        if Path(args.config).exists():
            print(f"configuration invalide : {args.config}", file=sys.stderr)
            return 2
    database_url = _resolve_database_url(args.database, config)
    engine = make_engine(database_url)
    factory = make_session_factory(engine)
    try:
        with factory() as session:
            if args.project:
                project = session.scalar(
                    select(Project).where(Project.slug == args.project)
                )
            else:
                projects = list(session.scalars(select(Project)).all())
                project = projects[0] if len(projects) == 1 else None
            if project is None:
                print(
                    "projet introuvable ou ambigu : préciser --project <slug>",
                    file=sys.stderr,
                )
                return 2

            task: Task | None
            if args.task.isdigit():
                task = session.get(Task, int(args.task))
                if task is not None and task.feature.project_id != project.id:
                    task = None
            elif ":" in args.task:
                feature_key, task_key = args.task.split(":", 1)
                task = session.scalar(
                    select(Task)
                    .join(Feature, Task.feature_id == Feature.id)
                    .where(
                        Feature.project_id == project.id,
                        Feature.key == feature_key,
                        Task.key == task_key,
                    )
                )
            else:
                candidates = list(
                    session.scalars(
                        select(Task)
                        .join(Feature, Task.feature_id == Feature.id)
                        .where(
                            Feature.project_id == project.id,
                            Task.key == args.task,
                        )
                    ).all()
                )
                task = candidates[0] if len(candidates) == 1 else None
            if task is None:
                print(f"tâche introuvable : {args.task}", file=sys.stderr)
                return 2

            docs_dir = None
            state_path = Path(args.state) if args.state else None
            html_path = Path(args.html) if args.html else None
            data = config.data if config is not None and isinstance(config.data, dict) else {}
            raw_paths = data.get("paths")
            paths: dict[str, Any] = (
                cast(dict[str, Any], raw_paths) if isinstance(raw_paths, dict) else {}
            )
            if state_path is None and paths.get("suivi"):
                state_path = Path(str(paths["suivi"])) / f"{project.slug}.json"
            if html_path is None:
                raw_ui = data.get("ui")
                ui: dict[str, Any] = (
                    cast(dict[str, Any], raw_ui) if isinstance(raw_ui, dict) else {}
                )
                if ui.get("suivi_path"):
                    html_path = Path(str(ui["suivi_path"]))
            if paths.get("docs"):
                docs_dir = Path(str(paths["docs"]))

            try:
                result = update_task_status(
                    session,
                    project,
                    task,
                    status=args.status,
                    note=args.note,
                    state_path=state_path,
                    tasks_path=Path(args.tasks) if args.tasks else None,
                    html_path=html_path,
                    json_path=Path(args.json) if args.json else None,
                    docs_dir=docs_dir,
                    root=root,
                )
            except (TaskUpdateError, OSError) as exc:
                print(f"mise à jour refusée : {exc}", file=sys.stderr)
                return 1
            print(
                f"tâche {result.task.key} : {result.status}"
                f" — {result.duration_ms} ms"
            )
            print(f"tasks.md  : {result.tasks_path}")
            print(f"state.json: {result.state_path}")
            print(f"HTML      : {result.html_path}")
            print(f"JSON      : {result.json_path}")
            return 0
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    """Exécute la commande et renvoie un code de sortie normalisé (0, 1, 2)."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "task":
        if args.task_command == "set":
            return _task_set(args)
        print("usage : sdlc-console task set <id> <statut> --note \"...\"", file=sys.stderr)
        return 2

    if args.command == "init":
        database_url = _resolve_database_url(args.database)
        _run_migrations(database_url)
        print(f"base initialisée : {database_url}")
        return 0

    if args.command == "schema":
        if args.schema_command == "status":
            return _print_schema(_resolve_database_url(args.database))
        if args.schema_command == "migrate":
            database_url = _resolve_database_url(args.database)
            _run_migrations(database_url)
            print(f"migrations appliquées : {database_url}")
            return 0
        print("usage : sdlc-console schema {status,migrate}", file=sys.stderr)
        return 2

    if args.command == "serve":
        if args.host != DEFAULT_HOST:
            print(
                f"refus : écoute sur {args.host} — le MVP sans authentification n'autorise que {DEFAULT_HOST}",
                file=sys.stderr,
            )
            return 2

        from .config import ConfigError, load_config

        try:
            config = load_config(args.config)
        except ConfigError as exc:
            print(f"configuration invalide : {exc}", file=sys.stderr)
            return 2

        database_url = _resolve_database_url(args.database, config)
        try:
            current, head = _schema_state(database_url)
        except Exception as exc:  # noqa: BLE001 — message utilisateur explicite
            print(f"schéma : erreur — {exc}", file=sys.stderr)
            return 2
        if current != head:
            print(
                f"schéma non à jour ({current or 'aucune'} → {head}) : lancer sdlc-console schema migrate",
                file=sys.stderr,
            )
            return 2

        import uvicorn

        ui = config.data.get("ui") if isinstance(config.data, dict) else None
        ui = ui if isinstance(ui, dict) else {}
        open_on_ready = bool(args.open_suivi or ui.get("open_suivi_on_ready", True))
        suivi_path = ui.get("suivi_path")
        from .app import create_app
        from .services.gates import config_fingerprint as gate_config_fingerprint

        application = create_app(
            database_url=database_url,
            open_suivi_on_ready=open_on_ready,
            suivi_html_path=str(suivi_path) if suivi_path else None,
            config_fingerprint=gate_config_fingerprint(config.data),
        )
        print(f"projet : {config.project_name} — confidentialité : {config.confidentiality}")
        print(f"ouverture automatique du suivi : {'oui' if open_on_ready else 'non'}")
        uvicorn.run(application, host=args.host, port=args.port)
        return 0

    if args.command == "doctor":
        from .config import ConfigError, load_config

        print(f"sdlc-console {__version__}")
        print(f"python {sys.version.split()[0]}")
        print(f"écoute par défaut : {DEFAULT_HOST}:{DEFAULT_PORT}")
        try:
            config = load_config(args.config)
        except ConfigError as exc:
            print(f"configuration : échec — {exc}")
            return 1
        print(f"configuration : valide ({config.path})")
        print(f"projet : {config.project_name} — confidentialité : {config.confidentiality}")

        database_url = _resolve_database_url(args.database, config)
        try:
            current, head = _schema_state(database_url)
        except Exception as exc:  # noqa: BLE001 — message utilisateur explicite
            print(f"schéma : erreur — {exc}")
            return 1
        print(f"base : {database_url}")
        print(f"révision actuelle : {current or '(aucune)'} | cible : {head or '(aucune)'}")
        if current != head:
            print("schéma : migration requise (sdlc-console schema migrate)")
            return 1
        print("schéma : à jour")

        if args.with_tokens:
            print("jetons : vérification non implémentée (tâche 1.6)")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
