import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api_testing.secrets import encrypt
from app.automation.schemas import StartRunInput
from app.automation.service import create_run
from app.common.exceptions import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError, ValidationAppError
from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.models.api_testing import ApiEnvironment
from app.database.models.automation import AutomationRun, AutomationTestSuite
from app.database.models.operations import CiTestExecution, Notification, NotificationPreference, ProjectApiKey, Webhook, WebhookDelivery
from app.database.models.project import Project
from app.database.models.project_member import ProjectMember, ProjectRole
from app.database.models.user import User, UserRole
from app.projects.service import get_membership, get_project_for_read

logger = get_logger(__name__)


def now() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _manage_project(db: Session, project_id: uuid.UUID, user: User) -> Project:
    project = get_project_for_read(db, project_id, user)
    membership = get_membership(db, project_id, user.id)
    if user.role != UserRole.ADMIN and (membership is None or membership.project_role != ProjectRole.OWNER):
        raise ForbiddenError("Only a project owner or administrator can manage integrations.")
    return project


def create_api_key(db: Session, project_id: uuid.UUID, payload, user: User):
    _manage_project(db, project_id, user)
    settings = get_settings()
    active = db.scalar(select(func.count(ProjectApiKey.id)).where(ProjectApiKey.project_id == project_id, ProjectApiKey.revoked_at.is_(None))) or 0
    if active >= settings.CI_API_KEYS_PER_PROJECT:
        raise ConflictError("The project API-key limit has been reached.")
    expires_at = aware(payload.expires_at)
    if expires_at and expires_at <= now():
        raise ValidationAppError("API-key expiration must be in the future.")
    plain = f"qh_{secrets.token_urlsafe(32)}"
    row = ProjectApiKey(project_id=project_id, name=payload.name, token_prefix=plain[:12], token_hash=token_hash(plain), scopes=["ci:run"], created_by=user.id, expires_at=expires_at)
    db.add(row); db.commit(); db.refresh(row)
    logger.info("project_api_key_created", extra={"user_id": str(user.id), "project_id": str(project_id), "status": "created"})
    return row, plain


def list_api_keys(db: Session, project_id: uuid.UUID, user: User):
    _manage_project(db, project_id, user)
    return list(db.scalars(select(ProjectApiKey).where(ProjectApiKey.project_id == project_id).order_by(ProjectApiKey.created_at.desc())))


def revoke_api_key(db: Session, project_id: uuid.UUID, key_id: uuid.UUID, user: User):
    _manage_project(db, project_id, user)
    row = db.get(ProjectApiKey, key_id)
    if row is None or row.project_id != project_id:
        raise NotFoundError("API key not found.")
    row.revoked_at = now(); db.commit()


def authenticate_api_key(db: Session, token: str | None) -> ProjectApiKey:
    if not token or not token.startswith("qh_"):
        raise UnauthorizedError("A valid QAHub project API key is required.")
    row = db.scalar(select(ProjectApiKey).where(ProjectApiKey.token_hash == token_hash(token)))
    if row is None or row.revoked_at is not None or (row.expires_at and aware(row.expires_at) <= now()) or "ci:run" not in row.scopes:
        raise UnauthorizedError("The project API key is invalid, expired, or revoked.")
    row.last_used_at = now()
    return row


