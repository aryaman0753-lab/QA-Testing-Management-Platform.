import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.database import get_db
from app.database.models.user import User
from app.users.schemas import UserPublic
from app.users.service import get_user_or_404, list_users

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserPublic)
def read_own_profile(current_user: User = Depends(get_current_user)) -> UserPublic:
    return UserPublic.model_validate(current_user)


@router.get("", response_model=list[UserPublic])
def list_all_users(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    # Any authenticated user (not just ADMIN) can browse the directory - this
    # is what lets a project OWNER who isn't a system ADMIN pick someone to
    # add as a project member. See README "Architecture Decisions".
    _current_user: User = Depends(get_current_user),
) -> list[UserPublic]:
    users = list_users(db, limit=limit, offset=offset)
    return [UserPublic.model_validate(user) for user in users]


@router.get("/{user_id}", response_model=UserPublic)
def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> UserPublic:
    user = get_user_or_404(db, user_id)
    return UserPublic.model_validate(user)
