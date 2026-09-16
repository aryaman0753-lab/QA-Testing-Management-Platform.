"""add isolated load testing and aggregated performance metrics

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-16 00:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.database.models.guid import GUID

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("next_load_run_number", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("load_allowlist_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("load_allowed_hosts", sa.JSON(), nullable=False, server_default="[]"))
    with op.batch_alter_table("api_environments") as batch:
        batch.add_column(sa.Column("classification", sa.String(16), nullable=False, server_default="QA"))

    op.create_table(
        "load_tests",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False), sa.Column("description", sa.Text()),
        sa.Column("target_type", sa.Enum("URL", "API_REQUEST", name="load_target_type", native_enum=False, length=16), nullable=False),
        sa.Column("api_request_id", GUID(), sa.ForeignKey("api_requests.id", ondelete="SET NULL")),
        sa.Column("environment_id", GUID(), sa.ForeignKey("api_environments.id"), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("request_method", sa.Enum("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", name="load_http_method", native_enum=False, length=12), nullable=False),
        sa.Column("headers", sa.JSON(), nullable=False), sa.Column("query_parameters", sa.JSON(), nullable=False), sa.Column("body", sa.Text()),
        sa.Column("body_type", sa.Enum("NONE", "JSON", "FORM_URLENCODED", "MULTIPART_FORM_DATA", "RAW", name="load_body_type", native_enum=False, length=32), nullable=False),
        sa.Column("authentication_type", sa.Enum("NONE", "BEARER", "BASIC", "API_KEY", name="load_auth_type", native_enum=False, length=16), nullable=False),
        sa.Column("authentication_config", sa.JSON(), nullable=False),
        sa.Column("profile", sa.Enum("CUSTOM", "SMOKE", "BASELINE", "LOAD", "STRESS", "SPIKE", "SOAK", name="load_test_profile", native_enum=False, length=16), nullable=False),
        sa.Column("virtual_users", sa.Integer(), nullable=False), sa.Column("spawn_rate", sa.Float(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False), sa.Column("timeout_seconds", sa.Float(), nullable=False), sa.Column("target_rps", sa.Float()),
        sa.Column("thresholds", sa.JSON(), nullable=False),
        sa.Column("status", sa.Enum("DRAFT", "QUEUED", "STARTING", "RUNNING", "STOPPING", "COMPLETED", "FAILED", "CANCELLED", name="load_test_status", native_enum=False, length=16), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_by", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name", name="uq_load_test_project_name"),
    )
    for column in ("project_id", "api_request_id", "environment_id", "status", "is_archived"):
        op.create_index(f"ix_load_tests_{column}", "load_tests", [column])

    op.create_table(
        "load_test_runs",
        sa.Column("id", GUID(), primary_key=True), sa.Column("load_test_id", GUID(), sa.ForeignKey("load_tests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False), sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum("DRAFT", "QUEUED", "STARTING", "RUNNING", "STOPPING", "COMPLETED", "FAILED", "CANCELLED", name="load_run_status", native_enum=False, length=16), nullable=False),
        sa.Column("result_status", sa.Enum("PASS", "FAIL", "THRESHOLD_EXCEEDED", "ERROR", "CANCELLED", name="load_result_status", native_enum=False, length=24)),
        sa.Column("worker_id", sa.String(255)), sa.Column("heartbeat_at", sa.DateTime(timezone=True)), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("virtual_users", sa.Integer(), nullable=False), sa.Column("spawn_rate", sa.Float(), nullable=False), sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("total_requests", sa.Integer(), nullable=False), sa.Column("successful_requests", sa.Integer(), nullable=False), sa.Column("failed_requests", sa.Integer(), nullable=False),
        sa.Column("requests_per_second", sa.Float(), nullable=False), sa.Column("failure_rate", sa.Float(), nullable=False),
        sa.Column("avg_response_time", sa.Float(), nullable=False), sa.Column("min_response_time", sa.Float(), nullable=False), sa.Column("max_response_time", sa.Float(), nullable=False),
        sa.Column("median_response_time", sa.Float(), nullable=False), sa.Column("p50_response_time", sa.Float(), nullable=False), sa.Column("p75_response_time", sa.Float(), nullable=False),
        sa.Column("p90_response_time", sa.Float(), nullable=False), sa.Column("p95_response_time", sa.Float(), nullable=False), sa.Column("p99_response_time", sa.Float(), nullable=False),
        sa.Column("status_distribution", sa.JSON(), nullable=False), sa.Column("error_summary", sa.JSON(), nullable=False), sa.Column("threshold_results", sa.JSON(), nullable=False),
        sa.Column("config_snapshot", sa.JSON(), nullable=False), sa.Column("is_baseline", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("error_message", sa.Text()),
        sa.Column("created_by", GUID(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "run_number", name="uq_load_run_project_number"),
    )
    for column in ("load_test_id", "project_id", "status", "result_status", "heartbeat_at", "started_at", "is_baseline"):
        op.create_index(f"ix_load_test_runs_{column}", "load_test_runs", [column])
    op.create_index("ix_load_runs_project_created", "load_test_runs", ["project_id", "created_at"])

    op.create_table(
        "load_test_metrics", sa.Column("id", GUID(), primary_key=True), sa.Column("run_id", GUID(), sa.ForeignKey("load_test_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False), sa.Column("active_users", sa.Integer(), nullable=False), sa.Column("requests_per_second", sa.Float(), nullable=False),
        sa.Column("failure_rate", sa.Float(), nullable=False), sa.Column("avg_response_time", sa.Float(), nullable=False), sa.Column("p50", sa.Float(), nullable=False),
        sa.Column("p90", sa.Float(), nullable=False), sa.Column("p95", sa.Float(), nullable=False), sa.Column("p99", sa.Float(), nullable=False),
        sa.Column("total_requests", sa.Integer(), nullable=False), sa.Column("failed_requests", sa.Integer(), nullable=False),
    )
    op.create_index("ix_load_test_metrics_run_id", "load_test_metrics", ["run_id"])
    op.create_index("ix_load_test_metrics_timestamp", "load_test_metrics", ["timestamp"])
    op.create_index("ix_load_metrics_run_timestamp", "load_test_metrics", ["run_id", "timestamp"])

    op.create_table(
        "load_test_endpoint_metrics", sa.Column("id", GUID(), primary_key=True), sa.Column("run_id", GUID(), sa.ForeignKey("load_test_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("method", sa.String(12), nullable=False), sa.Column("path", sa.String(1000), nullable=False), sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False), sa.Column("rps", sa.Float(), nullable=False), sa.Column("avg_response_time", sa.Float(), nullable=False),
        sa.Column("min_response_time", sa.Float(), nullable=False), sa.Column("max_response_time", sa.Float(), nullable=False), sa.Column("p50", sa.Float(), nullable=False),
        sa.Column("p90", sa.Float(), nullable=False), sa.Column("p95", sa.Float(), nullable=False), sa.Column("p99", sa.Float(), nullable=False),
        sa.UniqueConstraint("run_id", "method", "path", name="uq_load_endpoint_run_method_path"),
    )
    op.create_index("ix_load_test_endpoint_metrics_run_id", "load_test_endpoint_metrics", ["run_id"])

    op.create_table(
        "load_test_errors", sa.Column("id", GUID(), primary_key=True), sa.Column("run_id", GUID(), sa.ForeignKey("load_test_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("method", sa.String(12), nullable=False), sa.Column("path", sa.String(1000), nullable=False), sa.Column("error_type", sa.String(100), nullable=False),
        sa.Column("status_code", sa.Integer()), sa.Column("message", sa.String(1000), nullable=False), sa.Column("count", sa.Integer(), nullable=False),
    )
    op.create_index("ix_load_test_errors_run_id", "load_test_errors", ["run_id"])
    op.create_index("ix_load_errors_run_type", "load_test_errors", ["run_id", "error_type"])

    op.create_table(
        "load_test_audit_logs", sa.Column("id", GUID(), primary_key=True), sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False), sa.Column("action", sa.String(50), nullable=False), sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", GUID()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_load_test_audit_logs_project_id", "load_test_audit_logs", ["project_id"])
    op.create_index("ix_load_test_audit_logs_user_id", "load_test_audit_logs", ["user_id"])

    with op.batch_alter_table("bugs") as batch:
        batch.add_column(sa.Column("discovered_from_load_test_run_id", GUID(), nullable=True))
        batch.create_foreign_key("fk_bugs_discovered_from_load_test_run_id", "load_test_runs", ["discovered_from_load_test_run_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_bugs_discovered_from_load_test_run_id", ["discovered_from_load_test_run_id"])


def downgrade() -> None:
    with op.batch_alter_table("bugs") as batch:
        batch.drop_index("ix_bugs_discovered_from_load_test_run_id")
        batch.drop_constraint("fk_bugs_discovered_from_load_test_run_id", type_="foreignkey")
        batch.drop_column("discovered_from_load_test_run_id")
    op.drop_table("load_test_audit_logs")
    op.drop_table("load_test_errors")
    op.drop_table("load_test_endpoint_metrics")
    op.drop_table("load_test_metrics")
    op.drop_table("load_test_runs")
    op.drop_table("load_tests")
    with op.batch_alter_table("api_environments") as batch:
        batch.drop_column("classification")
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("load_allowed_hosts")
        batch.drop_column("load_allowlist_enabled")
        batch.drop_column("next_load_run_number")
