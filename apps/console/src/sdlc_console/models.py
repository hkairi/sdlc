"""Modèles SQLAlchemy de la Console SDLC.

L0 crée `projects` ; L1 ajoute `repositories` (multi-dépôts, dépôt principal,
retrait, déduplication).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
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
    persons: Mapped[list[Person]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    ingestion_runs: Mapped[list[IngestionRun]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    task_runs: Mapped[list[TaskRun]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    deployments: Mapped[list[Deployment]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    features: Mapped[list[Feature]] = relationship(
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
    commits: Mapped[list[Commit]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    merge_requests: Mapped[list[MergeRequest]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    ingestion_runs: Mapped[list[IngestionRun]] = relationship(back_populates="repository")
    task_runs: Mapped[list[TaskRun]] = relationship(back_populates="primary_repository")
    deployments: Mapped[list[Deployment]] = relationship(back_populates="repository")
    feature_links: Mapped[list[FeatureRepository]] = relationship(back_populates="repository")
    task_links: Mapped[list[TaskRepository]] = relationship(back_populates="repository")

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_repositories_project_name"),
        UniqueConstraint("project_id", "local_path", name="uq_repositories_project_path"),
        Index("uq_repositories_primary", "project_id", unique=True, sqlite_where=text("is_primary = 1")),
    )

    def __repr__(self) -> str:
        return f"Repository(id={self.id!r}, name={self.name!r}, provider={self.provider!r})"


class Person(Base):
    """Personne canonique d'un projet, indépendante du dépôt d'origine."""

    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    superseded_by_person_id: Mapped[int | None] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    project: Mapped[Project] = relationship(back_populates="persons")
    identities: Mapped[list[PersonIdentity]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
    )
    superseded_by: Mapped[Person | None] = relationship(
        "Person",
        remote_side=[id],
        back_populates="supersedes",
    )
    supersedes: Mapped[list[Person]] = relationship("Person", back_populates="superseded_by")
    commits: Mapped[list[Commit]] = relationship(back_populates="person")
    authored_merge_requests: Mapped[list[MergeRequest]] = relationship(back_populates="author")
    reviews: Mapped[list[Review]] = relationship(back_populates="reviewer")
    approvals: Mapped[list[Approval]] = relationship(back_populates="actor")
    deployments: Mapped[list[Deployment]] = relationship(back_populates="by_person")

    __table_args__ = (Index("ix_persons_project_name", "project_id", "display_name"),)

    def __repr__(self) -> str:
        return f"Person(id={self.id!r}, display_name={self.display_name!r})"


class PersonIdentity(Base):
    """Identité rattachée à une personne : email ou compte GitHub/GitLab."""

    __tablename__ = "person_identities"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    person_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    person: Mapped[Person] = relationship(back_populates="identities")

    __table_args__ = (
        Index(
            "uq_person_identities_email",
            "project_id",
            "email",
            unique=True,
            sqlite_where=text("email IS NOT NULL"),
        ),
        Index(
            "uq_person_identities_external",
            "project_id",
            "provider",
            "external_id",
            unique=True,
            sqlite_where=text("external_id IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"PersonIdentity(id={self.id!r}, provider={self.provider!r}, email={self.email!r})"


class PersonMerge(Base):
    """Journal des fusions de personnes, réversible et auditable."""

    __tablename__ = "person_merges"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_person_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_person_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    identity_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source_person: Mapped[Person] = relationship("Person", foreign_keys=[source_person_id])
    target_person: Mapped[Person] = relationship("Person", foreign_keys=[target_person_id])

    def __repr__(self) -> str:
        return f"PersonMerge(id={self.id!r}, source={self.source_person_id!r}, target={self.target_person_id!r})"


class AuditEvent(Base):
    """Événement d'audit chaîné par projet (conservé hors purge automatique)."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    actor_person_id: Mapped[int | None] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_label: Mapped[str] = mapped_column(String(200), nullable=False, default="système")
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    object_type: Mapped[str] = mapped_column(String(50), nullable=False)
    object_id: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("ix_audit_events_project_created", "project_id", "created_at"),
        Index("ix_audit_events_generation", "generation"),
    )

    def __repr__(self) -> str:
        return f"AuditEvent(id={self.id!r}, action={self.action!r}, object_id={self.object_id!r})"


