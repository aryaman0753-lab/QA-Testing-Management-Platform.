import enum
import uuid
from datetime import datetime
from typing import List

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.api_testing import AuthenticationType, BodyType, HttpMethod
from app.database.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from app.database.models.guid import GUID


class EnvironmentClassification(str, enum.Enum):
    DEVELOPMENT = "DEVELOPMENT"
    TEST = "TEST"
    QA = "QA"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"


class LoadTestStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class LoadTestResultStatus(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    THRESHOLD_EXCEEDED = "THRESHOLD_EXCEEDED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class LoadTestProfile(str, enum.Enum):
    CUSTOM = "CUSTOM"
    SMOKE = "SMOKE"
    BASELINE = "BASELINE"
    LOAD = "LOAD"
    STRESS = "STRESS"
    SPIKE = "SPIKE"
    SOAK = "SOAK"


class LoadTargetType(str, enum.Enum):
    URL = "URL"
    API_REQUEST = "API_REQUEST"


class LoadTest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "load_tests"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_load_test_project_name"),)

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    target_type: Mapped[LoadTargetType] = mapped_column(Enum(LoadTargetType, name="load_target_type", native_enum=False, length=16), nullable=False, default=LoadTargetType.URL)
    api_request_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("api_requests.id", ondelete="SET NULL"), index=True)
    environment_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("api_environments.id"), nullable=False, index=True)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    request_method: Mapped[HttpMethod] = mapped_column(Enum(HttpMethod, name="load_http_method", native_enum=False, length=12), nullable=False)
    headers: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    query_parameters: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    body: Mapped[str | None] = mapped_column(Text)
    body_type: Mapped[BodyType] = mapped_column(Enum(BodyType, name="load_body_type", native_enum=False, length=32), nullable=False, default=BodyType.NONE)
    authentication_type: Mapped[AuthenticationType] = mapped_column(Enum(AuthenticationType, name="load_auth_type", native_enum=False, length=16), nullable=False, default=AuthenticationType.NONE)
    authentication_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    profile: Mapped[LoadTestProfile] = mapped_column(Enum(LoadTestProfile, name="load_test_profile", native_enum=False, length=16), nullable=False, default=LoadTestProfile.CUSTOM)
    virtual_users: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    spawn_rate: Mapped[float] = mapped_column(Float, nullable=False, default=2)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    timeout_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=10)
    target_rps: Mapped[float | None] = mapped_column(Float)
    thresholds: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[LoadTestStatus] = mapped_column(Enum(LoadTestStatus, name="load_test_status", native_enum=False, length=16), nullable=False, default=LoadTestStatus.DRAFT, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)

    environment = relationship("ApiEnvironment")
    project = relationship("Project")
    api_request = relationship("ApiRequest")
    creator = relationship("User")
    runs: Mapped[List["LoadTestRun"]] = relationship(back_populates="load_test", cascade="all, delete-orphan")


class LoadTestRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "load_test_runs"
    __table_args__ = (UniqueConstraint("project_id", "run_number", name="uq_load_run_project_number"), Index("ix_load_runs_project_created", "project_id", "created_at"))

    load_test_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("load_tests.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[LoadTestStatus] = mapped_column(Enum(LoadTestStatus, name="load_run_status", native_enum=False, length=16), nullable=False, default=LoadTestStatus.QUEUED, index=True)
    result_status: Mapped[LoadTestResultStatus | None] = mapped_column(Enum(LoadTestResultStatus, name="load_result_status", native_enum=False, length=24), index=True)
    worker_id: Mapped[str | None] = mapped_column(String(255))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    virtual_users: Mapped[int] = mapped_column(Integer, nullable=False)
    spawn_rate: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    total_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requests_per_second: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    failure_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    avg_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    min_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    max_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    median_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    p50_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    p75_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    p90_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    p95_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    p99_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    status_distribution: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    threshold_results: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_baseline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    load_test: Mapped[LoadTest] = relationship(back_populates="runs")
    creator = relationship("User")
    metrics: Mapped[List["LoadTestMetric"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    endpoints: Mapped[List["LoadTestEndpointMetric"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    errors: Mapped[List["LoadTestError"]] = relationship(back_populates="run", cascade="all, delete-orphan")

    @property
    def run_key(self) -> str:
        return f"LOAD-RUN-{self.run_number:03d}"


class LoadTestMetric(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "load_test_metrics"
    __table_args__ = (Index("ix_load_metrics_run_timestamp", "run_id", "timestamp"),)
    run_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("load_test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    active_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requests_per_second: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    failure_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    avg_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    p50: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    p90: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    p95: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    p99: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    total_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    run: Mapped[LoadTestRun] = relationship(back_populates="metrics")


class LoadTestEndpointMetric(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "load_test_endpoint_metrics"
    __table_args__ = (UniqueConstraint("run_id", "method", "path", name="uq_load_endpoint_run_method_path"),)
    run_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("load_test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(12), nullable=False)
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rps: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    avg_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    min_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    max_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    p50: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    p90: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    p95: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    p99: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    run: Mapped[LoadTestRun] = relationship(back_populates="endpoints")


class LoadTestError(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "load_test_errors"
    __table_args__ = (Index("ix_load_errors_run_type", "run_id", "error_type"),)
    run_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("load_test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(12), nullable=False)
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    run: Mapped[LoadTestRun] = relationship(back_populates="errors")


class LoadTestAuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "load_test_audit_logs"
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
