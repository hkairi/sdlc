"""Ajout de la liste des fichiers touchés par commit.

Revision ID: 0013_commit_files
Revises: 0012_gate_waivers
Create Date: 2026-10-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_commit_files"
down_revision = "0012_gate_waivers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("commits") as batch_op:
        batch_op.add_column(
            sa.Column(
                "files_json",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("commits") as batch_op:
        batch_op.drop_column("files_json")
