"""add secure functional API testing

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-15 00:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.database.models.guid import GUID

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def timestamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)]


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("next_api_run_number", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "api_collections",
        sa.Column("id", GUID(), primary_key=True), sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False), sa.Column("description", sa.Text()), sa.Column("created_by", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()), *timestamps(),
        sa.UniqueConstraint("project_id", "name", name="uq_api_collection_project_name"),
    )
    op.create_index("ix_api_collections_project_id", "api_collections", ["project_id"])
    op.create_index("ix_api_collections_is_archived", "api_collections", ["is_archived"])
    op.create_table(
        "api_environments",
        sa.Column("id", GUID(), primary_key=True), sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False), sa.Column("variables", sa.JSON(), nullable=False), sa.Column("created_by", GUID(), sa.ForeignKey("users.id"), nullable=False), *timestamps(),
        sa.UniqueConstraint("project_id", "name", name="uq_api_environment_project_name"),
    )
    op.create_index("ix_api_environments_project_id", "api_environments", ["project_id"])
    op.create_table(
        "api_requests",
        sa.Column("id", GUID(), primary_key=True), sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("collection_id", GUID(), sa.ForeignKey("api_collections.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()), sa.Column("method", sa.Enum("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", name="http_method", native_enum=False, length=12), nullable=False),
        sa.Column("url", sa.Text(), nullable=False), sa.Column("headers", sa.JSON(), nullable=False), sa.Column("query_parameters", sa.JSON(), nullable=False),
        sa.Column("body", sa.Text()), sa.Column("body_type", sa.Enum("NONE", "JSON", "FORM_URLENCODED", "MULTIPART_FORM_DATA", "RAW", name="api_body_type", native_enum=False, length=32), nullable=False),
        sa.Column("authentication_type", sa.Enum("NONE", "BEARER", "BASIC", "API_KEY", name="api_auth_type", native_enum=False, length=16), nullable=False),
        sa.Column("authentication_config", sa.JSON(), nullable=False), sa.Column("position", sa.Integer(), nullable=False), sa.Column("created_by", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()), *timestamps(),
    )
    for column in ("project_id", "collection_id", "is_archived"):
        op.create_index(f"ix_api_requests_{column}", "api_requests", [column])
    op.create_index("ix_api_requests_project_collection", "api_requests", ["project_id", "collection_id"])
    op.create_table(
        "api_assertions", sa.Column("id", GUID(), primary_key=True), sa.Column("request_id", GUID(), sa.ForeignKey("api_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assertion_type", sa.Enum("STATUS_CODE", "RESPONSE_TIME", "BODY_CONTAINS", "JSON_PATH", "HEADER_EXISTS", "HEADER_EQUALS", "JSON_VALUE_EQUALS", "JSON_VALUE_CONTAINS", name="api_assertion_type", native_enum=False, length=32), nullable=False),
        sa.Column("operator", sa.Enum("EQUALS", "NOT_EQUALS", "LESS_THAN", "GREATER_THAN", "CONTAINS", "NOT_CONTAINS", "EXISTS", "NOT_EXISTS", name="api_assertion_operator", native_enum=False, length=20), nullable=False),
        sa.Column("target", sa.String(500)), sa.Column("expected_value", sa.Text()), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("position", sa.Integer(), nullable=False),
    )
    op.create_index("ix_api_assertions_request_id", "api_assertions", ["request_id"])
    op.create_table(
        "api_extractors", sa.Column("id", GUID(), primary_key=True), sa.Column("request_id", GUID(), sa.ForeignKey("api_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.Enum("JSON_PATH", "RESPONSE_HEADER", name="api_extractor_source", native_enum=False, length=24), nullable=False),
        sa.Column("path", sa.String(500), nullable=False), sa.Column("variable_name", sa.String(100), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("position", sa.Integer(), nullable=False),
    )
    op.create_index("ix_api_extractors_request_id", "api_extractors", ["request_id"])
    op.create_table(
        "api_test_runs", sa.Column("id", GUID(), primary_key=True), sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_number", sa.Integer(), nullable=False), sa.Column("collection_id", GUID(), sa.ForeignKey("api_collections.id")), sa.Column("request_id", GUID(), sa.ForeignKey("api_requests.id")),
        sa.Column("environment_id", GUID(), sa.ForeignKey("api_environments.id")), sa.Column("status", sa.Enum("RUNNING", "PASS", "FAIL", "TIMEOUT", "ERROR", name="api_execution_status", native_enum=False, length=16), nullable=False),
        sa.Column("requests_total", sa.Integer(), nullable=False), sa.Column("requests_passed", sa.Integer(), nullable=False), sa.Column("requests_failed", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False), sa.Column("created_by", GUID(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("project_id", "run_number", name="uq_api_run_project_number"),
    )
    for column in ("project_id", "collection_id", "request_id", "status"):
        op.create_index(f"ix_api_test_runs_{column}", "api_test_runs", [column])
    op.create_index("ix_api_runs_project_created", "api_test_runs", ["project_id", "created_at"])
    op.create_table(
        "api_test_results", sa.Column("id", GUID(), primary_key=True), sa.Column("test_run_id", GUID(), sa.ForeignKey("api_test_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_id", GUID(), sa.ForeignKey("api_requests.id"), nullable=False), sa.Column("request_name", sa.String(255), nullable=False), sa.Column("method", sa.String(12), nullable=False), sa.Column("resolved_url", sa.Text(), nullable=False),
        sa.Column("status", sa.Enum("RUNNING", "PASS", "FAIL", "TIMEOUT", "ERROR", name="api_result_status", native_enum=False, length=16), nullable=False),
        sa.Column("status_code", sa.Integer()), sa.Column("response_time_ms", sa.Float(), nullable=False), sa.Column("response_size", sa.Integer(), nullable=False), sa.Column("redirects", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(255)), sa.Column("response_headers", sa.JSON(), nullable=False), sa.Column("response_body", sa.Text()), sa.Column("response_truncated", sa.Boolean(), nullable=False),
        sa.Column("timing", sa.JSON(), nullable=False), sa.Column("assertion_results", sa.JSON(), nullable=False), sa.Column("assertions_total", sa.Integer(), nullable=False),
        sa.Column("assertions_passed", sa.Integer(), nullable=False), sa.Column("assertions_failed", sa.Integer(), nullable=False), sa.Column("extracted_variable_names", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text()), sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("test_run_id", "request_id", "status", "executed_at"):
        op.create_index(f"ix_api_test_results_{column}", "api_test_results", [column])
    op.create_index("ix_api_results_run_request", "api_test_results", ["test_run_id", "request_id"])
    op.create_table(
        "api_audit_logs", sa.Column("id", GUID(), primary_key=True), sa.Column("project_id", GUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False), sa.Column("action", sa.String(50), nullable=False), sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", GUID()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_api_audit_logs_project_id", "api_audit_logs", ["project_id"])
    op.create_index("ix_api_audit_logs_user_id", "api_audit_logs", ["user_id"])
    with op.batch_alter_table("bugs") as batch_op:
        batch_op.add_column(sa.Column("discovered_from_test_result_id", GUID(), nullable=True))
        batch_op.create_foreign_key(
            "fk_bugs_discovered_from_test_result_id",
            "api_test_results",
            ["discovered_from_test_result_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_bugs_discovered_from_test_result_id", ["discovered_from_test_result_id"])


def downgrade() -> None:
    with op.batch_alter_table("bugs") as batch_op:
        batch_op.drop_index("ix_bugs_discovered_from_test_result_id")
        batch_op.drop_constraint("fk_bugs_discovered_from_test_result_id", type_="foreignkey")
        batch_op.drop_column("discovered_from_test_result_id")
    op.drop_table("api_audit_logs")
    op.drop_table("api_test_results")
    op.drop_table("api_test_runs")
    op.drop_table("api_extractors")
    op.drop_table("api_assertions")
    op.drop_table("api_requests")
    op.drop_table("api_environments")
    op.drop_table("api_collections")
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("next_api_run_number")
