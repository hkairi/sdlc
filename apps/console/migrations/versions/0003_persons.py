"""Ajout des personnes, identités et fusions auditées.

Revision ID: 0003_persons
Revises: 0002_repositories
Create Date: 2026-10-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_persons"
down_revision = "0002_repositories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=True),
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("superseded_by_person_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["superseded_by_person_id"], ["persons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_persons_project_id", "persons", ["project_id"], unique=False)
    op.create_index("ix_persons_project_name", "persons", ["project_id", "display_name"], unique=False)

    op.create_table(
        "person_identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_person_identities_project_id", "person_identities", ["project_id"], unique=False)
    op.create_index("ix_person_identities_person_id", "person_identities", ["person_id"], unique=False)
    op.create_index(
        "uq_person_identities_email",
        "person_identities",
        ["project_id", "email"],
        unique=True,
        sqlite_where=sa.text("email IS NOT NULL"),
    )
    op.create_index(
        "uq_person_identities_external",
        "person_identities",
        ["project_id", "provider", "external_id"],
        unique=True,
        sqlite_where=sa.text("external_id IS NOT NULL"),
    )

    op.create_table(
        "person_merges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("source_person_id", sa.Integer(), nullable=False),
        sa.Column("target_person_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("identity_ids_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("undone_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_person_merges_project_id", "person_merges", ["project_id"], unique=False)
    op.create_index("ix_person_merges_source", "person_merges", ["source_person_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_person_merges_source", table_name="person_merges")
    op.drop_index("ix_person_merges_project_id", table_name="person_merges")
    op.drop_table("person_merges")

    op.drop_index("uq_person_identities_external", table_name="person_identities")
    op.drop_index("uq_person_identities_email", table_name="person_identities")
    op.drop_index("ix_person_identities_person_id", table_name="person_identities")
    op.drop_index("ix_person_identities_project_id", table_name="person_identities")
    op.drop_table("person_identities")

    op.drop_index("ix_persons_project_name", table_name="persons")
    op.drop_index("ix_persons_project_id", table_name="persons")
    op.drop_table("persons")
