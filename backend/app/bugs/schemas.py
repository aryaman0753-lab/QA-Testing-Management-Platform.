import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.database.models.bug import BugPriority, BugSeverity, BugStatus


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    full_name: str
    email: str


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    key: str


def _clean_required(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Field cannot be blank.")
    return value


class BugCreate(BaseModel):
    title: Annotated[str, Field(max_length=500)]
    description: Annotated[str, Field(max_length=50000)]
    steps_to_reproduce: list[Annotated[str, Field(max_length=2000)]] = Field(default_factory=list, max_length=100)
    expected_result: Annotated[str | None, Field(max_length=50000)] = None
    actual_result: Annotated[str | None, Field(max_length=50000)] = None
    severity: BugSeverity
    priority: BugPriority
    environment: Annotated[str | None, Field(max_length=100)] = None
    browser: Annotated[str | None, Field(max_length=100)] = None
    operating_system: Annotated[str | None, Field(max_length=100)] = None
    device: Annotated[str | None, Field(max_length=100)] = None
    assigned_to: uuid.UUID | None = None

    _title_required = field_validator("title")(_clean_required)
    _description_required = field_validator("description")(_clean_required)

    @field_validator("steps_to_reproduce")
    @classmethod
    def clean_steps(cls, value: list[str]) -> list[str]:
        return [step.strip() for step in value if step.strip()]


class BugUpdate(BaseModel):
    title: Annotated[str | None, Field(max_length=500)] = None
    description: Annotated[str | None, Field(max_length=50000)] = None
    steps_to_reproduce: list[Annotated[str, Field(max_length=2000)]] | None = Field(None, max_length=100)
    expected_result: Annotated[str | None, Field(max_length=50000)] = None
    actual_result: Annotated[str | None, Field(max_length=50000)] = None
    severity: BugSeverity | None = None
    priority: BugPriority | None = None
    environment: Annotated[str | None, Field(max_length=100)] = None
    browser: Annotated[str | None, Field(max_length=100)] = None
    operating_system: Annotated[str | None, Field(max_length=100)] = None
    device: Annotated[str | None, Field(max_length=100)] = None

    @field_validator("title", "description")
    @classmethod
    def required_if_set(cls, value: str | None) -> str | None:
        return _clean_required(value) if value is not None else value

    @field_validator("steps_to_reproduce")
    @classmethod
    def clean_optional_steps(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else [step.strip() for step in value if step.strip()]


class AssigneeUpdate(BaseModel):
    assigned_to: uuid.UUID | None


class StatusUpdate(BaseModel):
    status: BugStatus


class CommentCreate(BaseModel):
    comment: Annotated[str, Field(max_length=10000)]
    _comment_required = field_validator("comment")(_clean_required)


class CommentUpdate(CommentCreate):
    pass


class BugCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    bug_id: uuid.UUID
    user_id: uuid.UUID
    comment: str
    created_at: datetime
    updated_at: datetime
    user: UserSummary


class BugHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    bug_id: uuid.UUID
    user_id: uuid.UUID
    action: str
    field_name: str | None
    old_value: str | None
    new_value: str | None
    created_at: datetime
    user: UserSummary


class BugAttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    bug_id: uuid.UUID
    uploaded_by: uuid.UUID
    file_name: str
    file_size: int
    mime_type: str
    created_at: datetime
    uploader: UserSummary
    download_url: str


class BugListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    bug_number: int
    bug_key: str
    title: str
    severity: BugSeverity
    priority: BugPriority
    status: BugStatus
    environment: str | None
    reported_by: uuid.UUID
    assigned_to: uuid.UUID | None
    reporter: UserSummary
    assignee: UserSummary | None
    created_at: datetime
    updated_at: datetime


class ApiTestSourceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    test_run_id: uuid.UUID
    request_name: str
    method: str
    resolved_url: str


class LoadTestSourceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    load_test_id: uuid.UUID
    run_key: str
    threshold_results: list[dict]


class AutomationSourceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    suite_id: uuid.UUID
    status: str


class AutomationStepSourceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    case_id: uuid.UUID | None
    step_id: uuid.UUID | None
    case_name: str
    step_name: str
    assertions: list[dict]


class BugDetail(BugListItem):
    description: str
    steps_to_reproduce: list[str]
    expected_result: str | None
    actual_result: str | None
    browser: str | None
    operating_system: str | None
    device: str | None
    resolved_at: datetime | None
    closed_at: datetime | None
    project: ProjectSummary
    comments: list[BugCommentOut]
    attachments: list[BugAttachmentOut]
    history: list[BugHistoryOut]
    discovered_from_test_result_id: uuid.UUID | None
    discovered_from_test_result: ApiTestSourceSummary | None
    discovered_from_load_test_run_id: uuid.UUID | None
    discovered_from_load_test_run: LoadTestSourceSummary | None
    discovered_from_automation_run_id: uuid.UUID | None
    discovered_from_automation_step_result_id: uuid.UUID | None
    discovered_from_automation_run: AutomationSourceSummary | None
    discovered_from_automation_step_result: AutomationStepSourceSummary | None


class PaginatedBugs(BaseModel):
    items: list[BugListItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class TimePoint(BaseModel):
    date: date
    count: int


class BugAnalytics(BaseModel):
    total: int
    open: int
    critical: int
    high_priority: int
    by_status: dict[str, int]
    by_severity: dict[str, int]
    by_priority: dict[str, int]
    created_over_time: list[TimePoint]


SortField = Literal["created_at", "updated_at", "priority", "severity", "status", "bug_number"]
SortOrder = Literal["asc", "desc"]
