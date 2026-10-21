"""Ajout des décisions humaines.

Revision ID: 0017_decisions
Revises: 0016_review_reports
Create Date: 2026-10-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_decisions"
down_revision = "0016_review_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=50), nullable=False),
        sa.Column("subject_id", sa.String(length=100), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("actor_person_id", sa.Integer(), nullable=True),
        sa.Column("actor_label", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("conditions_json", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["actor_person_id"], ["persons.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_decisions_project_id", "decisions", ["project_id"])
    op.create_index("ix_decisions_project_created", "decisions", ["project_id", "created_at"])
    op.create_index(
        "ix_decisions_subject",
        "decisions",
        ["project_id", "subject_type", "subject_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_decisions_subject", table_name="decisions")
    op.drop_index("ix_decisions_project_created", table_name="decisions")
    op.drop_index("ix_decisions_project_id", table_name="decisions")
    op.drop_table("decisions")
