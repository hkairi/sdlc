"""Ajout des features, tâches et liaisons multi-dépôts.

Revision ID: 0008_features_tasks
Revises: 0007_runs_deployments
Create Date: 2026-10-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_features_tasks"
down_revision = "0007_runs_deployments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "features",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("primary_repository_id", sa.Integer(), nullable=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="todo"),
        sa.Column("owner_person_id", sa.Integer(), nullable=True),
        sa.Column("spec_path", sa.String(length=1000), nullable=True),
        sa.Column("change", sa.String(length=100), nullable=True),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("tasks_file", sa.String(length=1000), nullable=True),
        sa.Column("sources_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("delivered", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.String(length=50), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["primary_repository_id"], ["repositories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_person_id"], ["persons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "key", name="uq_features_project_key"),
    )
    op.create_index("ix_features_project_id", "features", ["project_id"], unique=False)
    op.create_index("ix_features_primary_repository_id", "features", ["primary_repository_id"], unique=False)
    op.create_index("ix_features_owner_person_id", "features", ["owner_person_id"], unique=False)
    op.create_index("ix_features_project_status", "features", ["project_id", "status"], unique=False)

    op.create_table(
        "feature_repositories",
        sa.Column("feature_id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["feature_id"], ["features.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("feature_id", "repository_id"),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("feature_id", sa.Integer(), nullable=False),
        sa.Column("primary_repository_id", sa.Integer(), nullable=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("lot", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="todo"),
        sa.Column("owner_person_id", sa.Integer(), nullable=True),
        sa.Column("reviewer_person_id", sa.Integer(), nullable=True),
        sa.Column("executor_label", sa.String(length=200), nullable=True),
        sa.Column("reviewer_label", sa.String(length=200), nullable=True),
        sa.Column("files_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("acceptance", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["feature_id"], ["features.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["primary_repository_id"], ["repositories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_person_id"], ["persons.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewer_person_id"], ["persons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feature_id", "key", name="uq_tasks_feature_key"),
    )
    op.create_index("ix_tasks_feature_id", "tasks", ["feature_id"], unique=False)
    op.create_index("ix_tasks_primary_repository_id", "tasks", ["primary_repository_id"], unique=False)
    op.create_index("ix_tasks_owner_person_id", "tasks", ["owner_person_id"], unique=False)
    op.create_index("ix_tasks_reviewer_person_id", "tasks", ["reviewer_person_id"], unique=False)
    op.create_index("ix_tasks_feature_status", "tasks", ["feature_id", "status"], unique=False)

    op.create_table(
        "task_repositories",
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "repository_id"),
    )
    op.create_index(
        "uq_task_repositories_primary",
        "task_repositories",
        ["task_id"],
        unique=True,
        sqlite_where=sa.text("is_primary = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_task_repositories_primary", table_name="task_repositories")
    op.drop_table("task_repositories")

    op.drop_index("ix_tasks_feature_status", table_name="tasks")
    op.drop_index("ix_tasks_reviewer_person_id", table_name="tasks")
    op.drop_index("ix_tasks_owner_person_id", table_name="tasks")
    op.drop_index("ix_tasks_primary_repository_id", table_name="tasks")
    op.drop_index("ix_tasks_feature_id", table_name="tasks")
    op.drop_table("tasks")

    op.drop_table("feature_repositories")

    op.drop_index("ix_features_project_status", table_name="features")
    op.drop_index("ix_features_owner_person_id", table_name="features")
    op.drop_index("ix_features_primary_repository_id", table_name="features")
    op.drop_index("ix_features_project_id", table_name="features")
    op.drop_table("features")
