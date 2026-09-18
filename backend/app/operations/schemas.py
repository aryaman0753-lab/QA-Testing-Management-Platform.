import uuid
import json
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


WEBHOOK_EVENTS = {
    "automation.run.started", "automation.run.completed", "automation.run.failed",
    "load_test.completed", "load_test.failed", "bug.created", "bug.updated",
}


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    expires_at: datetime | None = None


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    token_prefix: str
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreated(ApiKeyOut):
    token: str = Field(description="Shown once. Store it in the CI provider secret store.")


class CiRunCreate(BaseModel):
    model_config = {"json_schema_extra": {"examples": [{"project": "SHOP", "suite": "smoke-tests", "environment": "staging", "commit_sha": "abc123", "branch": "main", "build_number": "42", "ci_provider": "github", "metadata": {"pull_request": 17}}]}}
    project: str | None = Field(default=None, max_length=255)
    suite: str = Field(min_length=1, max_length=255)
    environment: str | None = Field(default=None, max_length=255)
    commit_sha: str | None = Field(default=None, max_length=100)
    branch: str | None = Field(default=None, max_length=255)
    build_number: str | None = Field(default=None, max_length=100)
    ci_provider: str = Field(default="generic", min_length=1, max_length=40)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def safe_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(value, default=str)
        if len(encoded.encode()) > 16_384:
            raise ValueError("CI metadata cannot exceed 16 KB.")
        sensitive = {"password", "secret", "token", "authorization", "cookie", "api_key", "api-key"}
        def keys(item):
            if isinstance(item, dict):
                for key, nested in item.items():
                    yield str(key).lower(); yield from keys(nested)
            elif isinstance(item, list):
                for nested in item: yield from keys(nested)
        if any(key in sensitive or any(word in key for word in ("password", "secret", "token")) for key in keys(value)):
            raise ValueError("CI metadata cannot contain credential-like fields.")
        return value


class CiRunOut(BaseModel):
    run_id: uuid.UUID
    status: str
    tracking_url: str


class WebhookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=8, max_length=2048)
    secret: str = Field(min_length=16, max_length=512, description="Shared signing secret. Write-only and never returned.")
    events: list[str] = Field(min_length=1)
    enabled: bool = True

    @field_validator("events")
    @classmethod
    def validate_events(cls, value: list[str]) -> list[str]:
        invalid = set(value) - WEBHOOK_EVENTS
        if invalid:
            raise ValueError(f"Unsupported webhook events: {', '.join(sorted(invalid))}")
        return list(dict.fromkeys(value))


class WebhookUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    url: str | None = Field(default=None, min_length=8, max_length=2048)
    secret: str | None = Field(default=None, min_length=16, max_length=512)
    events: list[str] | None = None
    enabled: bool | None = None

    @field_validator("events")
    @classmethod
    def validate_events(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and (not value or set(value) - WEBHOOK_EVENTS):
            raise ValueError("At least one supported webhook event is required.")
        return list(dict.fromkeys(value)) if value is not None else None


class WebhookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    url: str
    events: list[str]
    enabled: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class DeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    webhook_id: uuid.UUID
    project_id: uuid.UUID
    event: str
    event_id: str
    status: str
    attempt_count: int
    response_status: int | None
    failure_reason: str | None
    last_attempt_at: datetime | None
    next_retry_at: datetime | None
    created_at: datetime
    completed_at: datetime | None


class PreferenceInput(BaseModel):
    project_id: uuid.UUID | None = None
    in_app_enabled: bool = True
    email_enabled: bool = False
    webhook_enabled: bool = True
    events: list[str] = Field(default_factory=list)

    @field_validator("events")
    @classmethod
    def validate_events(cls, value: list[str]) -> list[str]:
        invalid = set(value) - WEBHOOK_EVENTS
        if invalid:
            raise ValueError(f"Unsupported notification events: {', '.join(sorted(invalid))}")
        return list(dict.fromkeys(value))


class PreferenceOut(PreferenceInput):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID | None
    event: str
    title: str
    message: str
    link: str | None
    is_read: bool
    email_status: str
    created_at: datetime
    read_at: datetime | None


class ReportFilters(BaseModel):
    environment_id: uuid.UUID | None = None
    date_from: date | None = None
    date_to: date | None = None


class ReportRequest(ReportFilters):
    format: Literal["json", "csv", "pdf"] = "json"
