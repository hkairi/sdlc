"""Ajout des définitions, runs et findings de gates.

Revision ID: 0011_gates
Revises: 0010_suivi_inconsistencies
Create Date: 2026-10-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_gates"
down_revision = "0010_suivi_inconsistencies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("blocking", sa.Boolean(), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("config_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "key", name="uq_gates_project_key"),
    )
    op.create_index("ix_gates_project_id", "gates", ["project_id"])

    op.create_table(
        "gate_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("gate_id", sa.Integer(), nullable=False),
        sa.Column("gate_key", sa.String(length=100), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=True),
        sa.Column("feature_id", sa.Integer(), nullable=True),
        sa.Column("verdict", sa.String(length=30), nullable=False),
        sa.Column("blocks", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("report_path", sa.String(length=1000), nullable=False),
        sa.Column("config_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("controls_json", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("findings_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["feature_id"], ["features.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["gate_id"], ["gates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gate_runs_project_id", "gate_runs", ["project_id"])
    op.create_index("ix_gate_runs_gate_id", "gate_runs", ["gate_id"])
    op.create_index("ix_gate_runs_gate_key", "gate_runs", ["gate_key"])
    op.create_index("ix_gate_runs_repository_id", "gate_runs", ["repository_id"])
    op.create_index("ix_gate_runs_feature_id", "gate_runs", ["feature_id"])
    op.create_index("ix_gate_runs_verdict", "gate_runs", ["verdict"])
    op.create_index("ix_gate_runs_project_created", "gate_runs", ["project_id", "created_at"])
    op.create_index("ix_gate_runs_gate_created", "gate_runs", ["gate_id", "created_at"])

    op.create_table(
        "gate_findings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("gate_run_id", sa.Integer(), nullable=False),
        sa.Column("control_key", sa.String(length=100), nullable=False),
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=True),
        sa.Column("line", sa.Integer(), nullable=True),
        sa.Column("evidence_path", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(["gate_run_id"], ["gate_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gate_findings_gate_run_id", "gate_findings", ["gate_run_id"])


def downgrade() -> None:
    op.drop_index("ix_gate_findings_gate_run_id", table_name="gate_findings")
    op.drop_table("gate_findings")
    op.drop_index("ix_gate_runs_gate_created", table_name="gate_runs")
    op.drop_index("ix_gate_runs_project_created", table_name="gate_runs")
    op.drop_index("ix_gate_runs_verdict", table_name="gate_runs")
    op.drop_index("ix_gate_runs_feature_id", table_name="gate_runs")
    op.drop_index("ix_gate_runs_repository_id", table_name="gate_runs")
    op.drop_index("ix_gate_runs_gate_key", table_name="gate_runs")
    op.drop_index("ix_gate_runs_gate_id", table_name="gate_runs")
    op.drop_index("ix_gate_runs_project_id", table_name="gate_runs")
    op.drop_table("gate_runs")
    op.drop_index("ix_gates_project_id", table_name="gates")
    op.drop_table("gates")
