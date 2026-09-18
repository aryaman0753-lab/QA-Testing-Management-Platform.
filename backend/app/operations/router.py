import uuid

from fastapi import APIRouter, Depends, Header, Query, Response, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.common.exceptions import NotFoundError
from app.core.config import get_settings
from app.core.dependencies import get_current_user
from app.database.database import get_db
from app.database.models.operations import ProjectApiKey, WebhookDelivery
from app.database.models.user import User
from app.operations import service
from app.operations.schemas import (
    ApiKeyCreate, ApiKeyCreated, ApiKeyOut, CiRunCreate, CiRunOut, DeliveryOut,
    NotificationOut, PreferenceInput, PreferenceOut, WebhookCreate, WebhookOut, WebhookUpdate,
)

ci_router = APIRouter(prefix="/ci", tags=["CI/CD"])
project_router = APIRouter(prefix="/projects/{project_id}/integrations", tags=["Integrations"])
notification_router = APIRouter(prefix="/notifications", tags=["Notifications"])
_project_key_header = APIKeyHeader(name="X-QAHub-API-Key", scheme_name="QAHubProjectApiKey", auto_error=False)


def get_project_api_key(
    x_qahub_api_key: str | None = Security(_project_key_header),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ProjectApiKey:
    token = x_qahub_api_key
    if token is None and authorization and authorization.lower().startswith("bearer qh_"):
        token = authorization[7:]
    return service.authenticate_api_key(db, token)


@project_router.post("/api-keys", response_model=ApiKeyCreated, status_code=201)
def create_key(project_id: uuid.UUID, payload: ApiKeyCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row, token = service.create_api_key(db, project_id, payload, user)
    return ApiKeyCreated(**ApiKeyOut.model_validate(row).model_dump(), token=token)


@project_router.get("/api-keys", response_model=list[ApiKeyOut])
def keys(project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.list_api_keys(db, project_id, user)


@project_router.delete("/api-keys/{key_id}", status_code=204)
def revoke_key(project_id: uuid.UUID, key_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service.revoke_api_key(db, project_id, key_id, user)
    return Response(status_code=204)


@ci_router.post(
    "/test-runs", response_model=CiRunOut, status_code=202,
    summary="Trigger an automation suite from CI",
    description="Authenticate with `X-QAHub-API-Key`. Suite and environment accept UUIDs or names.",
)
def trigger_ci_test(payload: CiRunCreate, db: Session = Depends(get_db), api_key: ProjectApiKey = Depends(get_project_api_key)):
    run = service.trigger_ci_run(db, api_key, payload)
    return CiRunOut(run_id=run.id, status=run.status, tracking_url=f"{get_settings().PUBLIC_BASE_URL}/projects/{run.project_id}/automation/runs/{run.id}")


@ci_router.get("/test-runs/{run_id}")
def get_ci_test(run_id: uuid.UUID, db: Session = Depends(get_db), api_key: ProjectApiKey = Depends(get_project_api_key)):
    run = service.ci_run_status(db, api_key, run_id)
    result = {
        "run_id": str(run.id), "project_id": str(run.project_id), "suite_id": str(run.suite_id),
        "status": run.status, "total": run.total_cases, "passed": run.passed_cases,
        "failed": run.failed_cases, "skipped": run.skipped_cases, "duration_ms": run.duration_ms,
        "error_message": run.error_message,
    }
    result["tracking_url"] = f"{get_settings().PUBLIC_BASE_URL}/projects/{run.project_id}/automation/runs/{run.id}"
    return result


@project_router.post("/webhooks", response_model=WebhookOut, status_code=201)
def create_webhook(project_id: uuid.UUID, payload: WebhookCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.create_webhook(db, project_id, payload, user)


@project_router.get("/webhooks", response_model=list[WebhookOut])
def webhooks(project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.list_webhooks(db, project_id, user)


@project_router.patch("/webhooks/{webhook_id}", response_model=WebhookOut)
def update_webhook(project_id: uuid.UUID, webhook_id: uuid.UUID, payload: WebhookUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if webhook_id not in {row.id for row in service.list_webhooks(db, project_id, user)}:
        raise NotFoundError("Webhook not found.")
    row = service.update_webhook(db, webhook_id, payload, user)
    return row


@project_router.delete("/webhooks/{webhook_id}", status_code=204)
def delete_webhook(project_id: uuid.UUID, webhook_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if webhook_id not in {row.id for row in service.list_webhooks(db, project_id, user)}:
        raise NotFoundError("Webhook not found.")
    service.delete_webhook(db, webhook_id, user)
    return Response(status_code=204)


@project_router.post("/webhooks/{webhook_id}/test", response_model=DeliveryOut, status_code=202)
def test_webhook(project_id: uuid.UUID, webhook_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    hooks = {row.id: row for row in service.list_webhooks(db, project_id, user)}
    if webhook_id not in hooks:
        raise NotFoundError("Webhook not found.")
    event_id = uuid.uuid4().hex
    created_at = service.now()
    row = WebhookDelivery(webhook_id=webhook_id, project_id=project_id, event="automation.run.started", event_id=event_id, payload={"id": event_id, "event": "automation.run.started", "created_at": created_at.isoformat(), "project_id": str(project_id), "data": {"test": True}}, status="PENDING", next_retry_at=created_at)
    db.add(row); db.commit(); db.refresh(row)
    return row


@project_router.get("/webhook-deliveries", response_model=list[DeliveryOut])
def deliveries(project_id: uuid.UUID, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.list_deliveries(db, project_id, user, limit)


@notification_router.get("", response_model=list[NotificationOut])
def notifications(unread_only: bool = False, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.list_notifications(db, user, unread_only, limit)


@notification_router.patch("/{notification_id}/read", response_model=NotificationOut)
def read_notification(notification_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.mark_notification_read(db, notification_id, user)


@notification_router.get("/preferences", response_model=list[PreferenceOut])
def preferences(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.get_preferences(db, user)


@notification_router.put("/preferences", response_model=PreferenceOut)
def save_preferences(payload: PreferenceInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.upsert_preferences(db, payload, user)
