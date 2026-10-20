"""Redaction des secrets dans les logs, exports et messages.

Les motifs couvrent les jetons GitHub/GitLab, les en-têtes Bearer, les paires
clé=valeur sensibles et les clés AWS. Le but est de ne jamais écrire un secret
en clair dans un journal ou un export.
"""

from __future__ import annotations

import re

RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "***"),
    (re.compile(r"glpat-[A-Za-z0-9_-]{20,}"), "***"),
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]+"), r"\1 ***"),
    (re.compile(r"(?i)\b(token|secret|password|api[_-]?key)\b\s*[:=]\s*[^\s,;]+"), r"\1=***"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "***"),
)


def redact(text: str) -> str:
    """Remplace les secrets connus par `***`."""
    result = text
    for pattern, replacement in RULES:
        result = pattern.sub(replacement, result)
    return result
