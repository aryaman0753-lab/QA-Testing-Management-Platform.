import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.bugs.schemas import BugCreate
from app.database.models.api_testing import (
    AssertionOperator, AssertionType, AuthenticationType, BodyType,
    ExecutionStatus, ExtractorSource, HttpMethod,
)


def clean_required(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Field cannot be blank.")
    return value


class KeyValueItem(BaseModel):
    key: Annotated[str, Field(max_length=500)]
    value: Annotated[str, Field(max_length=10000)] = ""
    enabled: bool = True


class AssertionInput(BaseModel):
    assertion_type: AssertionType
    operator: AssertionOperator
    target: Annotated[str | None, Field(max_length=500)] = None
    expected_value: Annotated[str | None, Field(max_length=10000)] = None
    enabled: bool = True


class AssertionOut(AssertionInput):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    position: int


class ExtractorInput(BaseModel):
    source: ExtractorSource
    path: Annotated[str, Field(max_length=500)]
    variable_name: Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,99}$")]
    enabled: bool = True

    _path_required = field_validator("path")(clean_required)


class ExtractorOut(ExtractorInput):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    position: int


class CollectionCreate(BaseModel):
    name: Annotated[str, Field(max_length=255)]
    description: Annotated[str | None, Field(max_length=10000)] = None
    _name_required = field_validator("name")(clean_required)


class CollectionUpdate(CollectionCreate):
    pass


class CollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    request_count: int = 0


class RequestCreate(BaseModel):
    name: Annotated[str, Field(max_length=255)]
    description: Annotated[str | None, Field(max_length=10000)] = None
    method: HttpMethod = HttpMethod.GET
    url: Annotated[str, Field(max_length=10000)]
    headers: list[KeyValueItem] = Field(default_factory=list, max_length=100)
    query_parameters: list[KeyValueItem] = Field(default_factory=list, max_length=100)
    body: Annotated[str | None, Field(max_length=1_000_000)] = None
    body_type: BodyType = BodyType.NONE
    authentication_type: AuthenticationType = AuthenticationType.NONE
    authentication_config: dict[str, str] = Field(default_factory=dict)
    assertions: list[AssertionInput] = Field(default_factory=list, max_length=100)
    extractors: list[ExtractorInput] = Field(default_factory=list, max_length=50)
    position: int = Field(0, ge=0)

    _name_required = field_validator("name")(clean_required)
    _url_required = field_validator("url")(clean_required)


class RequestUpdate(RequestCreate):
    pass


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    collection_id: uuid.UUID
    name: str
    description: str | None
    method: HttpMethod
    url: str
    headers: list[KeyValueItem]
    query_parameters: list[KeyValueItem]
    body: str | None
    body_type: BodyType
    authentication_type: AuthenticationType
    authentication_config: dict[str, str]
    assertions: list[AssertionOut]
    extractors: list[ExtractorOut]
    position: int
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class CollectionDetail(CollectionOut):
    requests: list[RequestOut]


class EnvironmentVariable(BaseModel):
    name: Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,99}$")]
    value: Annotated[str, Field(max_length=10000)] = ""
    is_secret: bool = False


class EnvironmentCreate(BaseModel):
    name: Annotated[str, Field(max_length=100)]
    variables: list[EnvironmentVariable] = Field(default_factory=list, max_length=200)
    _name_required = field_validator("name")(clean_required)


class EnvironmentUpdate(EnvironmentCreate):
    pass


class EnvironmentOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    variables: list[EnvironmentVariable]
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ExecuteInput(BaseModel):
    environment_id: uuid.UUID | None = None
    request_ids: list[uuid.UUID] | None = Field(None, max_length=1000)
    runtime_variables: dict[str, Annotated[str, Field(max_length=10000)]] = Field(default_factory=dict)
    timeout_seconds: float | None = Field(None, gt=0)
    verify_ssl: bool = True


class AssertionResultOut(BaseModel):
    assertion_type: str
    passed: bool
    description: str
    expected: str | None = None
    actual: str | None = None


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    test_run_id: uuid.UUID
    request_id: uuid.UUID
    request_name: str
    method: str
    resolved_url: str
    status: ExecutionStatus
    status_code: int | None
    response_time_ms: float
    response_size: int
    redirects: int
    content_type: str | None
    response_headers: dict[str, str]
    response_body: str | None
    response_truncated: bool
    timing: dict
    assertion_results: list[AssertionResultOut]
    assertions_total: int
    assertions_passed: int
    assertions_failed: int
    extracted_variable_names: list[str]
    error_message: str | None
    executed_at: datetime


class RunListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    run_number: int
    run_key: str
    collection_id: uuid.UUID | None
    request_id: uuid.UUID | None
    collection_name: str | None
    request_name: str | None
    status: ExecutionStatus
    requests_total: int
    requests_passed: int
    requests_failed: int
    duration_ms: float
    created_by: uuid.UUID
    created_at: datetime
    completed_at: datetime | None


class RunDetail(RunListItem):
    results: list[ResultOut]


class PaginatedRuns(BaseModel):
    items: list[RunListItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class HealthCheckInput(BaseModel):
    url: Annotated[str, Field(max_length=10000)]
    expected_status: int = Field(200, ge=100, le=599)
    max_response_time_ms: float | None = Field(None, gt=0)
    timeout_seconds: float | None = Field(None, gt=0)
    verify_ssl: bool = True
    _url_required = field_validator("url")(clean_required)


class HealthCheckResult(BaseModel):
    status: ExecutionStatus
    status_code: int | None
    response_time_ms: float
    response_size: int
    redirects: int
    content_type: str | None
    error_message: str | None
    assertions: list[AssertionResultOut]


class ApiAnalytics(BaseModel):
    total_api_requests: int
    total_runs: int
    pass_rate: float
    failure_rate: float
    average_response_time_ms: float
    slowest_endpoint: str | None


class BugFromResultCreate(BugCreate):
    pass
