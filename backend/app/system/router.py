from datetime import datetime, timedelta, timezone

import redis
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import require_admin
from app.core.observability import prometheus_metrics
from app.database.database import get_db
from app.database.models.automation import AutomationRun
from app.database.models.load_testing import LoadTestRun
from app.database.models.operations import WebhookDelivery, WorkerHeartbeat
from app.database.models.user import User

router = APIRouter(tags=["System"])
admin_router = APIRouter(prefix="/admin/system", tags=["Admin Operations"])


def _database(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1")); return True
    except Exception:
        db.rollback(); return False


def _redis():
    settings = get_settings()
    try:
        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=0.5, socket_timeout=0.5, decode_responses=True)
        client.ping(); return client
    except (redis.RedisError, OSError): return None


def _workers(db: Session):
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=get_settings().WORKER_UNAVAILABLE_SECONDS)
    rows = list(db.scalars(select(WorkerHeartbeat).order_by(WorkerHeartbeat.worker_type, WorkerHeartbeat.worker_id)))
    def unavailable(row):
        value = row.last_heartbeat
        if value.tzinfo is None: value = value.replace(tzinfo=timezone.utc)
        return value < cutoff
    return [{"worker_id": row.worker_id, "worker_type": row.worker_type, "status": "UNAVAILABLE" if unavailable(row) else row.status, "last_heartbeat": row.last_heartbeat, "current_job": row.current_job, "started_at": row.started_at, "completed_jobs": row.completed_jobs, "failed_jobs": row.failed_jobs} for row in rows]


def system_state(db: Session):
    settings = get_settings(); database_ok = _database(db); redis_client = _redis()
    queues = {"automation": None, "load_testing": None, "webhooks": None}
    if redis_client:
        try:
            queues = {"automation": redis_client.llen(settings.AUTOMATION_QUEUE_NAME), "load_testing": redis_client.llen(settings.LOAD_TEST_QUEUE_NAME), "webhooks": None}
        except redis.RedisError: pass
    workers = _workers(db) if database_ok else []
    automation_active = db.scalar(select(func.count(AutomationRun.id)).where(AutomationRun.status.in_(["QUEUED", "RUNNING"]))) if database_ok else None
    load_active = db.scalar(select(func.count(LoadTestRun.id)).where(LoadTestRun.status.in_(["QUEUED", "STARTING", "RUNNING", "STOPPING"]))) if database_ok else None
    failed_automation = db.scalar(select(func.count(AutomationRun.id)).where(AutomationRun.status == "FAILED")) if database_ok else None
    failed_load = db.scalar(select(func.count(LoadTestRun.id)).where(LoadTestRun.status == "FAILED")) if database_ok else None
    webhook_failures = db.scalar(select(func.count(WebhookDelivery.id)).where(WebhookDelivery.status == "FAILED")) if database_ok else None
    recent_failures = []
    if database_ok:
        queues["webhooks"] = db.scalar(select(func.count(WebhookDelivery.id)).where(WebhookDelivery.status.in_(["PENDING", "RETRYING", "DELIVERING"]))) or 0
        recent_failures.extend({"type": "automation", "id": str(row.id), "project_id": str(row.project_id), "created_at": row.created_at, "message": row.error_message or "Automation failed."} for row in db.scalars(select(AutomationRun).where(AutomationRun.status == "FAILED").order_by(AutomationRun.created_at.desc()).limit(5)))
        recent_failures.extend({"type": "load_test", "id": str(row.id), "project_id": str(row.project_id), "created_at": row.created_at, "message": row.error_message or "Load test failed."} for row in db.scalars(select(LoadTestRun).where(LoadTestRun.status == "FAILED").order_by(LoadTestRun.created_at.desc()).limit(5)))
        recent_failures.extend({"type": "webhook", "id": str(row.id), "project_id": str(row.project_id), "created_at": row.created_at, "message": row.failure_reason or "Webhook delivery failed."} for row in db.scalars(select(WebhookDelivery).where(WebhookDelivery.status == "FAILED").order_by(WebhookDelivery.created_at.desc()).limit(5)))
        recent_failures.sort(key=lambda row: row["created_at"].replace(tzinfo=timezone.utc) if row["created_at"].tzinfo is None else row["created_at"], reverse=True)
        recent_failures = recent_failures[:10]
    migration = "unavailable"
    if database_ok:
        try: migration = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none() or "none"
        except Exception: db.rollback()
    return {"status": "healthy" if database_ok and redis_client else "degraded", "api": "available", "database": "connected" if database_ok else "unavailable", "redis": "connected" if redis_client else "unavailable", "workers": workers, "queues": queues, "active_jobs": {"automation": automation_active or 0, "load_tests": load_active or 0}, "failed_jobs": {"automation": failed_automation or 0, "load_tests": failed_load or 0, "webhook_deliveries": webhook_failures or 0}, "recent_failures": recent_failures, "version": "0.6.0", "database_migration": migration, "email_configured": bool(settings.SMTP_HOST and settings.SMTP_FROM)}


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    database_ok, redis_ok = _database(db), _redis() is not None
    return {"status": "healthy" if database_ok and redis_ok else "degraded", "api": "available", "database": "connected" if database_ok else "unavailable", "redis": "connected" if redis_ok else "unavailable"}


@router.get("/health/live")
def liveness(): return {"status": "alive"}


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)):
    database_ok, redis_ok = _database(db), _redis() is not None
    content = {"status": "ready" if database_ok and redis_ok else "not_ready", "database": "connected" if database_ok else "unavailable", "redis": "connected" if redis_ok else "unavailable"}
    return JSONResponse(content=content, status_code=200 if database_ok and redis_ok else 503)


@router.get("/metrics", response_class=PlainTextResponse)
def metrics(db: Session = Depends(get_db)):
    state = system_state(db)
    lines = [prometheus_metrics().rstrip(), "# HELP qahub_dependency_up Dependency availability.", "# TYPE qahub_dependency_up gauge", f'qahub_dependency_up{{dependency="database"}} {1 if state["database"] == "connected" else 0}', f'qahub_dependency_up{{dependency="redis"}} {1 if state["redis"] == "connected" else 0}', "# HELP qahub_active_jobs Active or queued execution jobs.", "# TYPE qahub_active_jobs gauge"]
    lines.extend(f'qahub_active_jobs{{type="{kind}"}} {value}' for kind, value in state["active_jobs"].items())
    lines.extend(["# HELP qahub_queue_depth Waiting work by queue.", "# TYPE qahub_queue_depth gauge"])
    lines.extend(f'qahub_queue_depth{{queue="{kind}"}} {value}' for kind, value in state["queues"].items() if value is not None)
    unavailable = sum(worker["status"] == "UNAVAILABLE" for worker in state["workers"])
    lines.extend(["# HELP qahub_workers_unavailable Workers with stale heartbeats.", "# TYPE qahub_workers_unavailable gauge", f"qahub_workers_unavailable {unavailable}"])
    return "\n".join(lines) + "\n"


@admin_router.get("")
def admin_system(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return system_state(db)
