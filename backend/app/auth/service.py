from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.schemas import RegisterRequest
from app.common.exceptions import ConflictError, UnauthorizedError
from app.core.logging import get_logger
from app.core.security import create_access_token, hash_password, verify_password
from app.database.models.user import User, UserRole

logger = get_logger(__name__)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    normalized = normalize_email(email)
    return db.scalar(select(User).where(User.email == normalized))


def register_user(db: Session, payload: RegisterRequest, role: UserRole = UserRole.QA_ENGINEER) -> User:
    email = normalize_email(payload.email)
    if get_user_by_email(db, email) is not None:
        logger.warning("Registration attempted with existing email: %s", email)
        raise ConflictError("An account with this email already exists.")

    user = User(
        full_name=payload.full_name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("New user registered: %s", user.id)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        logger.warning("Failed login attempt for email: %s", normalize_email(email))
        raise UnauthorizedError("Incorrect email or password.")
    if not user.is_active:
        logger.warning("Login attempt for deactivated account: %s", user.id)
        raise UnauthorizedError("This account has been deactivated.")
    return user


def issue_token_for_user(user: User) -> str:
    return create_access_token(subject=user.id)
