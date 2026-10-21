"""Redaction des secrets dans les logs, exports et messages.

Les motifs couvrent les jetons GitHub/GitLab, les en-têtes Bearer, les paires
clé=valeur sensibles et les clés AWS. Le but est de ne jamais écrire un secret
en clair dans un journal ou un export.
"""

from __future__ import annotations

import re
from pathlib import Path

RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "***"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "***"),
    (re.compile(r"glpat-[A-Za-z0-9_-]{20,}"), "***"),
    (re.compile(r"gloas-[A-Za-z0-9_-]{20,}"), "***"),
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]+"), r"\1 ***"),
    (re.compile(r"(?i)\b(token|secret|password|api[_-]?key)\b\s*[:=]\s*[^\s,;]+"), r"\1=***"),
    (re.compile(r"(?i)([\"']?(?:access[_-]?key|secret[_-]?key|private[_-]?key)[\"']?)\s*[:=]\s*([^,\s}]+)"), r"\1=***"),
    (re.compile(r"(?im)([\"']?prompt[\"']?\s*:\s*)\"(?:[^\"\\]|\\.)*\""), r'\1"***"'),
    (re.compile(r"(?im)([\"']?prompt[\"']?\s*:\s*)'(?:[^'\\]|\\.)*'"), r"\1'***'"),
    (re.compile(r"(?im)\bprompt\s*=\s*[^\s,;]+"), "prompt=***"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "***"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "***"),
)


def redact(text: str) -> str:
    """Remplace les secrets connus par `***`."""
    result = text
    for pattern, replacement in RULES:
        result = pattern.sub(replacement, result)
    return result


def redact_value(value: object) -> object:
    """Redacte récursivement les chaînes d'une structure JSON."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, dict):
        redacted: dict[object, object] = {}
        for key, item in value.items():
            lowered = str(key).casefold()
            sensitive_key = (
                lowered in {"token", "secret", "password", "prompt", "api_key", "apikey"}
                or lowered.endswith(("_token", "-token", "_secret", "_password", "_api_key"))
            )
            redacted[key] = "***" if sensitive_key else redact_value(item)
        return redacted
    return value


def redact_json_text(text: str) -> str:
    """Redacte un document JSON sérialisé sans changer sa validité."""
    return redact(text)


def redact_log_file(path: str | Path) -> bool:
    """Redacte un journal sur disque ; retourne vrai si son contenu a changé."""
    target = Path(path)
    try:
        original = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    cleaned = redact(original)
    if cleaned == original:
        return False
    temporary = target.with_name(f".{target.name}.redact.tmp")
    temporary.write_text(cleaned, encoding="utf-8")
    temporary.replace(target)
    return True
