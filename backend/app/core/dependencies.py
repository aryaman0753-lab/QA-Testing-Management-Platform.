"""Shared FastAPI dependencies: DB session, current user, role guards.

Every module that needs "who is calling this endpoint" or "is this endpoint
restricted to a role" imports from here instead of re-implementing token
parsing, which is what keeps authorization logic in one place as new
modules (bugs, api testing, ...) get added.
"""
from typing import Iterable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.common.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import InvalidTokenError, decode_access_token
from app.database.database import get_db
from app.database.models.user import User, UserRole

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise UnauthorizedError("Missing bearer token.")

    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise UnauthorizedError("Invalid or expired token.") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("User no longer exists or is inactive.")

    return user


def require_roles(*roles: UserRole):
    """Dependency factory restricting an endpoint to specific system roles."""

    allowed: set[UserRole] = set(roles)

    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise ForbiddenError("You do not have the required role for this action.")
        return current_user

    return _dependency


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Administrator privileges are required.")
    return current_user
