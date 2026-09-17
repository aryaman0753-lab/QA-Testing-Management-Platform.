import asyncio
import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from time import monotonic

from sqlalchemy import select, update

from app.automation.bugs import create_failure_bugs
from app.automation.engine import ApiAutomationEngine
from app.automation.service import reveal_step_config
from app.common.exceptions import ValidationAppError
from app.core.config import get_settings
from app.database.database import SessionLocal
from app.database.models.api_testing import ApiEnvironment
from app.database.models.automation import AutomationAuditLog, AutomationRun, AutomationStepResult, AutomationTestCase, AutomationTestStep, AutomationTestSuite
from app.database.models.project import ProjectStatus
from app.database.models.project_member import ProjectRole
from app.database.models.user import User, UserRole
from app.projects.service import get_membership, get_project_for_read

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


def _execution_policy(db, run, snapshot):
    settings = get_settings()
    user = db.get(User, run.triggered_by)
    if user is None or not user.is_active or user.role not in {UserRole.ADMIN, UserRole.QA_ENGINEER}:
        raise ValidationAppError("The triggering user no longer has permission to execute automation.")
    project = get_project_for_read(db, run.project_id, user)
    membership = get_membership(db, project.id, user.id)
    if project.status == ProjectStatus.ARCHIVED or (user.role != UserRole.ADMIN and (membership is None or membership.project_role == ProjectRole.VIEWER)):
        raise ValidationAppError("The project no longer permits automation execution.")
    suite = db.get(AutomationTestSuite, run.suite_id)
    if suite is None or suite.status in {"ARCHIVED", "DISABLED"}:
        raise ValidationAppError("The suite is unavailable or disabled.")
    if not suite.allowed_hosts:
        raise ValidationAppError("The suite has no allowed destinations.")
    if run.trigger_type == "SCHEDULED" and suite.status != "ACTIVE":
        raise ValidationAppError("Only active suites can execute on a schedule.")
    environment = db.get(ApiEnvironment, run.environment_id) if run.environment_id else None
    if run.environment_id and (environment is None or environment.project_id != run.project_id):
        raise ValidationAppError("The selected environment is unavailable.")
    production = (environment and environment.classification == "PRODUCTION") or snapshot.get("environment_classification") == "PRODUCTION"
    if production and (not settings.AUTOMATION_ALLOW_PRODUCTION or user.role != UserRole.ADMIN or not snapshot.get("production_confirmed") or run.trigger_type == "SCHEDULED"):
        raise ValidationAppError("Production execution is not permitted by the current policy.")
    # The current destination policy takes effect even for an earlier queued snapshot.
    snapshot["allowed_hosts"] = suite.allowed_hosts
    return user, suite


async def execute_run(run_id, session_factory=SessionLocal, engine=None):
    run_id = uuid.UUID(str(run_id))
    engine = engine or ApiAutomationEngine()
    db = session_factory()
    auto_bugs = False
    try:
        claimed = db.execute(update(AutomationRun).where(AutomationRun.id == run_id, AutomationRun.status == "QUEUED").values(status="RUNNING", started_at=_now(), heartbeat_at=_now()))
        db.commit()
        if not claimed.rowcount:
            return
        run = db.get(AutomationRun, run_id)
        if run.stop_requested:
            run.status, run.completed_at = "CANCELLED", _now()
            db.commit()
            return
        snapshot = reveal_step_config(run.config_snapshot)
        user, suite = _execution_policy(db, run, snapshot)
        auto_bugs = bool(snapshot.get("auto_create_bugs") and suite.auto_create_bugs)
        case_ids = set(db.scalars(select(AutomationTestCase.id).where(AutomationTestCase.suite_id == run.suite_id)))
        step_ids = set(db.scalars(select(AutomationTestStep.id).where(AutomationTestStep.case_id.in_(case_ids)))) if case_ids else set()
        last_check = 0.0
        stopped = False

        def cancelled():
            nonlocal last_check, stopped
            if monotonic() - last_check < 0.2:
                return stopped
            # DB stop state remains authoritative if Redis is temporarily unavailable.
            last_check = monotonic()
            state = db.execute(select(AutomationRun.stop_requested, AutomationRun.status).where(AutomationRun.id == run_id)).first()
            stopped = state is None or state.stop_requested or state.status != "RUNNING"
            if not stopped:
                db.execute(update(AutomationRun).where(AutomationRun.id == run_id, AutomationRun.status == "RUNNING").values(heartbeat_at=_now()))
                db.commit()
            return stopped

        def publish(result):
            values = dict(result)
            for field, existing in (("case_id", case_ids), ("step_id", step_ids)):
                identifier = uuid.UUID(str(values[field])) if values.get(field) else None
                values[field] = identifier if identifier in existing else None
            db.add(AutomationStepResult(run_id=run_id, **values))
            db.execute(update(AutomationRun).where(AutomationRun.id == run_id).values(heartbeat_at=_now()))
            db.commit()

        outcome = await engine.run(snapshot, on_result=publish, is_cancelled=cancelled)
        values = asdict(outcome)
        values.pop("results")
        values.update(completed_at=_now(), heartbeat_at=_now())
        db.execute(update(AutomationRun).where(AutomationRun.id == run_id, AutomationRun.status == "RUNNING").values(**values))
        db.add(AutomationAuditLog(project_id=run.project_id, user_id=user.id, action="AUTOMATION_COMPLETED", resource_type="run", resource_id=run_id))
        db.commit()
    except Exception:
        db.rollback()
        db.execute(update(AutomationRun).where(AutomationRun.id == run_id, AutomationRun.status.in_(["QUEUED", "RUNNING"])).values(status="FAILED", completed_at=_now(), error_message="The automation worker could not execute this run. Check suite configuration, permissions, and worker availability."))
        db.commit()
        logger.warning("Automation execution failed for run %s", run_id)
    finally:
        db.close()
    if auto_bugs:
        with session_factory() as bug_db:
            try:
                run = bug_db.get(AutomationRun, run_id)
                user = bug_db.get(User, run.triggered_by)
                if user and user.is_active:
                    create_failure_bugs(bug_db, run, user)
                    bug_db.commit()
            except Exception:
                bug_db.rollback()
                logger.warning("Automatic bug creation failed for automation run %s", run_id)


def process_run(run_id, session_factory=SessionLocal, engine=None):
    return asyncio.run(execute_run(run_id, session_factory=session_factory, engine=engine))
