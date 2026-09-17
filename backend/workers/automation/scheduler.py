"""Database-locked cron scheduling; independent from the web process."""
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update

from app.automation import queue
from app.automation.cron import next_execution
from app.automation.schemas import StartRunInput
from app.automation.service import create_run
from app.core.config import get_settings
from app.database.database import SessionLocal
from app.database.models.automation import AutomationRun, AutomationSchedule, AutomationTestSuite
from app.database.models.user import User

logger = logging.getLogger(__name__)


def recover_stale_runs(db, now=None):
    now = now or datetime.now(timezone.utc)
    settings = get_settings()
    active_cutoff = now - timedelta(seconds=settings.AUTOMATION_STALE_RUN_SECONDS)
    queued_cutoff = now - timedelta(seconds=settings.AUTOMATION_QUEUE_TIMEOUT_SECONDS)
    stale = or_(
        (AutomationRun.status == "RUNNING") & or_(AutomationRun.heartbeat_at < active_cutoff, AutomationRun.heartbeat_at.is_(None)),
        (AutomationRun.status == "QUEUED") & (AutomationRun.created_at < queued_cutoff),
    )
    result = db.execute(update(AutomationRun).where(stale).values(status="FAILED", completed_at=now, error_message="Execution expired because its worker or queue was unavailable."))
    db.commit()
    return result.rowcount


def scheduler_tick(session_factory=SessionLocal, enqueue=None, now=None):
    enqueue = enqueue or queue.enqueue_run
    now = now or datetime.now(timezone.utc)
    scheduled = []
    with session_factory() as db:
        recover_stale_runs(db, now)
        due_ids = list(db.scalars(select(AutomationSchedule.id).where(AutomationSchedule.enabled.is_(True), AutomationSchedule.next_run_at <= now).order_by(AutomationSchedule.next_run_at).limit(100)))
    for schedule_id in due_ids:
        with session_factory() as db:
            schedule = db.scalar(select(AutomationSchedule).where(AutomationSchedule.id == schedule_id, AutomationSchedule.enabled.is_(True), AutomationSchedule.next_run_at <= now).with_for_update(skip_locked=True))
            if schedule is None:
                continue
            try:
                suite = db.get(AutomationTestSuite, schedule.suite_id)
                if suite is None or suite.status in {"DISABLED", "ARCHIVED"}:
                    schedule.enabled, schedule.next_run_at = False, None
                    schedule.last_error = "Schedule disabled because the suite is unavailable."
                    db.commit()
                    continue
                schedule.next_run_at = next_execution(schedule.cron_expression, schedule.timezone, after=now)
                active = db.scalar(select(AutomationRun.id).where(AutomationRun.suite_id == schedule.suite_id, AutomationRun.status.in_(["QUEUED", "RUNNING"])).limit(1))
                if active:
                    schedule.last_error = "Skipped because a previous suite run is still active."
                    db.commit()
                    continue
                user = db.get(User, schedule.created_by)
                if user is None or not user.is_active:
                    schedule.last_error = "The schedule owner is unavailable."
                    db.commit()
                    continue
                # create_run commits the run and this already-advanced schedule together.
                schedule.last_run_at, schedule.last_error = now, None
                run = create_run(db, suite.id, StartRunInput(environment_id=schedule.environment_id), user, trigger_type="SCHEDULED", schedule_id=schedule.id, enqueue=False)
                try:
                    enqueue(run.id)
                    scheduled.append(run.id)
                except Exception:
                    run.status, run.completed_at, run.error_message = "FAILED", now, "The automation queue is unavailable."
                    schedule.last_error = "The automation queue is unavailable."
                    db.commit()
            except Exception:
                db.rollback()
                schedule = db.get(AutomationSchedule, schedule_id)
                if schedule:
                    schedule.last_error = "Scheduled execution failed validation, permissions, or worker configuration."
                    try:
                        schedule.next_run_at = next_execution(schedule.cron_expression, schedule.timezone, after=now)
                    except Exception:
                        schedule.enabled, schedule.next_run_at = False, None
                    db.commit()
                logger.warning("Automation schedule %s could not be queued", schedule_id)
    return scheduled


def main():
    logging.basicConfig(level=logging.INFO)
    logger.info("Automation scheduler started")
    while True:
        try:
            scheduler_tick()
        except KeyboardInterrupt:
            return
        except Exception:
            logger.warning("Automation scheduler database is temporarily unavailable")
        time.sleep(get_settings().AUTOMATION_SCHEDULER_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
