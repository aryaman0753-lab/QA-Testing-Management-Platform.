"""add advanced API automation, scheduling, and execution history

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-17 00:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.database.models.guid import GUID

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "automation_test_suites",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("environment_id", GUID(), sa.ForeignKey("api_environments.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("auto_create_bugs", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("allowed_hosts", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_by", GUID(), sa.ForeignKey("users.id"), nullable=False),
        *_timestamps(),
    )
    for column in ("project_id", "environment_id", "status"):
        op.create_index(f"ix_automation_test_suites_{column}", "automation_test_suites", [column])

    op.create_table(
        "automation_test_cases",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("suite_id", GUID(), sa.ForeignKey("automation_test_suites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("timeout", sa.Float(), nullable=False, server_default="60"),
        *_timestamps(),
    )
    for column in ("project_id", "suite_id"):
        op.create_index(f"ix_automation_test_cases_{column}", "automation_test_cases", [column])

    op.create_table(
        "automation_test_steps",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("case_id", GUID(), sa.ForeignKey("automation_test_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("step_type", sa.String(32), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("api_request_id", GUID(), sa.ForeignKey("api_requests.id", ondelete="SET NULL")),
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("condition", sa.JSON()),
        *_timestamps(),
    )
    for column in ("case_id", "api_request_id"):
        op.create_index(f"ix_automation_test_steps_{column}", "automation_test_steps", [column])

    op.create_table(
        "automation_schedules",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("suite_id", GUID(), sa.ForeignKey("automation_test_suites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("environment_id", GUID(), sa.ForeignKey("api_environments.id", ondelete="SET NULL")),
        sa.Column("cron_expression", sa.String(100), nullable=False),
        sa.Column("timezone", sa.String(100), nullable=False, server_default="UTC"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_by", GUID(), sa.ForeignKey("users.id"), nullable=False),
        *_timestamps(),
    )
    for column in ("suite_id", "project_id", "environment_id", "enabled", "next_run_at"):
        op.create_index(f"ix_automation_schedules_{column}", "automation_schedules", [column])

    op.create_table(
        "automation_runs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("suite_id", GUID(), sa.ForeignKey("automation_test_suites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("environment_id", GUID(), sa.ForeignKey("api_environments.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(16), nullable=False, server_default="QUEUED"),
        sa.Column("triggered_by", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("trigger_type", sa.String(16), nullable=False, server_default="MANUAL"),
        sa.Column("schedule_id", GUID(), sa.ForeignKey("automation_schedules.id", ondelete="SET NULL")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_steps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed_steps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_steps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_steps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("stop_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_message", sa.Text()),
        sa.Column("config_snapshot", sa.JSON(), nullable=False, server_default="{}"),
    )
    for column in ("project_id", "suite_id", "environment_id", "status", "schedule_id", "heartbeat_at"):
        op.create_index(f"ix_automation_runs_{column}", "automation_runs", [column])
    op.create_index("ix_automation_runs_project_created", "automation_runs", ["project_id", "created_at"])

    op.create_table(
        "automation_step_results",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("run_id", GUID(), sa.ForeignKey("automation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", GUID(), sa.ForeignKey("automation_test_cases.id", ondelete="SET NULL")),
        sa.Column("step_id", GUID(), sa.ForeignKey("automation_test_steps.id", ondelete="SET NULL")),
        sa.Column("case_name", sa.String(255), nullable=False),
        sa.Column("step_name", sa.String(255), nullable=False),
        sa.Column("step_type", sa.String(32), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_final", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("request_method", sa.String(12)),
        sa.Column("resolved_url", sa.Text()),
        sa.Column("status_code", sa.Integer()),
        sa.Column("response_time_ms", sa.Float()),
        sa.Column("assertions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("extracted_variables", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text()),
        sa.Column("error_kind", sa.String(64)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    for column in ("run_id", "case_id", "step_id", "status"):
        op.create_index(f"ix_automation_step_results_{column}", "automation_step_results", [column])

    op.create_table(
        "automation_failure_links",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("bug_id", GUID(), sa.ForeignKey("bugs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", GUID(), sa.ForeignKey("automation_runs.id", ondelete="SET NULL")),
        sa.Column("case_id", GUID(), sa.ForeignKey("automation_test_cases.id", ondelete="SET NULL")),
        sa.Column("step_id", GUID(), sa.ForeignKey("automation_test_steps.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_automation_failure_links_bug_id", "automation_failure_links", ["bug_id"])

    op.create_table(
        "automation_audit_logs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", GUID()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_automation_audit_logs_project_id", "automation_audit_logs", ["project_id"])

    with op.batch_alter_table("bugs") as batch:
        batch.add_column(sa.Column("discovered_from_automation_run_id", GUID(), nullable=True))
        batch.add_column(sa.Column("discovered_from_automation_step_result_id", GUID(), nullable=True))
        batch.create_foreign_key("fk_bugs_automation_run", "automation_runs", ["discovered_from_automation_run_id"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_bugs_automation_step_result", "automation_step_results", ["discovered_from_automation_step_result_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_bugs_discovered_from_automation_run_id", ["discovered_from_automation_run_id"])
        batch.create_index("ix_bugs_discovered_from_automation_step_result_id", ["discovered_from_automation_step_result_id"])


def downgrade() -> None:
    with op.batch_alter_table("bugs") as batch:
        batch.drop_index("ix_bugs_discovered_from_automation_step_result_id")
        batch.drop_index("ix_bugs_discovered_from_automation_run_id")
        batch.drop_constraint("fk_bugs_automation_step_result", type_="foreignkey")
        batch.drop_constraint("fk_bugs_automation_run", type_="foreignkey")
        batch.drop_column("discovered_from_automation_step_result_id")
        batch.drop_column("discovered_from_automation_run_id")
    op.drop_table("automation_audit_logs")
    op.drop_table("automation_failure_links")
    op.drop_table("automation_step_results")
    op.drop_table("automation_runs")
    op.drop_table("automation_schedules")
    op.drop_table("automation_test_steps")
    op.drop_table("automation_test_cases")
    op.drop_table("automation_test_suites")
