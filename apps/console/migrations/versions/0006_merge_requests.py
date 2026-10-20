"""Ajout des MR, revues et approbations normalisées.

Revision ID: 0006_merge_requests
Revises: 0005_commits
Create Date: 2026-10-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_merge_requests"
down_revision = "0005_commits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merge_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("author_person_id", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("target_branch", sa.String(length=200), nullable=True),
        sa.Column("source_branch", sa.String(length=200), nullable=True),
        sa.Column("merge_strategy", sa.String(length=50), nullable=True),
        sa.Column("additions", sa.Integer(), nullable=True),
        sa.Column("deletions", sa.Integer(), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_person_id"], ["persons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", "number", name="uq_merge_requests_repository_number"),
    )
    op.create_index("ix_merge_requests_repository_id", "merge_requests", ["repository_id"], unique=False)
    op.create_index("ix_merge_requests_author_person_id", "merge_requests", ["author_person_id"], unique=False)
    op.create_index(
        "ix_merge_requests_repository_state",
        "merge_requests",
        ["repository_id", "state"],
        unique=False,
    )
    op.create_index(
        "ix_merge_requests_repository_merged",
        "merge_requests",
        ["repository_id", "merged_at"],
        unique=False,
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mr_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_person_id", sa.Integer(), nullable=True),
        sa.Column("reviewer_agent_id", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_agent", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("independence", sa.String(length=30), nullable=True),
        sa.Column("external_id", sa.String(length=200), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["mr_id"], ["merge_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_person_id"], ["persons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reviews_mr_id", "reviews", ["mr_id"], unique=False)
    op.create_index("ix_reviews_reviewer_person_id", "reviews", ["reviewer_person_id"], unique=False)
    op.create_index("ix_reviews_submitted_at", "reviews", ["submitted_at"], unique=False)
    op.create_index(
        "uq_reviews_mr_external",
        "reviews",
        ["mr_id", "external_id"],
        unique=True,
        sqlite_where=sa.text("external_id IS NOT NULL"),
    )

    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mr_id", sa.Integer(), nullable=False),
        sa.Column("actor_person_id", sa.Integer(), nullable=True),
        sa.Column("actor_type", sa.String(length=20), nullable=False, server_default="human"),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_id", sa.String(length=200), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["mr_id"], ["merge_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_person_id"], ["persons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approvals_mr_id", "approvals", ["mr_id"], unique=False)
    op.create_index("ix_approvals_actor_person_id", "approvals", ["actor_person_id"], unique=False)
    op.create_index(
        "uq_approvals_mr_external",
        "approvals",
        ["mr_id", "external_id"],
        unique=True,
        sqlite_where=sa.text("external_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_approvals_mr_external", table_name="approvals")
    op.drop_index("ix_approvals_actor_person_id", table_name="approvals")
    op.drop_index("ix_approvals_mr_id", table_name="approvals")
    op.drop_table("approvals")

    op.drop_index("uq_reviews_mr_external", table_name="reviews")
    op.drop_index("ix_reviews_submitted_at", table_name="reviews")
    op.drop_index("ix_reviews_reviewer_person_id", table_name="reviews")
    op.drop_index("ix_reviews_mr_id", table_name="reviews")
    op.drop_table("reviews")

    op.drop_index("ix_merge_requests_repository_merged", table_name="merge_requests")
    op.drop_index("ix_merge_requests_repository_state", table_name="merge_requests")
    op.drop_index("ix_merge_requests_author_person_id", table_name="merge_requests")
    op.drop_index("ix_merge_requests_repository_id", table_name="merge_requests")
    op.drop_table("merge_requests")
