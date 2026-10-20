"""Sécurité locale de la Console : Host, Origin, CSRF, Content-Type, en-têtes.

L'application n'a pas d'authentification en MVP. Les protections ci-dessous
limitent l'exposition au DNS rebinding, aux POST cross-origin et aux écritures
non JSON.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

DEFAULT_ALLOWED_HOSTS = frozenset({"127.0.0.2", "localhost"})
DEFAULT_ALLOWED_ORIGINS = frozenset(
    {
        "http://127.0.0.2:8765",
        "http://localhost:8765",
        "http://127.0.0.2:5173",
        "http://localhost:5173",
    }
)

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


class CsrfProtector:
    """Émet et vérifie des jetons CSRF signés, sans session."""

    def __init__(self, secret: bytes | None = None, ttl_seconds: int = 3600) -> None:
        self._secret = secret or secrets.token_bytes(32)
        self._ttl = ttl_seconds

    def issue(self) -> str:
        timestamp = str(int(time.time()))
        nonce = secrets.token_urlsafe(16)
        payload = f"{timestamp}.{nonce}"
        signature = hmac.new(self._secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{payload}.{signature}"

    def verify(self, token: str | None) -> bool:
        if not token:
            return False
        parts = token.split(".")
        if len(parts) != 3:
            return False
        timestamp, nonce, signature = parts
        payload = f"{timestamp}.{nonce}"
        expected = hmac.new(self._secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        try:
            issued_at = int(timestamp)
        except ValueError:
            return False
        return 0 <= time.time() - issued_at <= self._ttl


def _error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"code": code, "message": message}, status_code=status_code)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Applique les règles de sécurité locales à chaque requête."""

    def __init__(
        self,
        app: object,
        *,
        allowed_hosts: frozenset[str] | set[str] | None = None,
        allowed_origins: frozenset[str] | set[str] | None = None,
        csrf: CsrfProtector | None = None,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.allowed_hosts = set(allowed_hosts or DEFAULT_ALLOWED_HOSTS)
        self.allowed_origins = set(allowed_origins or DEFAULT_ALLOWED_ORIGINS)
        self.csrf = csrf or CsrfProtector()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        host = (request.headers.get("host") or "").split(":", 1)[0].lower()
        if host not in self.allowed_hosts:
            return _error("invalid_host", f"hôte non autorisé : {host or '(vide)'}", 400)

        origin = request.headers.get("origin")
        if origin and origin not in self.allowed_origins:
            return _error("invalid_origin", "origine externe refusée", 403)

        referer = request.headers.get("referer")
        if referer:
            parsed = urlparse(referer)
            referer_origin = f"{parsed.scheme}://{parsed.netloc}"
            if referer_origin not in self.allowed_origins:
                return _error("invalid_referer", "référent externe refusé", 403)

        if request.method not in SAFE_METHODS:
            content_type = request.headers.get("content-type", "").lower()
            if not content_type.startswith("application/json"):
                return _error("invalid_content_type", "Content-Type application/json requis", 415)
            if not self.csrf.verify(request.headers.get("x-sdlc-csrf")):
                return _error("invalid_csrf", "jeton CSRF absent ou invalide", 403)

        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response
