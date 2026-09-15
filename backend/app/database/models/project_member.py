import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, UUIDPrimaryKeyMixin, utcnow
from app.database.models.guid import GUID

if TYPE_CHECKING:
    from app.database.models.project import Project
    from app.database.models.user import User


class ProjectRole(str, enum.Enum):
    OWNER = "OWNER"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


class ProjectMember(UUIDPrimaryKeyMixin, Base):
    """The many-to-many link between users and projects.

    Kept as an explicit entity (rather than a plain association table) so it
    can carry a per-project role today and additional fields later (e.g.
    notification preferences) without a migration that changes its shape.
    """

    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_member"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_role: Mapped[ProjectRole] = mapped_column(
        Enum(ProjectRole, name="project_role", native_enum=False, length=16),
        nullable=False,
        default=ProjectRole.MEMBER,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="project_memberships")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProjectMember project_id={self.project_id} user_id={self.user_id} role={self.project_role}>"
