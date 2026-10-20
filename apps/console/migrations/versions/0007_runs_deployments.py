"""Ajout des runs d'agents et des déploiements.

Revision ID: 0007_runs_deployments
Revises: 0006_merge_requests
Create Date: 2026-10-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_runs_deployments"
down_revision = "0006_merge_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=200), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("task_key", sa.String(length=100), nullable=True),
        sa.Column("agent_id", sa.String(length=100), nullable=True),
        sa.Column("primary_repository_id", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("cost_eur", sa.Float(), nullable=True),
        sa.Column("estimated_cost_eur", sa.Float(), nullable=True),
        sa.Column("budget_eur", sa.Float(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("process_group", sa.Integer(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("log_path", sa.String(length=1000), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("report_path", sa.String(length=1000), nullable=True),
        sa.Column("origin", sa.String(length=20), nullable=False, server_default="ingérée"),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["primary_repository_id"], ["repositories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "run_id", name="uq_task_runs_project_run"),
    )
    op.create_index("ix_task_runs_project_id", "task_runs", ["project_id"], unique=False)
    op.create_index("ix_task_runs_task_id", "task_runs", ["task_id"], unique=False)
    op.create_index("ix_task_runs_primary_repository_id", "task_runs", ["primary_repository_id"], unique=False)
    op.create_index("ix_task_runs_started_at", "task_runs", ["started_at"], unique=False)
    op.create_index("ix_task_runs_status", "task_runs", ["status"], unique=False)
    op.create_index("ix_task_runs_project_started", "task_runs", ["project_id", "started_at"], unique=False)

    op.create_table(
        "deployments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("deploy_id", sa.String(length=200), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=True),
        sa.Column("repository_label", sa.String(length=200), nullable=True),
        sa.Column("env", sa.String(length=50), nullable=False),
        sa.Column("version", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("by_person_id", sa.Integer(), nullable=True),
        sa.Column("by_label", sa.String(length=200), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("feature_id", sa.Integer(), nullable=True),
        sa.Column("feature_key", sa.String(length=100), nullable=True),
        sa.Column("is_rollback", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("rollback_of_version", sa.String(length=200), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["by_person_id"], ["persons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "deploy_id", name="uq_deployments_project_deploy"),
    )
    op.create_index("ix_deployments_project_id", "deployments", ["project_id"], unique=False)
    op.create_index("ix_deployments_repository_id", "deployments", ["repository_id"], unique=False)
    op.create_index("ix_deployments_by_person_id", "deployments", ["by_person_id"], unique=False)
    op.create_index(
        "ix_deployments_project_env_started",
        "deployments",
        ["project_id", "env", "started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_deployments_project_env_started", table_name="deployments")
    op.drop_index("ix_deployments_by_person_id", table_name="deployments")
    op.drop_index("ix_deployments_repository_id", table_name="deployments")
    op.drop_index("ix_deployments_project_id", table_name="deployments")
    op.drop_table("deployments")

    op.drop_index("ix_task_runs_project_started", table_name="task_runs")
    op.drop_index("ix_task_runs_status", table_name="task_runs")
    op.drop_index("ix_task_runs_started_at", table_name="task_runs")
    op.drop_index("ix_task_runs_primary_repository_id", table_name="task_runs")
    op.drop_index("ix_task_runs_task_id", table_name="task_runs")
    op.drop_index("ix_task_runs_project_id", table_name="task_runs")
    op.drop_table("task_runs")
