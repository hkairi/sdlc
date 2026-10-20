"""Ajout de la table repositories (multi-dépôts).

Revision ID: 0002_repositories
Revises: 0001_initial
Create Date: 2026-10-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_repositories"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repositories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("local_path", sa.String(length=1000), nullable=False),
        sa.Column("default_branch", sa.String(length=120), nullable=False, server_default="main"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("dedup_group", sa.String(length=120), nullable=True),
        sa.Column("is_mirror", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_fork", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uq_repositories_project_name"),
        sa.UniqueConstraint("project_id", "local_path", name="uq_repositories_project_path"),
    )
    op.create_index("ix_repositories_project_id", "repositories", ["project_id"], unique=False)
    op.create_index(
        "uq_repositories_primary",
        "repositories",
        ["project_id"],
        unique=True,
        sqlite_where=sa.text("is_primary = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_repositories_primary", table_name="repositories")
    op.drop_index("ix_repositories_project_id", table_name="repositories")
    op.drop_table("repositories")
