import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.api_testing.schemas import RequestCreate, clean_required
from app.database.models.automation import AutomationStepType, SuiteStatus

Name = Annotated[str, Field(min_length=1, max_length=255)]


class SuiteCreate(BaseModel):
    name: Name
    description: str | None = Field(None, max_length=10000)
    environment_id: uuid.UUID | None = None
    status: SuiteStatus = SuiteStatus.DRAFT
    auto_create_bugs: bool = False
    max_retries: int = Field(0, ge=0, le=3)
    allowed_hosts: list[str] = Field(default_factory=list, max_length=100)
    _name_required = field_validator("name")(clean_required)

    @field_validator("allowed_hosts")
    @classmethod
    def hosts(cls, values):
        import re
        result = []
        for value in values:
            value = value.strip().lower().rstrip(".")
            if not re.fullmatch(r"(?:\*\.)?[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", value) or ".." in value:
                raise ValueError("Allowed hosts must be hostnames, optionally prefixed with '*.'.")
            if value not in result:
                result.append(value)
        return result


class SuiteUpdate(BaseModel):
    name: Name | None = None
    description: str | None = Field(None, max_length=10000)
    environment_id: uuid.UUID | None = None
    status: SuiteStatus | None = None
    auto_create_bugs: bool | None = None
    max_retries: int | None = Field(None, ge=0, le=3)
    allowed_hosts: list[str] | None = Field(None, max_length=100)


class CaseCreate(BaseModel):
    name: Name
    description: str | None = Field(None, max_length=10000)
    order_index: int = Field(0, ge=0)
    enabled: bool = True
    timeout: float = Field(60, gt=0, le=3600)
    _name_required = field_validator("name")(clean_required)


class CaseUpdate(BaseModel):
    name: Name | None = None
    description: str | None = Field(None, max_length=10000)
    order_index: int | None = Field(None, ge=0)
    enabled: bool | None = None
    timeout: float | None = Field(None, gt=0, le=3600)


class ConditionInput(BaseModel):
    source: Literal["STATUS_CODE", "VARIABLE", "JSON_PATH", "HEADER"]
    operator: Literal["EQUALS", "NOT_EQUALS", "CONTAINS", "EXISTS"]
    target: str | None = Field(None, max_length=500)
    expected: str | None = Field(None, max_length=10000)


class AssertionInput(BaseModel):
    source: Literal["STATUS_CODE", "BODY", "JSON_PATH", "HEADER", "RESPONSE_TIME"]
    operator: Literal["EQUALS", "NOT_EQUALS", "GREATER_THAN", "LESS_THAN", "CONTAINS", "NOT_CONTAINS", "EXISTS"]
    target: str | None = Field(None, max_length=500)
    expected: str | None = Field(None, max_length=10000)


class AssertionConfig(BaseModel):
    assertions: list[AssertionInput] = Field(min_length=1, max_length=100)


class ExtractionConfig(BaseModel):
    source: Literal["JSON_PATH", "HEADER"]
    path: str = Field(min_length=1, max_length=500)
    variable_name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,99}$")
    is_secret: bool = False
    strip_prefix: str | None = Field(None, max_length=100)


class VariableConfig(BaseModel):
    variable_name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,99}$")
    value: str = Field(default="", max_length=10000)
    is_secret: bool = False


class DelayConfig(BaseModel):
    seconds: float = Field(ge=0, le=60)


class StepCreate(BaseModel):
    name: Name
    step_type: AutomationStepType
    order_index: int = Field(0, ge=0)
    enabled: bool = True
    api_request_id: uuid.UUID | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    condition: ConditionInput | None = None
    _name_required = field_validator("name")(clean_required)

    @model_validator(mode="after")
    def validate_config(self):
        schemas = {"ASSERTION": AssertionConfig, "EXTRACT_VARIABLE": ExtractionConfig,
                   "SET_VARIABLE": VariableConfig, "DELAY": DelayConfig, "CONDITION": ConditionInput}
        if self.step_type == "HTTP_REQUEST":
            if self.api_request_id:
                self.config = {}
            else:
                self.config = {"request": RequestCreate.model_validate(self.config.get("request", {})).model_dump(mode="json")}
        else:
            if self.api_request_id:
                raise ValueError("Only HTTP steps may reference API requests.")
            self.config = schemas[self.step_type].model_validate(self.config).model_dump(mode="json")
        return self


class StepUpdate(BaseModel):
    name: Name | None = None
    step_type: AutomationStepType | None = None
    order_index: int | None = Field(None, ge=0)
    enabled: bool | None = None
    api_request_id: uuid.UUID | None = None
    config: dict[str, Any] | None = None
    condition: ConditionInput | None = None


class StepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    case_id: uuid.UUID
    name: str
    step_type: str
    order_index: int
    enabled: bool
    api_request_id: uuid.UUID | None
    config: dict
    condition: dict | None
    created_at: datetime
    updated_at: datetime


class CaseOut(CaseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    suite_id: uuid.UUID
    steps: list[StepOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SuiteOut(SuiteCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    cases: list[CaseOut] = Field(default_factory=list)


class ReorderInput(BaseModel):
    ids: list[uuid.UUID] = Field(max_length=1000)


class StartRunInput(BaseModel):
    environment_id: uuid.UUID | None = None
    confirm_production: bool = False


class StepResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    run_id: uuid.UUID
    case_id: uuid.UUID | None
    step_id: uuid.UUID | None
    case_name: str
    step_name: str
    step_type: str
    order_index: int
    status: str
    attempt: int
    is_final: bool
    request_method: str | None
    resolved_url: str | None
    status_code: int | None
    response_time_ms: float | None
    assertions: list[dict]
    extracted_variables: dict
    error_message: str | None
    error_kind: str | None
    started_at: datetime
    completed_at: datetime | None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    suite_id: uuid.UUID
    suite_name: str | None = None
    environment_id: uuid.UUID | None
    environment_name: str | None = None
    status: str
    triggered_by: uuid.UUID
    trigger_type: str
    schedule_id: uuid.UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: float
    total_cases: int
    passed_cases: int
    failed_cases: int
    skipped_cases: int
    total_steps: int
    passed_steps: int
    failed_steps: int
    skipped_steps: int
    created_at: datetime
    stop_requested: bool
    error_message: str | None


class RunDetail(RunOut):
    results: list[StepResultOut]
    linked_bugs: list[dict] = Field(default_factory=list)


class ScheduleCreate(BaseModel):
    suite_id: uuid.UUID
    environment_id: uuid.UUID | None = None
    cron_expression: str = Field(min_length=1, max_length=100)
    timezone: str = Field(default="UTC", max_length=100)
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    environment_id: uuid.UUID | None = None
    cron_expression: str | None = Field(None, min_length=1, max_length=100)
    timezone: str | None = Field(None, max_length=100)
    enabled: bool | None = None


class ScheduleOut(ScheduleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_error: str | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class Page(BaseModel):
    items: list[Any]
    page: int
    page_size: int
    total: int
    total_pages: int
