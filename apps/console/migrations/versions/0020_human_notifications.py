"""Ajout des notifications humaines et escalades."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020_human_notifications"
down_revision = "0019_run_failure_reason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "human_notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("subject_type", sa.String(length=50), nullable=False),
        sa.Column("subject_id", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_human_notifications_project_id", "human_notifications", ["project_id"])
    op.create_index(
        "ix_human_notifications_project_created",
        "human_notifications",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_human_notifications_subject",
        "human_notifications",
        ["project_id", "subject_type", "subject_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_human_notifications_subject", table_name="human_notifications")
    op.drop_index("ix_human_notifications_project_created", table_name="human_notifications")
    op.drop_index("ix_human_notifications_project_id", table_name="human_notifications")
    op.drop_table("human_notifications")
