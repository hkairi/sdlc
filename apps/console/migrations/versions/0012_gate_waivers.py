"""Ajout des dérogations de gates.

Revision ID: 0012_gate_waivers
Revises: 0011_gates
Create Date: 2026-10-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012_gate_waivers"
down_revision = "0011_gates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gate_waivers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("gate_key", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.String(length=200), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("owner", sa.String(length=200), nullable=False),
        sa.Column("approver", sa.String(length=200), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gate_waivers_project_id", "gate_waivers", ["project_id"])
    op.create_index("ix_gate_waivers_gate_key", "gate_waivers", ["gate_key"])
    op.create_index(
        "ix_gate_waivers_project_gate",
        "gate_waivers",
        ["project_id", "gate_key"],
    )
    op.create_index("ix_gate_waivers_expires", "gate_waivers", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_gate_waivers_expires", table_name="gate_waivers")
    op.drop_index("ix_gate_waivers_project_gate", table_name="gate_waivers")
    op.drop_index("ix_gate_waivers_gate_key", table_name="gate_waivers")
    op.drop_index("ix_gate_waivers_project_id", table_name="gate_waivers")
    op.drop_table("gate_waivers")
