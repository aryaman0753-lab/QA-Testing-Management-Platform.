"""Automation definitions, immutable execution history and scheduler state."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from app.database.models.guid import GUID


class SuiteStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    ARCHIVED = "ARCHIVED"


class AutomationRunStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AutomationStepType(str, enum.Enum):
    HTTP_REQUEST = "HTTP_REQUEST"
    ASSERTION = "ASSERTION"
    EXTRACT_VARIABLE = "EXTRACT_VARIABLE"
    SET_VARIABLE = "SET_VARIABLE"
    DELAY = "DELAY"
    CONDITION = "CONDITION"


class AutomationResultStatus(str, enum.Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class AutomationTestSuite(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "automation_test_suites"
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    environment_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("api_environments.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", index=True)
    auto_create_bugs: Mapped[bool] = mapped_column(Boolean, default=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=0)
    allowed_hosts: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"))
    environment = relationship("ApiEnvironment")
    project = relationship("Project")
    cases: Mapped[list["AutomationTestCase"]] = relationship(back_populates="suite", cascade="all, delete-orphan", order_by="AutomationTestCase.order_index")


class AutomationTestCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "automation_test_cases"
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    suite_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("automation_test_suites.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    timeout: Mapped[float] = mapped_column(Float, default=60)
    suite: Mapped[AutomationTestSuite] = relationship(back_populates="cases")
    steps: Mapped[list["AutomationTestStep"]] = relationship(back_populates="case", cascade="all, delete-orphan", order_by="AutomationTestStep.order_index")


class AutomationTestStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "automation_test_steps"
    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("automation_test_cases.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    step_type: Mapped[str] = mapped_column(String(32))
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    api_request_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("api_requests.id", ondelete="SET NULL"), index=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    condition: Mapped[dict | None] = mapped_column(JSON)
    case: Mapped[AutomationTestCase] = relationship(back_populates="steps")
    api_request = relationship("ApiRequest")


class AutomationRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "automation_runs"
    __table_args__ = (Index("ix_automation_runs_project_created", "project_id", "created_at"),)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    suite_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("automation_test_suites.id", ondelete="CASCADE"), index=True)
    environment_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("api_environments.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="QUEUED", index=True)
    triggered_by: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"))
    trigger_type: Mapped[str] = mapped_column(String(16), default="MANUAL")
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("automation_schedules.id", ondelete="SET NULL"), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[float] = mapped_column(Float, default=0)
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, default=0)
    failed_cases: Mapped[int] = mapped_column(Integer, default=0)
    skipped_cases: Mapped[int] = mapped_column(Integer, default=0)
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    passed_steps: Mapped[int] = mapped_column(Integer, default=0)
    failed_steps: Mapped[int] = mapped_column(Integer, default=0)
    skipped_steps: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    stop_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    config_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    suite = relationship("AutomationTestSuite")
    results: Mapped[list["AutomationStepResult"]] = relationship(back_populates="run", cascade="all, delete-orphan", order_by="AutomationStepResult.order_index, AutomationStepResult.attempt")


class AutomationStepResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "automation_step_results"
    run_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("automation_runs.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("automation_test_cases.id", ondelete="SET NULL"), index=True)
    step_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("automation_test_steps.id", ondelete="SET NULL"), index=True)
    case_name: Mapped[str] = mapped_column(String(255))
    step_name: Mapped[str] = mapped_column(String(255))
    step_type: Mapped[str] = mapped_column(String(32))
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    is_final: Mapped[bool] = mapped_column(Boolean, default=True)
    request_method: Mapped[str | None] = mapped_column(String(12))
    resolved_url: Mapped[str | None] = mapped_column(Text)
    status_code: Mapped[int | None] = mapped_column(Integer)
    response_time_ms: Mapped[float | None] = mapped_column(Float)
    assertions: Mapped[list] = mapped_column(JSON, default=list)
    extracted_variables: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    error_kind: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run: Mapped[AutomationRun] = relationship(back_populates="results")


class AutomationSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "automation_schedules"
    suite_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("automation_test_suites.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    environment_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("api_environments.id", ondelete="SET NULL"), index=True)
    cron_expression: Mapped[str] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(100), default="UTC")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"))
    suite = relationship("AutomationTestSuite")


class AutomationFailureLink(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "automation_failure_links"
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    bug_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("bugs.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("automation_runs.id", ondelete="SET NULL"))
    case_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("automation_test_cases.id", ondelete="SET NULL"))
    step_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("automation_test_steps.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    bug = relationship("Bug", foreign_keys=[bug_id])


class AutomationAuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "automation_audit_logs"
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(50))
    resource_type: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
