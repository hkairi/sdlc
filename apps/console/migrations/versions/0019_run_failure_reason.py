"""Ajout du motif d'échec des runs.

Revision ID: 0019_run_failure_reason
Revises: 0018_task_run_timeout
Create Date: 2026-10-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019_run_failure_reason"
down_revision = "0018_task_run_timeout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("task_runs") as batch_op:
        batch_op.add_column(sa.Column("failure_reason", sa.String(length=100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("task_runs") as batch_op:
        batch_op.drop_column("failure_reason")
