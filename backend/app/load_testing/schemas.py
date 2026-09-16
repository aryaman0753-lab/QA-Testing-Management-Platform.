import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api_testing.schemas import KeyValueItem
from app.bugs.schemas import BugCreate
from app.database.models.api_testing import AuthenticationType, BodyType, HttpMethod
from app.database.models.load_testing import (
    EnvironmentClassification, LoadTargetType, LoadTestProfile, LoadTestResultStatus, LoadTestStatus,
)


class Thresholds(BaseModel):
    max_p95_ms: float | None = Field(None, gt=0)
    max_p99_ms: float | None = Field(None, gt=0)
    max_failure_rate: float | None = Field(None, ge=0, le=100)
    max_average_ms: float | None = Field(None, gt=0)
    min_rps: float | None = Field(None, gt=0)
    max_error_count: int | None = Field(None, ge=0)


class LoadTestCreate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=255)]
    description: Annotated[str | None, Field(max_length=10000)] = None
    api_request_id: uuid.UUID | None = None
    environment_id: uuid.UUID
    target_url: Annotated[str, Field(min_length=1, max_length=10000)]
    request_method: HttpMethod = HttpMethod.GET
    headers: list[KeyValueItem] = Field(default_factory=list, max_length=100)
    query_parameters: list[KeyValueItem] = Field(default_factory=list, max_length=100)
    body: Annotated[str | None, Field(max_length=1_000_000)] = None
    body_type: BodyType = BodyType.NONE
    authentication_type: AuthenticationType = AuthenticationType.NONE
    authentication_config: dict[str, str] = Field(default_factory=dict)
    profile: LoadTestProfile = LoadTestProfile.CUSTOM
    virtual_users: int = Field(10, ge=1)
    spawn_rate: float = Field(2, gt=0)
    duration_seconds: int = Field(30, ge=1)
    timeout_seconds: float = Field(10, gt=0)
    target_rps: float | None = Field(None, gt=0)
    thresholds: Thresholds = Field(default_factory=Thresholds)

    @field_validator("name", "target_url")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank.")
        return value


class LoadTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    target_type: LoadTargetType
    api_request_id: uuid.UUID | None
    environment_id: uuid.UUID
    environment_name: str
    environment_classification: EnvironmentClassification
    target_url: str
    request_method: HttpMethod
    headers: list[KeyValueItem]
    query_parameters: list[KeyValueItem]
    body: str | None
    body_type: BodyType
    authentication_type: AuthenticationType
    authentication_config: dict[str, str]
    profile: LoadTestProfile
    virtual_users: int
    spawn_rate: float
    duration_seconds: int
    timeout_seconds: float
    target_rps: float | None
    thresholds: Thresholds
    status: LoadTestStatus
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class StartRunInput(BaseModel):
    confirm_production: bool = False


class MetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    timestamp: datetime
    active_users: int
    requests_per_second: float
    failure_rate: float
    avg_response_time: float
    p50: float
    p90: float
    p95: float
    p99: float
    total_requests: int
    failed_requests: int


class EndpointMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    method: str
    path: str
    request_count: int
    failure_count: int
    rps: float
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p50: float
    p90: float
    p95: float
    p99: float


class ErrorMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    method: str
    path: str
    error_type: str
    status_code: int | None
    message: str
    count: int


class LoadRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    load_test_id: uuid.UUID
    project_id: uuid.UUID
    run_number: int
    run_key: str
    load_test_name: str
    status: LoadTestStatus
    result_status: LoadTestResultStatus | None
    started_at: datetime | None
    completed_at: datetime | None
    virtual_users: int
    spawn_rate: float
    duration_seconds: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    requests_per_second: float
    failure_rate: float
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    median_response_time: float
    p50_response_time: float
    p75_response_time: float
    p90_response_time: float
    p95_response_time: float
    p99_response_time: float
    status_distribution: dict[str, int]
    error_summary: dict[str, int]
    threshold_results: list[dict]
    config_snapshot: dict
    is_baseline: bool
    error_message: str | None
    created_by: uuid.UUID
    created_at: datetime


class LoadRunDetail(LoadRunOut):
    metrics: list[MetricOut]
    endpoints: list[EndpointMetricOut]
    errors: list[ErrorMetricOut]


class PaginatedLoadRuns(BaseModel):
    items: list[LoadRunOut]
    page: int
    page_size: int
    total: int
    total_pages: int


class AllowlistSettings(BaseModel):
    enabled: bool = True
    allowed_hosts: list[Annotated[str, Field(min_length=1, max_length=253)]] = Field(default_factory=list, max_length=100)


class ComparisonOut(BaseModel):
    run_a: LoadRunOut
    run_b: LoadRunOut
    metrics: list[dict]


class BugFromLoadRunCreate(BugCreate):
    pass
