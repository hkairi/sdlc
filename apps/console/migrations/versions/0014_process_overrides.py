"""Ajout des surcharges de profil de processus.

Revision ID: 0014_process_overrides
Revises: 0013_commit_files
Create Date: 2026-10-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_process_overrides"
down_revision = "0013_commit_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "process_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=True),
        sa.Column("profile_key", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_label", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_process_overrides_project_id", "process_overrides", ["project_id"])
    op.create_index("ix_process_overrides_repository_id", "process_overrides", ["repository_id"])
    op.create_index(
        "ix_process_overrides_project_repo",
        "process_overrides",
        ["project_id", "repository_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_process_overrides_project_repo", table_name="process_overrides")
    op.drop_index("ix_process_overrides_repository_id", table_name="process_overrides")
    op.drop_index("ix_process_overrides_project_id", table_name="process_overrides")
    op.drop_table("process_overrides")
