"""add CI, webhook, notification and worker operations

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-17 00:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.database.models.guid import GUID

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "project_api_keys",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("token_prefix", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("created_by", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    for column in ("project_id", "token_prefix", "revoked_at"):
        op.create_index(f"ix_project_api_keys_{column}", "project_api_keys", [column])

    op.create_table(
        "ci_test_executions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("automation_run_id", GUID(), sa.ForeignKey("automation_runs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("api_key_id", GUID(), sa.ForeignKey("project_api_keys.id", ondelete="SET NULL")),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("commit_sha", sa.String(100)),
        sa.Column("branch", sa.String(255)),
        sa.Column("build_number", sa.String(100)),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("project_id", "automation_run_id", "provider", "commit_sha", "branch", "created_at"):
        op.create_index(f"ix_ci_test_executions_{column}", "ci_test_executions", [column])
    op.create_index("ix_ci_executions_project_created", "ci_test_executions", ["project_id", "created_at"])
    op.create_index("ix_ci_executions_provider_build", "ci_test_executions", ["provider", "build_number"])

    op.create_table(
        "webhooks",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by", GUID(), sa.ForeignKey("users.id"), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("project_id", "name", name="uq_webhooks_project_name"),
    )
    for column in ("project_id", "enabled"):
        op.create_index(f"ix_webhooks_{column}", "webhooks", [column])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("webhook_id", GUID(), sa.ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("response_status", sa.Integer()),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    for column in ("webhook_id", "project_id", "event", "event_id", "status", "next_retry_at"):
        op.create_index(f"ix_webhook_deliveries_{column}", "webhook_deliveries", [column])
    op.create_index("ix_webhook_deliveries_due", "webhook_deliveries", ["status", "next_retry_at"])
    op.create_index("ix_webhook_deliveries_project_created", "webhook_deliveries", ["project_id", "created_at"])

    op.create_table(
        "notification_preferences",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), nullable=False),
        sa.Column("webhook_enabled", sa.Boolean(), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "project_id", name="uq_notification_preferences_user_project"),
    )
    op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"])
    op.create_index("ix_notification_preferences_project_id", "notification_preferences", ["project_id"])
    op.create_index("uq_notification_preferences_user_global", "notification_preferences", ["user_id"], unique=True, postgresql_where=sa.text("project_id IS NULL"), sqlite_where=sa.text("project_id IS NULL"))

    op.create_table(
        "notifications",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("link", sa.Text()),
        sa.Column("dedupe_key", sa.String(128), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("email_status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe"),
    )
    for column in ("user_id", "project_id", "event", "is_read"):
        op.create_index(f"ix_notifications_{column}", "notifications", [column])
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"])

    op.create_table(
        "worker_heartbeats",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("worker_id", sa.String(255), nullable=False, unique=True),
        sa.Column("worker_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_job", sa.String(255)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_jobs", sa.Integer(), nullable=False),
        sa.Column("failed_jobs", sa.Integer(), nullable=False),
    )
    for column in ("worker_id", "worker_type", "status", "last_heartbeat"):
        op.create_index(f"ix_worker_heartbeats_{column}", "worker_heartbeats", [column])


def downgrade() -> None:
    op.drop_table("worker_heartbeats")
    op.drop_table("notifications")
    op.drop_table("notification_preferences")
    op.drop_table("webhook_deliveries")
    op.drop_table("webhooks")
    op.drop_table("ci_test_executions")
    op.drop_table("project_api_keys")
