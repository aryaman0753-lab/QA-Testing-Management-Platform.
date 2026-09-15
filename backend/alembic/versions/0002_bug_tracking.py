"""bug tracking, comments, history, and attachments

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-15 00:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.database.models.guid import GUID

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("next_bug_number", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "bugs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bug_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("steps_to_reproduce", sa.JSON(), nullable=False),
        sa.Column("expected_result", sa.Text()),
        sa.Column("actual_result", sa.Text()),
        sa.Column("severity", sa.Enum("CRITICAL", "HIGH", "MEDIUM", "LOW", "TRIVIAL", name="bug_severity", native_enum=False, length=16), nullable=False),
        sa.Column("priority", sa.Enum("URGENT", "HIGH", "MEDIUM", "LOW", name="bug_priority", native_enum=False, length=16), nullable=False),
        sa.Column("status", sa.Enum("NEW", "ASSIGNED", "IN_PROGRESS", "FIXED", "QA_VERIFICATION", "VERIFIED", "CLOSED", "REOPENED", "DUPLICATE", "WONT_FIX", name="bug_status", native_enum=False, length=24), nullable=False),
        sa.Column("environment", sa.String(length=100)),
        sa.Column("browser", sa.String(length=100)),
        sa.Column("operating_system", sa.String(length=100)),
        sa.Column("device", sa.String(length=100)),
        sa.Column("reported_by", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_to", GUID(), sa.ForeignKey("users.id")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("archived_by", GUID(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "bug_number", name="uq_bug_project_number"),
    )
    for column in ("project_id", "status", "severity", "priority", "assigned_to", "reported_by", "created_at", "is_archived"):
        op.create_index(f"ix_bugs_{column}", "bugs", [column])
    op.create_index("ix_bugs_project_status", "bugs", ["project_id", "status"])
    op.create_index("ix_bugs_project_created", "bugs", ["project_id", "created_at"])

    op.create_table(
        "bug_comments",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("bug_id", GUID(), sa.ForeignKey("bugs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bug_comments_bug_id", "bug_comments", ["bug_id"])
    op.create_index("ix_bug_comments_user_id", "bug_comments", ["user_id"])

    op.create_table(
        "bug_history",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("bug_id", GUID(), sa.ForeignKey("bugs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("field_name", sa.String(length=100)),
        sa.Column("old_value", sa.Text()),
        sa.Column("new_value", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bug_history_bug_id", "bug_history", ["bug_id"])
    op.create_index("ix_bug_history_user_id", "bug_history", ["user_id"])

    op.create_table(
        "bug_attachments",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("bug_id", GUID(), sa.ForeignKey("bugs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_by", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False, unique=True),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bug_attachments_bug_id", "bug_attachments", ["bug_id"])
    op.create_index("ix_bug_attachments_uploaded_by", "bug_attachments", ["uploaded_by"])


def downgrade() -> None:
    op.drop_table("bug_attachments")
    op.drop_table("bug_history")
    op.drop_table("bug_comments")
    op.drop_table("bugs")
    op.drop_column("projects", "next_bug_number")
