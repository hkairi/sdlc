"""Ajout des paquets de revue aveugle.

Revision ID: 0015_review_packages
Revises: 0014_process_overrides
Create Date: 2026-10-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015_review_packages"
down_revision = "0014_process_overrides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_packages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("task_key", sa.String(length=100), nullable=False),
        sa.Column("feature_key", sa.String(length=100), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("report_path", sa.String(length=1000), nullable=False),
        sa.Column("files_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_packages_project_id", "review_packages", ["project_id"])
    op.create_index("ix_review_packages_task_key", "review_packages", ["task_key"])
    op.create_index("ix_review_packages_fingerprint", "review_packages", ["fingerprint"])
    op.create_index(
        "ix_review_packages_project_created",
        "review_packages",
        ["project_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_review_packages_project_created", table_name="review_packages")
    op.drop_index("ix_review_packages_fingerprint", table_name="review_packages")
    op.drop_index("ix_review_packages_task_key", table_name="review_packages")
    op.drop_index("ix_review_packages_project_id", table_name="review_packages")
    op.drop_table("review_packages")
