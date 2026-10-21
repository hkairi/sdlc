"""Ajout des rapports de revue et fiches de décision.

Revision ID: 0016_review_reports
Revises: 0015_review_packages
Create Date: 2026-10-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016_review_reports"
down_revision = "0015_review_packages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("package_id", sa.Integer(), nullable=False),
        sa.Column("task_key", sa.String(length=100), nullable=False),
        sa.Column("verdict", sa.String(length=30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("report_path", sa.String(length=1000), nullable=False),
        sa.Column("decision_path", sa.String(length=1000), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["package_id"], ["review_packages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_reports_project_id", "review_reports", ["project_id"])
    op.create_index("ix_review_reports_package_id", "review_reports", ["package_id"])
    op.create_index("ix_review_reports_task_key", "review_reports", ["task_key"])
    op.create_index(
        "ix_review_reports_project_created",
        "review_reports",
        ["project_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_review_reports_project_created", table_name="review_reports")
    op.drop_index("ix_review_reports_task_key", table_name="review_reports")
    op.drop_index("ix_review_reports_package_id", table_name="review_reports")
    op.drop_index("ix_review_reports_project_id", table_name="review_reports")
    op.drop_table("review_reports")
