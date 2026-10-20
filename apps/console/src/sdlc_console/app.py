"""Application FastAPI de la Console SDLC.

Le squelette L0 expose `/api/health` et `/api/csrf`. Les routes métier arrivent
avec les lots suivants.
"""

from __future__ import annotations

from fastapi import FastAPI

from . import __version__
from .security import (
    DEFAULT_ALLOWED_HOSTS,
    DEFAULT_ALLOWED_ORIGINS,
    CsrfProtector,
    SecurityMiddleware,
)


def create_app(
    *,
    allowed_hosts: set[str] | None = None,
    allowed_origins: set[str] | None = None,
    csrf_secret: bytes | None = None,
) -> FastAPI:
    """Crée l'application FastAPI avec la sécurité locale."""
    app = FastAPI(title="Console SDLC", version=__version__)
    csrf = CsrfProtector(csrf_secret)
    app.add_middleware(
        SecurityMiddleware,
        allowed_hosts=allowed_hosts or set(DEFAULT_ALLOWED_HOSTS),
        allowed_origins=allowed_origins or set(DEFAULT_ALLOWED_ORIGINS),
        csrf=csrf,
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/csrf")
    def csrf_token() -> dict[str, str]:
        return {"token": csrf.issue()}

    return app


app = create_app()
