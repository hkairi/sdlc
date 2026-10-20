"""Transport HTTP, cache ETag et reprise avec backoff pour les fournisseurs."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Protocol


class ProviderError(RuntimeError):
    """Erreur de collecte auprès d'un fournisseur."""


class ProviderAuthError(ProviderError):
    """Jeton absent, invalide ou droits insuffisants."""


class ProviderQuotaError(ProviderError):
    """Quota ou limite de débit épuisé après reprises."""


class ProviderUnavailableError(ProviderError):
    """Fournisseur injoignable (réseau, DNS, timeout)."""


def default_cache_path() -> Path:
    """Chemin du cache ETag, surchargeable par `SDLC_PROVIDER_CACHE`."""
    return Path(os.environ.get("SDLC_PROVIDER_CACHE", "data/provider-cache.json"))


@dataclass(frozen=True)
class HttpResponse:
    """Réponse HTTP minimale et indépendante du client."""

    status: int
    headers: Mapping[str, str]
    json: Any | None = None
    text: str = ""


class HttpClient(Protocol):
    """Client HTTP injectable pour les tests hors réseau."""

    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse: ...


def header_value(headers: Mapping[str, str], name: str) -> str | None:
    """Lit un en-tête sans dépendre de la casse."""
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return None


def _decode_json(body: bytes) -> Any | None:
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


class UrllibHttpClient:
    """Client HTTP standard, sans dépendance externe."""

    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        request = urllib.request.Request(url, headers=dict(headers), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                body = response.read()
                return HttpResponse(
                    status=int(response.status),
                    headers={key.lower(): value for key, value in response.headers.items()},
                    json=_decode_json(body),
                    text=body.decode("utf-8", errors="replace"),
                )
        except urllib.error.HTTPError as exc:
            body = exc.read()
            return HttpResponse(
                status=int(exc.code),
                headers={key.lower(): value for key, value in exc.headers.items()},
                json=_decode_json(body),
                text=body.decode("utf-8", errors="replace"),
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderUnavailableError(f"fournisseur injoignable : {exc}") from exc


def _is_rate_limit(response: HttpResponse) -> bool:
    if header_value(response.headers, "x-ratelimit-remaining") == "0":
        return True
    text = response.text.lower()
    return "rate limit" in text or "quota" in text


def _retry_delay(headers: Mapping[str, str], attempt: int, now: float) -> float:
    retry_after = header_value(headers, "retry-after")
    if retry_after:
        try:
            return max(0.0, min(float(retry_after), 60.0))
        except ValueError:
            try:
                when = parsedate_to_datetime(retry_after)
                if when.tzinfo is None:
                    when = when.replace(tzinfo=UTC)
                return max(0.0, min((when.timestamp() - now), 60.0))
            except (TypeError, ValueError):
                pass
    reset = header_value(headers, "x-ratelimit-reset")
    if reset:
        try:
            return max(0.0, min(float(int(reset) - int(now)) + 1.0, 60.0))
        except ValueError:
            pass
    return float(min(2**attempt, 60))


def retry_get(
    client: HttpClient,
    url: str,
    headers: Mapping[str, str],
    *,
    attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.time,
) -> HttpResponse:
    """Exécute un GET avec reprise sur quota et erreurs serveur."""
    last: HttpResponse | None = None
    for attempt in range(attempts):
        response = client.get(url, headers)
        last = response
        if response.status < 400 or response.status == 304:
            return response
        if response.status == 401:
            raise ProviderAuthError("jeton fournisseur absent ou invalide")
        rate_limited = response.status == 429 or (
            response.status == 403 and _is_rate_limit(response)
        )
        if rate_limited or response.status >= 500:
            if attempt + 1 >= attempts:
                if rate_limited:
                    raise ProviderQuotaError("quota fournisseur épuisé après reprises")
                raise ProviderError(f"fournisseur indisponible (HTTP {response.status})")
            sleep(_retry_delay(response.headers, attempt, now()))
            continue
        if response.status == 403:
            raise ProviderAuthError("droits insuffisants pour le fournisseur")
        raise ProviderError(f"réponse fournisseur inattendue (HTTP {response.status})")
    raise ProviderError(f"échec de la requête fournisseur (HTTP {last.status if last else 'inconnu'})")


class JsonETagCache:
    """Cache JSON persistant des réponses fournisseur indexées par URL."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._entries: dict[str, dict[str, Any]] = {}
        if path is not None and path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                entries = raw.get("entries") if isinstance(raw, dict) else None
                if isinstance(entries, dict):
                    self._entries = {
                        str(key): value
                        for key, value in entries.items()
                        if isinstance(value, dict)
                    }
            except (OSError, json.JSONDecodeError):
                self._entries = {}

    def get(self, url: str) -> tuple[str | None, Any | None]:
        entry = self._entries.get(url)
        if not entry:
            return None, None
        etag = entry.get("etag")
        return (etag if isinstance(etag, str) and etag else None, entry.get("payload"))

    def set(self, url: str, etag: str, payload: Any) -> None:
        self._entries[url] = {"etag": etag, "payload": payload}
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps({"entries": self._entries}, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(self.path)


def cached_json_get(
    client: HttpClient,
    url: str,
    headers: Mapping[str, str],
    cache: JsonETagCache,
    *,
    attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.time,
) -> Any | None:
    """GET JSON avec ETag et cache ; une réponse 304 réutilise le cache."""
    etag, payload = cache.get(url)
    request_headers = dict(headers)
    if etag:
        request_headers["If-None-Match"] = etag
    response = retry_get(
        client,
        url,
        request_headers,
        attempts=attempts,
        sleep=sleep,
        now=now,
    )
    if response.status == 304:
        if payload is None:
            raise ProviderError("réponse 304 sans entrée de cache")
        return payload
    if response.status >= 300:
        raise ProviderError(f"réponse fournisseur inattendue (HTTP {response.status})")
    new_etag = header_value(response.headers, "etag")
    if new_etag:
        cache.set(url, new_etag, response.json)
    return response.json
