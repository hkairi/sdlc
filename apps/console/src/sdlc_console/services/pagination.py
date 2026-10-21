"""Pagination commune des listes côté serveur."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_LIMIT = 50
MAX_LIMIT = 200



class PaginationError(ValueError):
    """Bornes de pagination invalides."""


@dataclass(frozen=True)
class PageParams:
    limit: int = DEFAULT_LIMIT
    offset: int = 0

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= MAX_LIMIT:
            raise PaginationError(
                f"limit doit être compris entre 1 et {MAX_LIMIT} (reçu : {self.limit})"
            )
        if self.offset < 0:
            raise PaginationError(
                f"offset doit être positif ou nul (reçu : {self.offset})"
            )


@dataclass(frozen=True)
class Page:
    items: list[object]
    total: int
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total

    @property
    def next_offset(self) -> int | None:
        return self.offset + len(self.items) if self.has_more else None

    def data(self, key: str) -> dict[str, object]:
        return {
            key: self.items,
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
            "has_more": self.has_more,
            "next_offset": self.next_offset,
        }


def paginate(items: list[Any], params: PageParams) -> Page:
    """Découpe une liste déjà filtrée et expose les métadonnées de page."""
    total = len(items)
    start = params.offset
    return Page(
        items=list(items[start : start + params.limit]),
        total=total,
        limit=params.limit,
        offset=params.offset,
    )
