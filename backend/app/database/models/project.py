import enum
import uuid
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.models.guid import GUID

if TYPE_CHECKING:
    from app.database.models.bug import Bug
    from app.database.models.user import User
    from app.database.models.project_member import ProjectMember


class ProjectStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key: Mapped[str] = mapped_column(String(10), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status", native_enum=False, length=16),
        nullable=False,
        default=ProjectStatus.ACTIVE,
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    next_bug_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_api_run_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_load_run_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    load_allowlist_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    load_allowed_hosts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    creator: Mapped["User"] = relationship(back_populates="created_projects")
    members: Mapped[List["ProjectMember"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    bugs: Mapped[List["Bug"]] = relationship(back_populates="project", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Project id={self.id} key={self.key!r} status={self.status}>"
