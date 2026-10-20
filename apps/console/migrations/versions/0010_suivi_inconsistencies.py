"""Ajout des incohérences de suivi persistées.

Revision ID: 0010_suivi_inconsistencies
Revises: 0009_feature_phases
Create Date: 2026-10-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_suivi_inconsistencies"
down_revision = "0009_feature_phases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suivi_inconsistencies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("ingestion_run_id", sa.Integer(), nullable=True),
        sa.Column("feature_key", sa.String(length=100), nullable=False),
        sa.Column("task_key", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=60), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("state_status", sa.String(length=30), nullable=True),
        sa.Column("tasks_md_checked", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_suivi_inconsistencies_project_id",
        "suivi_inconsistencies",
        ["project_id"],
    )
    op.create_index(
        "ix_suivi_inconsistencies_ingestion_run_id",
        "suivi_inconsistencies",
        ["ingestion_run_id"],
    )
    op.create_index(
        "ix_suivi_inconsistencies_feature_key",
        "suivi_inconsistencies",
        ["feature_key"],
    )
    op.create_index(
        "ix_suivi_inconsistencies_project_feature",
        "suivi_inconsistencies",
        ["project_id", "feature_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_suivi_inconsistencies_project_feature", table_name="suivi_inconsistencies")
    op.drop_index("ix_suivi_inconsistencies_feature_key", table_name="suivi_inconsistencies")
    op.drop_index("ix_suivi_inconsistencies_ingestion_run_id", table_name="suivi_inconsistencies")
    op.drop_index("ix_suivi_inconsistencies_project_id", table_name="suivi_inconsistencies")
    op.drop_table("suivi_inconsistencies")
