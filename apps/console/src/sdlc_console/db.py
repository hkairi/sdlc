"""Accès SQLite : moteur, pragmas et sessions.

Le fichier de base est un fichier unique. Les pragmas sont appliqués à chaque
connexion : WAL, clés étrangères, synchronous=NORMAL et busy_timeout=5000.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DATABASE_URL = "sqlite:///data/sdlc.sqlite3"
SQLITE_PREFIX = "sqlite:///"


def _ensure_parent(url: str) -> None:
    """Crée le dossier du fichier SQLite s'il n'existe pas."""
    if not url.startswith(SQLITE_PREFIX):
        return
    path = Path(url[len(SQLITE_PREFIX) :])
    if path.parent and str(path.parent) != ".":
        path.parent.mkdir(parents=True, exist_ok=True)


def make_engine(url: str = DEFAULT_DATABASE_URL, *, echo: bool = False) -> Engine:
    """Crée un moteur SQLAlchemy et applique les pragmas SQLite."""
    _ensure_parent(url)
    engine = create_engine(url, echo=echo, future=True)

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection: object, _connection_record: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            try:
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=5000")
            finally:
                cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Crée une fabrique de sessions liée au moteur."""
    return sessionmaker(bind=engine, expire_on_commit=False)
