"""Ajout du timeout aux runs d'agents.

Revision ID: 0018_task_run_timeout
Revises: 0017_decisions
Create Date: 2026-10-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018_task_run_timeout"
down_revision = "0017_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("task_runs") as batch_op:
        batch_op.add_column(sa.Column("timeout_seconds", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("task_runs") as batch_op:
        batch_op.drop_column("timeout_seconds")
