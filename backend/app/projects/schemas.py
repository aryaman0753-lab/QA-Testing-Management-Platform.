import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.database.models.project import ProjectStatus
from app.database.models.project_member import ProjectRole
from app.users.schemas import UserPublic

_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")


def normalize_project_key(raw_key: str) -> str:
    key = raw_key.strip().upper()
    if not _KEY_PATTERN.match(key):
        raise ValueError(
            "Project key must be 2-10 characters, start with a letter, and contain only "
            "letters and digits (e.g. 'ECOM'). Lowercase letters are automatically uppercased."
        )
    return key


class ProjectCreate(BaseModel):
    name: str
    key: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name is required.")
        return value

    @field_validator("key")
    @classmethod
    def key_valid(cls, value: str) -> str:
        return normalize_project_key(value)


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: ProjectStatus | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Project name cannot be blank.")
        return value


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    key: str
    description: str | None
    status: ProjectStatus
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ProjectMemberCreate(BaseModel):
    user_id: uuid.UUID
    project_role: ProjectRole = ProjectRole.MEMBER


class ProjectMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    project_role: ProjectRole
    created_at: datetime
    user: UserPublic