class Commit(Base):
    """Commit Git ingéré, rattaché à un dépôt et à une personne canonique."""

    __tablename__ = "commits"

    id: Mapped[int] = mapped_column(primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sha: Mapped[str] = mapped_column(String(64), nullable=False)
    person_id: Mapped[int | None] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    author_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    author_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    authored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    additions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deletions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    files_changed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    files_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_merge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_bot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_assisted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trailers_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    commit_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    repository: Mapped[Repository] = relationship(back_populates="commits")
    person: Mapped[Person | None] = relationship(back_populates="commits")

    __table_args__ = (
        UniqueConstraint("repository_id", "sha", name="uq_commits_repository_sha"),
        Index("ix_commits_repository_committed", "repository_id", "committed_at"),
        Index("ix_commits_fingerprint", "commit_fingerprint"),
    )

    def __repr__(self) -> str:
        return f"Commit(id={self.id!r}, sha={self.sha!r}, repository_id={self.repository_id!r})"


class MergeRequest(Base):
    """Pull request GitHub ou merge request GitLab normalisée."""

    __tablename__ = "merge_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    author_person_id: Mapped[int | None] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    target_branch: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_branch: Mapped[str | None] = mapped_column(String(200), nullable=True)
    merge_strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    additions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deletions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    repository: Mapped[Repository] = relationship(back_populates="merge_requests")
    author: Mapped[Person | None] = relationship(back_populates="authored_merge_requests")
    reviews: Mapped[list[Review]] = relationship(
        back_populates="mr",
        cascade="all, delete-orphan",
    )
    approvals: Mapped[list[Approval]] = relationship(
        back_populates="mr",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("repository_id", "number", name="uq_merge_requests_repository_number"),
        Index("ix_merge_requests_repository_state", "repository_id", "state"),
        Index("ix_merge_requests_repository_merged", "repository_id", "merged_at"),
    )

    def __repr__(self) -> str:
        return f"MergeRequest(id={self.id!r}, number={self.number!r}, state={self.state!r})"


class Review(Base):
    """Revue d'une MR, humaine ou agentique."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    mr_id: Mapped[int] = mapped_column(
        ForeignKey("merge_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_person_id: Mapped[int | None] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewer_agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_agent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    independence: Mapped[str | None] = mapped_column(String(30), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    mr: Mapped[MergeRequest] = relationship(back_populates="reviews")
    reviewer: Mapped[Person | None] = relationship(back_populates="reviews")

    __table_args__ = (
        Index(
            "uq_reviews_mr_external",
            "mr_id",
            "external_id",
            unique=True,
            sqlite_where=text("external_id IS NOT NULL"),
        ),
        Index("ix_reviews_submitted_at", "submitted_at"),
    )

    def __repr__(self) -> str:
        return f"Review(id={self.id!r}, state={self.state!r}, is_agent={self.is_agent!r})"


class Approval(Base):
    """Approbation formelle d'une MR."""

    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    mr_id: Mapped[int] = mapped_column(
        ForeignKey("merge_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_person_id: Mapped[int | None] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False, default="human")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    mr: Mapped[MergeRequest] = relationship(back_populates="approvals")
    actor: Mapped[Person | None] = relationship(back_populates="approvals")

    __table_args__ = (
        Index(
            "uq_approvals_mr_external",
            "mr_id",
            "external_id",
            unique=True,
            sqlite_where=text("external_id IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"Approval(id={self.id!r}, actor_type={self.actor_type!r})"


class TaskRun(Base):
    """Run d'agent ingéré ou lancé depuis l'interface."""

    __tablename__ = "task_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[str] = mapped_column(String(200), nullable=False)
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    task_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    primary_repository_id: Mapped[int | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    cost_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_cost_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    budget_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    process_group: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    log_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failure_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    report_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    origin: Mapped[str] = mapped_column(String(20), nullable=False, default="ingérée")
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    project: Mapped[Project] = relationship(back_populates="task_runs")
    primary_repository: Mapped[Repository | None] = relationship(back_populates="task_runs")

    __table_args__ = (
        UniqueConstraint("project_id", "run_id", name="uq_task_runs_project_run"),
        Index("ix_task_runs_project_started", "project_id", "started_at"),
    )

    def __repr__(self) -> str:
        return f"TaskRun(id={self.id!r}, run_id={self.run_id!r}, status={self.status!r})"


class Deployment(Base):
    """Déploiement ingéré depuis `deploys.jsonl`."""

    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deploy_id: Mapped[str] = mapped_column(String(200), nullable=False)
    repository_id: Mapped[int | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    repository_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    env: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    by_person_id: Mapped[int | None] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    by_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    feature_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feature_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_rollback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rollback_of_version: Mapped[str | None] = mapped_column(String(200), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    project: Mapped[Project] = relationship(back_populates="deployments")
    repository: Mapped[Repository | None] = relationship(back_populates="deployments")
    by_person: Mapped[Person | None] = relationship(back_populates="deployments")

    __table_args__ = (
        UniqueConstraint("project_id", "deploy_id", name="uq_deployments_project_deploy"),
        Index("ix_deployments_project_env_started", "project_id", "env", "started_at"),
    )

    def __repr__(self) -> str:
        return f"Deployment(id={self.id!r}, env={self.env!r}, status={self.status!r})"


class Feature(Base):
    """Feature suivie, éventuellement répartie sur plusieurs dépôts."""

    __tablename__ = "features"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    primary_repository_id: Mapped[int | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="todo")
    owner_person_id: Mapped[int | None] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    spec_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    change: Mapped[str | None] = mapped_column(String(100), nullable=True)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    tasks_file: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    sources_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    phases_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    project: Mapped[Project] = relationship(back_populates="features")
    primary_repository: Mapped[Repository | None] = relationship(
        "Repository",
        foreign_keys=[primary_repository_id],
    )
    owner: Mapped[Person | None] = relationship("Person", foreign_keys=[owner_person_id])
    tasks: Mapped[list[Task]] = relationship(
        back_populates="feature",
        cascade="all, delete-orphan",
    )
    repository_links: Mapped[list[FeatureRepository]] = relationship(
        back_populates="feature",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("project_id", "key", name="uq_features_project_key"),
        Index("ix_features_project_status", "project_id", "status"),
    )

    @property
    def repositories(self) -> list[Repository]:
        """Dépôts couverts par la feature, via la table de liaison."""
        return [link.repository for link in self.repository_links]

    def __repr__(self) -> str:
        return f"Feature(id={self.id!r}, key={self.key!r}, status={self.status!r})"


class Task(Base):
    """Tâche d'une feature, éventuellement répartie sur plusieurs dépôts."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    feature_id: Mapped[int] = mapped_column(
        ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    primary_repository_id: Mapped[int | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    lot: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="todo")
    owner_person_id: Mapped[int | None] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewer_person_id: Mapped[int | None] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    executor_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewer_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    files_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    acceptance: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    feature: Mapped[Feature] = relationship(back_populates="tasks")
    primary_repository: Mapped[Repository | None] = relationship(
        "Repository",
        foreign_keys=[primary_repository_id],
    )
    owner: Mapped[Person | None] = relationship("Person", foreign_keys=[owner_person_id])
    reviewer: Mapped[Person | None] = relationship("Person", foreign_keys=[reviewer_person_id])
    repository_links: Mapped[list[TaskRepository]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("feature_id", "key", name="uq_tasks_feature_key"),
        Index("ix_tasks_feature_status", "feature_id", "status"),
    )

    @property
    def repositories(self) -> list[Repository]:
        """Dépôts touchés par la tâche, via la table de liaison."""
        return [link.repository for link in self.repository_links]

    def __repr__(self) -> str:
        return f"Task(id={self.id!r}, key={self.key!r}, status={self.status!r})"


class FeatureRepository(Base):
    """Liaison feature → dépôt."""

    __tablename__ = "feature_repositories"

    feature_id: Mapped[int] = mapped_column(
        ForeignKey("features.id", ondelete="CASCADE"),
        primary_key=True,
    )
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        primary_key=True,
    )

    feature: Mapped[Feature] = relationship(back_populates="repository_links")
    repository: Mapped[Repository] = relationship(back_populates="feature_links")


class TaskRepository(Base):
    """Liaison tâche → dépôt, avec le dépôt principal de la tâche."""

    __tablename__ = "task_repositories"

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    task: Mapped[Task] = relationship(back_populates="repository_links")
    repository: Mapped[Repository] = relationship(back_populates="task_links")

    __table_args__ = (
        Index(
            "uq_task_repositories_primary",
            "task_id",
            unique=True,
            sqlite_where=text("is_primary = 1"),
        ),
    )


class IngestionRun(Base):
    """Exécution d'ingestion, par dépôt, avec statistiques et erreur éventuelle."""

    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[int | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="git")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    stats_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship(back_populates="ingestion_runs")
    repository: Mapped[Repository | None] = relationship(back_populates="ingestion_runs")

    __table_args__ = (
        Index("ix_ingestion_runs_project_started", "project_id", "started_at"),
    )

    def __repr__(self) -> str:
        return f"IngestionRun(id={self.id!r}, status={self.status!r}, repository_id={self.repository_id!r})"


class Gate(Base):
    """Définition d'un gate pour un projet."""

    __tablename__ = "gates"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    config_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    __table_args__ = (
        UniqueConstraint("project_id", "key", name="uq_gates_project_key"),
    )

    def __repr__(self) -> str:
        return f"Gate(id={self.id!r}, key={self.key!r})"


class GateRun(Base):
    """Exécution d'un gate, avec verdict et preuves liées."""

    __tablename__ = "gate_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    gate_id: Mapped[int] = mapped_column(
        ForeignKey("gates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    gate_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    repository_id: Mapped[int | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    feature_id: Mapped[int | None] = mapped_column(
        ForeignKey("features.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    verdict: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    blocks: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    report_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    config_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    controls_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    findings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    gate: Mapped[Gate] = relationship()
    findings: Mapped[list[GateFinding]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_gate_runs_project_created", "project_id", "created_at"),
        Index("ix_gate_runs_gate_created", "gate_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"GateRun(id={self.id!r}, gate={self.gate_key!r}, verdict={self.verdict!r})"


class GateFinding(Base):
    """Finding rattaché à un run de gate."""

    __tablename__ = "gate_findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    gate_run_id: Mapped[int] = mapped_column(
        ForeignKey("gate_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    control_key: Mapped[str] = mapped_column(String(100), nullable=False)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    run: Mapped[GateRun] = relationship(back_populates="findings")

    def __repr__(self) -> str:
        return f"GateFinding(id={self.id!r}, key={self.key!r}, severity={self.severity!r})"


class ReviewPackage(Base):
    """Paquet aveugle de revue, traçable par empreinte."""

    __tablename__ = "review_packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    feature_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    report_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    files_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    __table_args__ = (
        Index("ix_review_packages_project_created", "project_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"ReviewPackage(id={self.id!r}, task={self.task_key!r})"


class Decision(Base):
    """Décision humaine, tracée et auditée."""

    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(100), nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_person_id: Mapped[int | None] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_label: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    conditions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_decisions_project_created", "project_id", "created_at"),
        Index("ix_decisions_subject", "project_id", "subject_type", "subject_id"),
    )

    def __repr__(self) -> str:
        return f"Decision(id={self.id!r}, subject={self.subject_type!r}, decision={self.decision!r})"


class HumanNotification(Base):
    """Notification destinée à l'humain, notamment après escalade."""

    __tablename__ = "human_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    acknowledged_by: Mapped[str | None] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        Index("ix_human_notifications_project_created", "project_id", "created_at"),
        Index("ix_human_notifications_subject", "project_id", "subject_type", "subject_id"),
    )

    def __repr__(self) -> str:
        return f"HumanNotification(id={self.id!r}, kind={self.kind!r})"


class ReviewReport(Base):
    """Rapport structuré et fiche de décision d'une revue."""

    __tablename__ = "review_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    package_id: Mapped[int] = mapped_column(
        ForeignKey("review_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    verdict: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    report_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    decision_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    __table_args__ = (
        Index("ix_review_reports_project_created", "project_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"ReviewReport(id={self.id!r}, task={self.task_key!r}, verdict={self.verdict!r})"


class ProcessOverride(Base):
    """Surcharge manuelle datée et auditée du profil de processus."""

    __tablename__ = "process_overrides"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[int | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    profile_key: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_label: Mapped[str] = mapped_column(String(200), nullable=False, default="orchestrateur local")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    __table_args__ = (
        Index("ix_process_overrides_project_repo", "project_id", "repository_id"),
    )

    def __repr__(self) -> str:
        return (
            f"ProcessOverride(id={self.id!r}, profile={self.profile_key!r}, "
            f"repository={self.repository_id!r})"
        )


class GateWaiverRecord(Base):
    """Dérogation motivée et datée sur un gate, un run ou un finding."""

    __tablename__ = "gate_waivers"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    gate_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(200), nullable=False)
    approver: Mapped[str] = mapped_column(String(200), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_gate_waivers_project_gate", "project_id", "gate_key"),
        Index("ix_gate_waivers_expires", "expires_at"),
    )

    def __repr__(self) -> str:
        return (
            f"GateWaiverRecord(id={self.id!r}, gate={self.gate_key!r}, "
            f"target={self.target_type!r})"
        )


class SuiviInconsistency(Base):
    """Incohérence durable entre `tasks.md` et `state.json`."""

    __tablename__ = "suivi_inconsistencies"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ingestion_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    feature_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    task_key: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(60), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    state_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tasks_md_checked: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    __table_args__ = (
        Index("ix_suivi_inconsistencies_project_feature", "project_id", "feature_key"),
    )

    def __repr__(self) -> str:
        return (
            f"SuiviInconsistency(id={self.id!r}, feature={self.feature_key!r}, "
            f"task={self.task_key!r}, kind={self.kind!r})"
        )
