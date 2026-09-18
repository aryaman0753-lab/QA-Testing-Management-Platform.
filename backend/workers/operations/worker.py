"""Reliable webhook/email delivery and explicitly-configured retention cleanup."""
import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import delete, or_, select

from app.api_testing.outbound_security import validate_and_pin_url, verify_connected_peer
from app.api_testing.secrets import decrypt
from app.core.config import get_settings
from app.database.database import SessionLocal
from app.database.models.automation import AutomationRun
from app.database.models.operations import Notification, Webhook, WebhookDelivery
from app.operations.providers import EmailNotificationProvider
from app.load_testing.service import cleanup_expired_runs
from app.database.models.user import User
from workers.heartbeat import Heartbeat
from app.core.logging import configure_logging

logger = logging.getLogger("qahub.operations_worker")


def sign_payload(secret: str, payload: dict) -> tuple[bytes, str]:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return body, f"sha256={digest}"


async def _post(webhook: Webhook, delivery: WebhookDelivery) -> int:
    settings = get_settings()
    pinned = await validate_and_pin_url(webhook.url, allow_private=False)
    body, signature = sign_payload(decrypt(webhook.secret_encrypted), delivery.payload)
    headers = {
        "Content-Type": "application/json", "Host": pinned.host_header,
        "X-QAHub-Event": delivery.event, "X-QAHub-Delivery": delivery.event_id,
        "X-QAHub-Signature-256": signature,
    }
    timeout = httpx.Timeout(settings.WEBHOOK_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        async with client.stream("POST", pinned.network_url, content=body, headers=headers, extensions={"sni_hostname": pinned.sni_hostname}) as response:
            verify_connected_peer(response, pinned.ip)
            if response.status_code < 200 or response.status_code >= 300:
                raise httpx.HTTPStatusError(f"Destination returned HTTP {response.status_code}.", request=response.request, response=response)
            return response.status_code


def deliver_one(delivery_id) -> bool:
    settings = get_settings(); moment = datetime.now(timezone.utc)
    with SessionLocal() as db:
        delivery = db.scalar(select(WebhookDelivery).where(WebhookDelivery.id == delivery_id).with_for_update())
        if delivery is None or delivery.status not in {"PENDING", "RETRYING"} or (delivery.next_retry_at and delivery.next_retry_at > moment):
            return True
        webhook = db.get(Webhook, delivery.webhook_id)
        delivery.attempt_count += 1; delivery.last_attempt_at = moment; delivery.status = "DELIVERING"; db.commit()
        try:
            if webhook is None or not webhook.enabled:
                raise RuntimeError("Webhook is disabled or was removed.")
            status = asyncio.run(_post(webhook, delivery))
            delivery.response_status = status; delivery.status = "DELIVERED"; delivery.failure_reason = None; delivery.next_retry_at = None; delivery.completed_at = datetime.now(timezone.utc)
            db.commit(); return True
        except Exception as exc:
            logger.warning("Webhook delivery %s attempt %s failed: %s", delivery.id, delivery.attempt_count, type(exc).__name__)
            delivery.failure_reason = str(exc)[:1000] or type(exc).__name__
            if delivery.attempt_count >= settings.WEBHOOK_MAX_ATTEMPTS:
                delivery.status = "FAILED"; delivery.next_retry_at = None; delivery.completed_at = datetime.now(timezone.utc)
            else:
                delivery.status = "RETRYING"
                delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=min(3600, 30 * (2 ** (delivery.attempt_count - 1))))
            db.commit(); return False


def deliver_email(notification_id) -> bool:
    with SessionLocal() as db:
        notification = db.get(Notification, notification_id)
        if notification is None or notification.email_status != "PENDING": return True
        user = db.get(User, notification.user_id)
        try:
            if user is None or not user.is_active: raise RuntimeError("Notification recipient is inactive.")
            EmailNotificationProvider().send(user.email, notification.title, notification.message)
            notification.email_status = "SENT"; db.commit(); return True
        except Exception as exc:
            logger.warning("Email notification %s failed: %s", notification.id, type(exc).__name__)
            notification.email_status = "FAILED"; db.commit(); return False


def cleanup_retained_data() -> None:
    settings = get_settings(); moment = datetime.now(timezone.utc)
    with SessionLocal() as db:
        cleanup_expired_runs(db)
        if settings.WEBHOOK_DELIVERY_RETENTION_DAYS:
            cutoff = moment - timedelta(days=settings.WEBHOOK_DELIVERY_RETENTION_DAYS)
            db.execute(delete(WebhookDelivery).where(WebhookDelivery.created_at < cutoff, WebhookDelivery.status.in_(["DELIVERED", "FAILED"])))
        if settings.AUTOMATION_RESULT_RETENTION_DAYS:
            cutoff = moment - timedelta(days=settings.AUTOMATION_RESULT_RETENTION_DAYS)
            db.execute(delete(AutomationRun).where(AutomationRun.created_at < cutoff, AutomationRun.status.in_(["PASSED", "FAILED", "CANCELLED"])))
        db.commit()


def tick() -> int:
    moment = datetime.now(timezone.utc); settings = get_settings()
    with SessionLocal() as db:
        stale = list(db.scalars(select(WebhookDelivery).where(WebhookDelivery.status == "DELIVERING", WebhookDelivery.last_attempt_at < moment - timedelta(seconds=max(60, settings.WEBHOOK_TIMEOUT_SECONDS * 2)))))
        for row in stale:
            row.status = "RETRYING"; row.next_retry_at = moment; row.failure_reason = "Delivery worker stopped before recording a response."
        if stale: db.commit()
        delivery_ids = list(db.scalars(select(WebhookDelivery.id).where(WebhookDelivery.status.in_(["PENDING", "RETRYING"]), or_(WebhookDelivery.next_retry_at.is_(None), WebhookDelivery.next_retry_at <= moment)).order_by(WebhookDelivery.created_at).limit(50)))
        email_ids = list(db.scalars(select(Notification.id).where(Notification.email_status == "PENDING").order_by(Notification.created_at).limit(50)))
    for item in delivery_ids: deliver_one(item)
    for item in email_ids: deliver_email(item)
    return len(delivery_ids) + len(email_ids)


def main() -> None:
    configure_logging()
    heartbeat = Heartbeat("OPERATIONS").start(); last_cleanup = 0.0
    try:
        while True:
            heartbeat.working("delivery-poll")
            try:
                count = tick(); heartbeat.finished(completed=count)
            except Exception:
                logger.exception("Operations delivery tick failed"); heartbeat.finished(True); count = 0
            if time.monotonic() - last_cleanup > 3600:
                try: cleanup_retained_data()
                except Exception: logger.exception("Retention cleanup failed")
                last_cleanup = time.monotonic()
            time.sleep(1 if count else 5)
    except KeyboardInterrupt:
        heartbeat.stop()


if __name__ == "__main__": main()
