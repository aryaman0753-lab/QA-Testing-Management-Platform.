import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, List

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.models.guid import GUID

if TYPE_CHECKING:
    from app.database.models.api_testing import ApiTestResult
    from app.database.models.project import Project
    from app.database.models.user import User


class BugSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    TRIVIAL = "TRIVIAL"


class BugPriority(str, enum.Enum):
    URGENT = "URGENT"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class BugStatus(str, enum.Enum):
    NEW = "NEW"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    FIXED = "FIXED"
    QA_VERIFICATION = "QA_VERIFICATION"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"
    DUPLICATE = "DUPLICATE"
    WONT_FIX = "WONT_FIX"


class Bug(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bugs"
    __table_args__ = (
        UniqueConstraint("project_id", "bug_number", name="uq_bug_project_number"),
        Index("ix_bugs_project_status", "project_id", "status"),
        Index("ix_bugs_project_created", "project_id", "created_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bug_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    steps_to_reproduce: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    expected_result: Mapped[str | None] = mapped_column(Text)
    actual_result: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[BugSeverity] = mapped_column(
        Enum(BugSeverity, name="bug_severity", native_enum=False, length=16), nullable=False, index=True
    )
    priority: Mapped[BugPriority] = mapped_column(
        Enum(BugPriority, name="bug_priority", native_enum=False, length=16), nullable=False, index=True
    )
    status: Mapped[BugStatus] = mapped_column(
        Enum(BugStatus, name="bug_status", native_enum=False, length=24),
        nullable=False,
        default=BugStatus.NEW,
        index=True,
    )
    environment: Mapped[str | None] = mapped_column(String(100))
    browser: Mapped[str | None] = mapped_column(String(100))
    operating_system: Mapped[str | None] = mapped_column(String(100))
    device: Mapped[str | None] = mapped_column(String(100))
    reported_by: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    discovered_from_test_result_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("api_test_results.id", ondelete="SET NULL"), nullable=True, index=True
    )

    project: Mapped["Project"] = relationship(back_populates="bugs")
    reporter: Mapped["User"] = relationship(foreign_keys=[reported_by])
    assignee: Mapped["User | None"] = relationship(foreign_keys=[assigned_to])
    comments: Mapped[List["BugComment"]] = relationship(back_populates="bug", cascade="all, delete-orphan")
    history: Mapped[List["BugHistory"]] = relationship(back_populates="bug", cascade="all, delete-orphan")
    attachments: Mapped[List["BugAttachment"]] = relationship(back_populates="bug", cascade="all, delete-orphan")
    discovered_from_test_result: Mapped["ApiTestResult | None"] = relationship(foreign_keys=[discovered_from_test_result_id])

    @property
    def bug_key(self) -> str:
        return f"{self.project.key}-{self.bug_number:03d}"


class BugComment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bug_comments"

    bug_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("bugs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    bug: Mapped["Bug"] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship()


class BugHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "bug_history"

    bug_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("bugs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(100))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bug: Mapped["Bug"] = relationship(back_populates="history")
    user: Mapped["User"] = relationship()


class BugAttachment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "bug_attachments"

    bug_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("bugs.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bug: Mapped["Bug"] = relationship(back_populates="attachments")
    uploader: Mapped["User"] = relationship()

    @property
    def download_url(self) -> str:
        return f"/api/v1/bug-attachments/{self.id}/download"
