"""Point d'entrée CLI de la Console SDLC.

Usage :
    sdlc-console --version
    sdlc-console init [--database sqlite:///data/sdlc.sqlite3]
    sdlc-console doctor [--config sdlc.config.yaml] [--database ...]
    sdlc-console schema status|migrate [--database ...]
    sdlc-console serve [--host 127.0.0.2] [--port 8765] [--config ...] [--database ...]

L'écoute par défaut est strictement locale. Aucune authentification n'est
implémentée dans le MVP ; le bind hors boucle locale est refusé.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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

    return parser


def main(argv: list[str] | None = None) -> int:
    """Exécute la commande et renvoie un code de sortie normalisé (0, 1, 2)."""
    parser = build_parser()
    args = parser.parse_args(argv)

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

        if args.open_suivi:
            print("ouverture du suivi demandée (implémentée à la tâche 3.5)", file=sys.stderr)
        print(f"projet : {config.project_name} — confidentialité : {config.confidentiality}")
        uvicorn.run("sdlc_console.app:app", host=args.host, port=args.port)
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
