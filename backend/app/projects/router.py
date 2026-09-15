import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.database import get_db
from app.database.models.user import User
from app.projects.schemas import (
    ProjectCreate,
    ProjectMemberCreate,
    ProjectMemberOut,
    ProjectOut,
    ProjectUpdate,
)
from app.projects.service import (
    add_member,
    archive_project,
    create_project,
    get_project_for_read,
    list_members,
    list_projects_for_user,
    remove_member,
    update_project,
)

router = APIRouter(prefix="/projects", tags=["Projects"])
members_router = APIRouter(prefix="/projects/{project_id}/members", tags=["Project Members"])


@router.post("", response_model=ProjectOut, status_code=201)
def create_project_endpoint(
    payload: ProjectCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ProjectOut:
    project = create_project(db, payload, current_user)
    return ProjectOut.model_validate(project)


@router.get("", response_model=list[ProjectOut])
def list_projects_endpoint(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProjectOut]:
    projects = list_projects_for_user(db, current_user, limit=limit, offset=offset)
    return [ProjectOut.model_validate(project) for project in projects]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project_endpoint(
    project_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ProjectOut:
    project = get_project_for_read(db, project_id, current_user)
    return ProjectOut.model_validate(project)


@router.put("/{project_id}", response_model=ProjectOut)
def update_project_endpoint(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectOut:
    project = update_project(db, project_id, payload, current_user)
    return ProjectOut.model_validate(project)


@router.delete("/{project_id}", response_model=ProjectOut)
def archive_project_endpoint(
    project_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ProjectOut:
    """Archives the project rather than deleting it (see service docstring)."""
    project = archive_project(db, project_id, current_user)
    return ProjectOut.model_validate(project)


@members_router.post("", response_model=ProjectMemberOut, status_code=201)
def add_member_endpoint(
    project_id: uuid.UUID,
    payload: ProjectMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectMemberOut:
    membership = add_member(db, project_id, payload, current_user)
    return ProjectMemberOut.model_validate(membership)


@members_router.get("", response_model=list[ProjectMemberOut])
def list_members_endpoint(
    project_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[ProjectMemberOut]:
    memberships = list_members(db, project_id, current_user)
    return [ProjectMemberOut.model_validate(m) for m in memberships]


@members_router.delete("/{user_id}", status_code=204)
def remove_member_endpoint(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    remove_member(db, project_id, user_id, current_user)
