"""Modèles SQLAlchemy de la Console SDLC.

L0 crée `projects` ; L1 ajoute `repositories` (multi-dépôts, dépôt principal,
retrait, déduplication).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base déclarative commune."""


def utc_now() -> datetime:
    """Horodatage UTC."""
    return datetime.now(UTC)


class Project(Base):
    """Projet suivi par la Console."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Europe/Paris")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    repositories: Mapped[list[Repository]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Project(id={self.id!r}, slug={self.slug!r})"


class Repository(Base):
    """Dépôt Git d'un projet (GitHub ou GitLab)."""

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    local_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(120), nullable=False, default="main")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dedup_group: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_mirror: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_fork: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    project: Mapped[Project] = relationship(back_populates="repositories")

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_repositories_project_name"),
        UniqueConstraint("project_id", "local_path", name="uq_repositories_project_path"),
        Index("uq_repositories_primary", "project_id", unique=True, sqlite_where=text("is_primary = 1")),
    )

    def __repr__(self) -> str:
        return f"Repository(id={self.id!r}, name={self.name!r}, provider={self.provider!r})"
