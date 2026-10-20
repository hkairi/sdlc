"""Création initiale de la table projects.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Europe/Paris"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_slug", "projects", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_projects_slug", table_name="projects")
    op.drop_table("projects")
