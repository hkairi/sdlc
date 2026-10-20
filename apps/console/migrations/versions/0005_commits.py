"""Ajout des commits et des exécutions d'ingestion.

Revision ID: 0005_commits
Revises: 0004_audit_events
Create Date: 2026-10-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_commits"
down_revision = "0004_audit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("sha", sa.String(length=64), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=True),
        sa.Column("author_name", sa.String(length=200), nullable=True),
        sa.Column("author_email", sa.String(length=320), nullable=True),
        sa.Column("authored_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("additions", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("deletions", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("files_changed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_merge", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("ai_assisted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("trailers_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("commit_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", "sha", name="uq_commits_repository_sha"),
    )
    op.create_index("ix_commits_repository_id", "commits", ["repository_id"], unique=False)
    op.create_index("ix_commits_person_id", "commits", ["person_id"], unique=False)
    op.create_index(
        "ix_commits_repository_committed",
        "commits",
        ["repository_id", "committed_at"],
        unique=False,
    )
    op.create_index("ix_commits_fingerprint", "commits", ["commit_fingerprint"], unique=False)

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="git"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("stats_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_runs_project_id", "ingestion_runs", ["project_id"], unique=False)
    op.create_index(
        "ix_ingestion_runs_repository_id",
        "ingestion_runs",
        ["repository_id"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_runs_project_started",
        "ingestion_runs",
        ["project_id", "started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_runs_project_started", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_repository_id", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_project_id", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")

    op.drop_index("ix_commits_fingerprint", table_name="commits")
    op.drop_index("ix_commits_repository_committed", table_name="commits")
    op.drop_index("ix_commits_person_id", table_name="commits")
    op.drop_index("ix_commits_repository_id", table_name="commits")
    op.drop_table("commits")
