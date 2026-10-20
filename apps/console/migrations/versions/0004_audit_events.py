"""Ajout du journal d'audit chaîné par projet.

Revision ID: 0004_audit_events
Revises: 0003_persons
Create Date: 2026-10-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_audit_events"
down_revision = "0003_persons"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("actor_person_id", sa.Integer(), nullable=True),
        sa.Column("actor_label", sa.String(length=200), nullable=False, server_default="système"),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("object_type", sa.String(length=50), nullable=False),
        sa.Column("object_id", sa.String(length=100), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("prev_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_person_id"], ["persons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_project_id", "audit_events", ["project_id"], unique=False)
    op.create_index(
        "ix_audit_events_project_created",
        "audit_events",
        ["project_id", "created_at"],
        unique=False,
    )
    op.create_index("ix_audit_events_generation", "audit_events", ["generation"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_events_generation", table_name="audit_events")
    op.drop_index("ix_audit_events_project_created", table_name="audit_events")
    op.drop_index("ix_audit_events_project_id", table_name="audit_events")
    op.drop_table("audit_events")
