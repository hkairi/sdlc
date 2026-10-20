"""Ajout des phases de suivi sur les features.

Revision ID: 0009_feature_phases
Revises: 0008_features_tasks
Create Date: 2026-10-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_feature_phases"
down_revision = "0008_features_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("features") as batch_op:
        batch_op.add_column(
            sa.Column(
                "phases_json",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("features") as batch_op:
        batch_op.drop_column("phases_json")
