import enum
import uuid
from datetime import datetime
from typing import List

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from app.database.models.guid import GUID


class HttpMethod(str, enum.Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class BodyType(str, enum.Enum):
    NONE = "NONE"
    JSON = "JSON"
    FORM_URLENCODED = "FORM_URLENCODED"
    MULTIPART_FORM_DATA = "MULTIPART_FORM_DATA"
    RAW = "RAW"


class AuthenticationType(str, enum.Enum):
    NONE = "NONE"
    BEARER = "BEARER"
    BASIC = "BASIC"
    API_KEY = "API_KEY"


class AssertionType(str, enum.Enum):
    STATUS_CODE = "STATUS_CODE"
    RESPONSE_TIME = "RESPONSE_TIME"
    BODY_CONTAINS = "BODY_CONTAINS"
    JSON_PATH = "JSON_PATH"
    HEADER_EXISTS = "HEADER_EXISTS"
    HEADER_EQUALS = "HEADER_EQUALS"
    JSON_VALUE_EQUALS = "JSON_VALUE_EQUALS"
    JSON_VALUE_CONTAINS = "JSON_VALUE_CONTAINS"


class AssertionOperator(str, enum.Enum):
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    LESS_THAN = "LESS_THAN"
    GREATER_THAN = "GREATER_THAN"
    CONTAINS = "CONTAINS"
    NOT_CONTAINS = "NOT_CONTAINS"
    EXISTS = "EXISTS"
    NOT_EXISTS = "NOT_EXISTS"


class ExtractorSource(str, enum.Enum):
    JSON_PATH = "JSON_PATH"
    RESPONSE_HEADER = "RESPONSE_HEADER"


class ExecutionStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


class ApiCollection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_collections"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_api_collection_project_name"),)

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    requests: Mapped[List["ApiRequest"]] = relationship(back_populates="collection", cascade="all, delete-orphan")
    creator = relationship("User")


class ApiRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_requests"
    __table_args__ = (Index("ix_api_requests_project_collection", "project_id", "collection_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    collection_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("api_collections.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    method: Mapped[HttpMethod] = mapped_column(Enum(HttpMethod, name="http_method", native_enum=False, length=12), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    headers: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    query_parameters: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    body: Mapped[str | None] = mapped_column(Text)
    body_type: Mapped[BodyType] = mapped_column(Enum(BodyType, name="api_body_type", native_enum=False, length=32), nullable=False, default=BodyType.NONE)
    authentication_type: Mapped[AuthenticationType] = mapped_column(Enum(AuthenticationType, name="api_auth_type", native_enum=False, length=16), nullable=False, default=AuthenticationType.NONE)
    authentication_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    collection: Mapped[ApiCollection] = relationship(back_populates="requests")
    creator = relationship("User")
    assertions: Mapped[List["ApiAssertion"]] = relationship(back_populates="request", cascade="all, delete-orphan")
    extractors: Mapped[List["ApiExtractor"]] = relationship(back_populates="request", cascade="all, delete-orphan")


class ApiAssertion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "api_assertions"

    request_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("api_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    assertion_type: Mapped[AssertionType] = mapped_column(Enum(AssertionType, name="api_assertion_type", native_enum=False, length=32), nullable=False)
    operator: Mapped[AssertionOperator] = mapped_column(Enum(AssertionOperator, name="api_assertion_operator", native_enum=False, length=20), nullable=False)
    target: Mapped[str | None] = mapped_column(String(500))
    expected_value: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request: Mapped[ApiRequest] = relationship(back_populates="assertions")


class ApiExtractor(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "api_extractors"

    request_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("api_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[ExtractorSource] = mapped_column(Enum(ExtractorSource, name="api_extractor_source", native_enum=False, length=24), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    variable_name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request: Mapped[ApiRequest] = relationship(back_populates="extractors")


class ApiEnvironment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_environments"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_api_environment_project_name"),)

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    variables: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    classification: Mapped[str] = mapped_column(String(16), nullable=False, default="QA")
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    creator = relationship("User")


class ApiTestRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "api_test_runs"
    __table_args__ = (
        UniqueConstraint("project_id", "run_number", name="uq_api_run_project_number"),
        Index("ix_api_runs_project_created", "project_id", "created_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    collection_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("api_collections.id"), index=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("api_requests.id"), index=True)
    environment_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("api_environments.id"))
    status: Mapped[ExecutionStatus] = mapped_column(Enum(ExecutionStatus, name="api_execution_status", native_enum=False, length=16), nullable=False, default=ExecutionStatus.RUNNING, index=True)
    requests_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requests_passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requests_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collection = relationship("ApiCollection")
    request = relationship("ApiRequest", foreign_keys=[request_id])
    environment = relationship("ApiEnvironment")
    creator = relationship("User")
    results: Mapped[List["ApiTestResult"]] = relationship(back_populates="run", cascade="all, delete-orphan")

    @property
    def run_key(self) -> str:
        return f"API-RUN-{self.run_number:03d}"


class ApiTestResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "api_test_results"
    __table_args__ = (Index("ix_api_results_run_request", "test_run_id", "request_id"),)

    test_run_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("api_test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    request_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("api_requests.id"), nullable=False, index=True)
    request_name: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(12), nullable=False)
    resolved_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ExecutionStatus] = mapped_column(Enum(ExecutionStatus, name="api_result_status", native_enum=False, length=16), nullable=False, index=True)
    status_code: Mapped[int | None] = mapped_column(Integer)
    response_time_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    response_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    redirects: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_type: Mapped[str | None] = mapped_column(String(255))
    response_headers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    response_body: Mapped[str | None] = mapped_column(Text)
    response_truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timing: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    assertion_results: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    assertions_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assertions_passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assertions_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extracted_variable_names: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    run: Mapped[ApiTestRun] = relationship(back_populates="results")
    request = relationship("ApiRequest")


class ApiAuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "api_audit_logs"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
