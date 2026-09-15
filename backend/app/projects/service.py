"""Project and project-membership business logic.

Authorization model (Phase 1):
  - System role ADMIN can see/manage every project regardless of membership.
  - System roles ADMIN and QA_ENGINEER may create new projects; the creator
    is automatically added as that project's OWNER.
  - Within a project, the OWNER project-role can update the project,
    archive it, and manage membership. MEMBER/VIEWER can only read.
  - A user must be a member of a project (or a system ADMIN) to see it at
    all; non-members get 404 rather than 403 so project existence isn't
    leaked to outsiders.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.common.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.database.models.project import Project, ProjectStatus
from app.database.models.project_member import ProjectMember, ProjectRole
from app.database.models.user import User, UserRole
from app.projects.schemas import ProjectCreate, ProjectMemberCreate, ProjectUpdate

logger = get_logger(__name__)

_PROJECT_CREATOR_ROLES = {UserRole.ADMIN, UserRole.QA_ENGINEER}


def _is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


def get_membership(db: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> ProjectMember | None:
    stmt = select(ProjectMember).where(
        ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
    )
    return db.scalar(stmt)


def _get_project_or_404(db: Session, project_id: uuid.UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found.")
    return project


def get_project_for_read(db: Session, project_id: uuid.UUID, current_user: User) -> Project:
    project = _get_project_or_404(db, project_id)
    if _is_admin(current_user):
        return project
    if get_membership(db, project_id, current_user.id) is None:
        # Do not leak existence of a project the user cannot access.
        raise NotFoundError("Project not found.")
    return project


def _get_project_for_management(db: Session, project_id: uuid.UUID, current_user: User) -> Project:
    project = get_project_for_read(db, project_id, current_user)
    if _is_admin(current_user):
        return project
    membership = get_membership(db, project_id, current_user.id)
    if membership is None or membership.project_role != ProjectRole.OWNER:
        raise ForbiddenError("Only the project owner or an administrator can perform this action.")
    return project


def create_project(db: Session, payload: ProjectCreate, current_user: User) -> Project:
    if current_user.role not in _PROJECT_CREATOR_ROLES and not _is_admin(current_user):
        raise ForbiddenError("Only administrators and QA engineers can create projects.")

    existing = db.scalar(select(Project).where(Project.key == payload.key))
    if existing is not None:
        raise ConflictError(f"A project with key '{payload.key}' already exists.")

    project = Project(
        name=payload.name,
        key=payload.key,
        description=payload.description,
        created_by=current_user.id,
    )
    db.add(project)
    db.flush()

    owner_membership = ProjectMember(
        project_id=project.id, user_id=current_user.id, project_role=ProjectRole.OWNER
    )
    db.add(owner_membership)
    db.commit()
    db.refresh(project)
    logger.info("Project created: %s (%s) by user %s", project.key, project.id, current_user.id)
    return project


def list_projects_for_user(db: Session, current_user: User, limit: int = 100, offset: int = 0) -> list[Project]:
    if _is_admin(current_user):
        stmt = select(Project).order_by(Project.created_at.desc()).limit(limit).offset(offset)
        return list(db.scalars(stmt))

    stmt = (
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == current_user.id)
        .order_by(Project.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))


def update_project(db: Session, project_id: uuid.UUID, payload: ProjectUpdate, current_user: User) -> Project:
    project = _get_project_for_management(db, project_id, current_user)

    if payload.name is not None:
        project.name = payload.name
    if payload.description is not None:
        project.description = payload.description
    if payload.status is not None:
        project.status = payload.status

    db.commit()
    db.refresh(project)
    logger.info("Project updated: %s by user %s", project.id, current_user.id)
    return project


def archive_project(db: Session, project_id: uuid.UUID, current_user: User) -> Project:
    project = _get_project_for_management(db, project_id, current_user)
    project.status = ProjectStatus.ARCHIVED
    db.commit()
    db.refresh(project)
    logger.info("Project archived: %s by user %s", project.id, current_user.id)
    return project


# --- Membership -----------------------------------------------------------


def list_members(db: Session, project_id: uuid.UUID, current_user: User) -> list[ProjectMember]:
    get_project_for_read(db, project_id, current_user)
    stmt = (
        select(ProjectMember)
        .options(joinedload(ProjectMember.user))
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.created_at.asc())
    )
    return list(db.scalars(stmt))


def add_member(
    db: Session, project_id: uuid.UUID, payload: ProjectMemberCreate, current_user: User
) -> ProjectMember:
    _get_project_for_management(db, project_id, current_user)

    target_user = db.get(User, payload.user_id)
    if target_user is None:
        raise NotFoundError("User not found.")

    if get_membership(db, project_id, payload.user_id) is not None:
        raise ConflictError("User is already a member of this project.")

    membership = ProjectMember(
        project_id=project_id, user_id=payload.user_id, project_role=payload.project_role
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    logger.info("User %s added to project %s as %s", payload.user_id, project_id, payload.project_role)
    return membership


def remove_member(db: Session, project_id: uuid.UUID, user_id: uuid.UUID, current_user: User) -> None:
    _get_project_for_management(db, project_id, current_user)

    membership = get_membership(db, project_id, user_id)
    if membership is None:
        raise NotFoundError("This user is not a member of the project.")

    if membership.project_role == ProjectRole.OWNER:
        owners = list(
            db.scalars(
                select(ProjectMember).where(
                    ProjectMember.project_id == project_id,
                    ProjectMember.project_role == ProjectRole.OWNER,
                )
            )
        )
        if len(owners) <= 1:
            raise ConflictError("Cannot remove the last remaining owner of a project.")

    db.delete(membership)
    db.commit()
    logger.info("User %s removed from project %s by %s", user_id, project_id, current_user.id)