def _id(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None


def trigger_ci_run(db: Session, api_key: ProjectApiKey, payload):
    project = db.get(Project, api_key.project_id)
    if project is None:
        raise UnauthorizedError("The project API key is no longer valid.")
    if payload.project and payload.project not in {str(project.id), project.key, project.name}:
        raise NotFoundError("Project does not match this API key.")
    suite_id = _id(payload.suite)
    suite = db.scalar(select(AutomationTestSuite).where(AutomationTestSuite.project_id == project.id, or_(AutomationTestSuite.id == suite_id, AutomationTestSuite.name == payload.suite)))
    if suite is None:
        raise NotFoundError("Automation suite not found in this project.")
    environment = None
    if payload.environment:
        environment_id = _id(payload.environment)
        environment = db.scalar(select(ApiEnvironment).where(ApiEnvironment.project_id == project.id, or_(ApiEnvironment.id == environment_id, ApiEnvironment.name == payload.environment)))
        if environment is None:
            raise NotFoundError("Environment not found in this project.")
    actor = db.get(User, api_key.created_by)
    if actor is None or not actor.is_active:
        raise UnauthorizedError("The API key owner is inactive.")
    run = create_run(db, suite.id, StartRunInput(environment_id=environment.id if environment else None), actor, trigger_type="CI")
    execution = CiTestExecution(project_id=project.id, automation_run_id=run.id, api_key_id=api_key.id, provider=payload.ci_provider.lower(), commit_sha=payload.commit_sha, branch=payload.branch, build_number=payload.build_number, metadata_json=payload.metadata)
    db.add(execution); db.commit()
    logger.info("ci_automation_queued", extra={"user_id": str(actor.id), "project_id": str(project.id), "run_id": str(run.id), "status": run.status})
    return run


def ci_run_status(db: Session, api_key: ProjectApiKey, run_id: uuid.UUID) -> AutomationRun:
    row = db.get(AutomationRun, run_id)
    if row is None or row.project_id != api_key.project_id:
        raise NotFoundError("CI test run not found.")
    return row


def validate_webhook_url(value: str) -> str:
    parsed = urlsplit(value)
    host = (parsed.hostname or "").rstrip(".").lower()
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValidationAppError("Webhook URLs must use HTTPS and cannot include credentials, query strings, or fragments.")
    if host == "localhost" or host.endswith((".localhost", ".local")):
        raise ValidationAppError("Local webhook destinations are not allowed.")
    return value


def create_webhook(db: Session, project_id: uuid.UUID, payload, user: User) -> Webhook:
    _manage_project(db, project_id, user)
    row = Webhook(project_id=project_id, name=payload.name, url=validate_webhook_url(payload.url), secret_encrypted=encrypt(payload.secret), events=payload.events, enabled=payload.enabled, created_by=user.id)
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback(); raise ConflictError("A webhook with this name already exists.") from exc
    db.refresh(row)
    logger.info("webhook_created", extra={"user_id": str(user.id), "project_id": str(project_id), "status": "enabled" if row.enabled else "disabled"})
    return row


def list_webhooks(db: Session, project_id: uuid.UUID, user: User):
    get_project_for_read(db, project_id, user)
    return list(db.scalars(select(Webhook).where(Webhook.project_id == project_id).order_by(Webhook.created_at.desc())))


def update_webhook(db: Session, webhook_id: uuid.UUID, payload, user: User) -> Webhook:
    row = db.get(Webhook, webhook_id)
    if row is None:
        raise NotFoundError("Webhook not found.")
    _manage_project(db, row.project_id, user)
    values = payload.model_dump(exclude_unset=True)
    if "url" in values: values["url"] = validate_webhook_url(values["url"])
    secret = values.pop("secret", None)
    if secret: row.secret_encrypted = encrypt(secret)
    for key, value in values.items(): setattr(row, key, value)
    db.commit(); db.refresh(row); return row


def delete_webhook(db: Session, webhook_id: uuid.UUID, user: User):
    row = db.get(Webhook, webhook_id)
    if row is None: raise NotFoundError("Webhook not found.")
    _manage_project(db, row.project_id, user); db.delete(row); db.commit()


def list_deliveries(db: Session, project_id: uuid.UUID, user: User, limit: int = 100):
    get_project_for_read(db, project_id, user)
    return list(db.scalars(select(WebhookDelivery).where(WebhookDelivery.project_id == project_id).order_by(WebhookDelivery.created_at.desc()).limit(limit)))


def emit_event(db: Session, project_id: uuid.UUID, event: str, data: dict, *, event_id: str | None = None, title: str | None = None, message: str | None = None, link: str | None = None):
    """Persist fan-out atomically. Delivery workers perform all outbound I/O."""
    event_id = event_id or uuid.uuid4().hex
    safe_data = {key: value for key, value in data.items() if key.lower() not in {"secret", "token", "password", "authorization", "cookie"}}
    envelope = {"id": event_id, "event": event, "created_at": now().isoformat(), "project_id": str(project_id), "data": safe_data}
    member_ids = list(db.scalars(select(ProjectMember.user_id).where(ProjectMember.project_id == project_id)))
    preference_rows = list(db.scalars(select(NotificationPreference).where(NotificationPreference.user_id.in_(member_ids), or_(NotificationPreference.project_id == project_id, NotificationPreference.project_id.is_(None))))) if member_ids else []
    preferences = {user_id: None for user_id in member_ids}
    for pref in sorted(preference_rows, key=lambda item: item.project_id is not None):
        preferences[pref.user_id] = pref  # Project-specific preferences override global defaults.
    webhook_enabled = any(pref is None or (pref.webhook_enabled and (not pref.events or event in pref.events)) for pref in preferences.values())
    if webhook_enabled:
        hooks = db.scalars(select(Webhook).where(Webhook.project_id == project_id, Webhook.enabled.is_(True))).all()
        for hook in hooks:
            if event in hook.events:
                db.add(WebhookDelivery(webhook_id=hook.id, project_id=project_id, event=event, event_id=event_id, payload=envelope, status="PENDING", next_retry_at=now()))
    if title and message:
        for user_id in member_ids:
            pref = preferences[user_id]
            if pref and (not pref.in_app_enabled or (pref.events and event not in pref.events)):
                continue
            db.add(Notification(user_id=user_id, project_id=project_id, event=event, title=title, message=message, link=link, dedupe_key=f"{event}:{event_id}", email_status="PENDING" if pref and pref.email_enabled else "NOT_REQUESTED"))
    try:
        db.commit()
        logger.info("project_event_persisted", extra={"project_id": str(project_id), "job_id": event_id, "status": event})
    except IntegrityError:
        db.rollback()  # A duplicate notification/event is intentionally ignored.


def get_preferences(db: Session, user: User):
    return list(db.scalars(select(NotificationPreference).where(NotificationPreference.user_id == user.id).order_by(NotificationPreference.created_at)))


def upsert_preferences(db: Session, payload, user: User):
    if payload.project_id:
        get_project_for_read(db, payload.project_id, user)
    row = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user.id, NotificationPreference.project_id == payload.project_id))
    if row is None:
        row = NotificationPreference(user_id=user.id, **payload.model_dump()); db.add(row)
    else:
        for key, value in payload.model_dump(exclude={"project_id"}).items(): setattr(row, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user.id, NotificationPreference.project_id == payload.project_id))
        if row is None: raise
        for key, value in payload.model_dump(exclude={"project_id"}).items(): setattr(row, key, value)
        db.commit()
    db.refresh(row); return row


def list_notifications(db: Session, user: User, unread_only: bool = False, limit: int = 100):
    conditions = [Notification.user_id == user.id]
    if unread_only: conditions.append(Notification.is_read.is_(False))
    return list(db.scalars(select(Notification).where(*conditions).order_by(Notification.created_at.desc()).limit(limit)))


def mark_notification_read(db: Session, notification_id: uuid.UUID, user: User):
    row = db.get(Notification, notification_id)
    if row is None or row.user_id != user.id: raise NotFoundError("Notification not found.")
    row.is_read = True; row.read_at = now(); db.commit(); db.refresh(row); return row
