import copy
import json
import math
import threading
import uuid
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import redis
from pydantic import ValidationError
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.orm import Session, selectinload

from app.api_testing.schemas import RequestCreate
from app.api_testing.secrets import MASK, decrypt, encrypt, is_sensitive_name, mask_auth, mask_key_values, reveal_auth, reveal_key_values
from app.automation import queue
from app.automation.cron import next_execution
from app.automation.schemas import CaseCreate, CaseOut, RunDetail, RunOut, ScheduleCreate, ScheduleOut, StartRunInput, StepCreate, StepOut, SuiteCreate, SuiteOut
from app.common.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.core.config import get_settings
from app.database.models.api_testing import ApiEnvironment, ApiRequest
from app.database.models.automation import AutomationAuditLog, AutomationRun, AutomationSchedule, AutomationTestCase, AutomationTestStep, AutomationTestSuite
from app.database.models.bug import Bug
from app.database.models.project_member import ProjectRole
from app.database.models.user import User, UserRole
from app.projects.service import get_membership, get_project_for_read

ACTIVE_STATUSES = {"QUEUED", "RUNNING"}
_sqlite_start_lock = threading.RLock()


class QueueUnavailableError(AppError):
    status_code = 503
    detail = "The automation queue is unavailable. Try again later."


def _now():
    return datetime.now(timezone.utc)


def audit(db, project_id, user_id, action, resource_type, resource_id):
    db.add(AutomationAuditLog(project_id=project_id, user_id=user_id, action=action, resource_type=resource_type, resource_id=resource_id))


def _manage(db, project_id, user):
    project = get_project_for_read(db, project_id, user)
    membership = get_membership(db, project_id, user.id)
    if user.role != UserRole.ADMIN and (user.role != UserRole.QA_ENGINEER or membership is None or membership.project_role == ProjectRole.VIEWER):
        raise ForbiddenError("Only administrators and QA engineers with project write access can manage automation.")
    return project


def _environment(db, environment_id, project_id):
    if environment_id is None:
        return None
    environment = db.get(ApiEnvironment, environment_id)
    if environment is None or environment.project_id != project_id:
        raise NotFoundError("Environment not found in this project.")
    return environment


def _source(db, source_id, project_id):
    source = db.get(ApiRequest, source_id)
    if source is None or source.project_id != project_id or source.is_archived or source.collection.is_archived:
        raise NotFoundError("API request not found in this project.")
    return source


def get_suite(db, suite_id, user, manage=False):
    suite = db.scalar(select(AutomationTestSuite).options(selectinload(AutomationTestSuite.cases).selectinload(AutomationTestCase.steps)).where(AutomationTestSuite.id == suite_id))
    if suite is None:
        raise NotFoundError("Automation suite not found.")
    (_manage if manage else get_project_for_read)(db, suite.project_id, user)
    return suite


def _editable(db, suite):
    # Serialize definition changes with execution's snapshot under PostgreSQL.
    db.scalar(select(AutomationTestSuite.id).where(AutomationTestSuite.id == suite.id).with_for_update())
    if suite.status == "ARCHIVED":
        raise ConflictError("Archived suites cannot be edited.")
    if db.scalar(select(AutomationRun.id).where(AutomationRun.suite_id == suite.id, AutomationRun.status.in_(ACTIVE_STATUSES)).limit(1)):
        raise ConflictError("Stop the active run before editing this suite.")


def protect_step_config(value):
    return {"encrypted": encrypt(json.dumps(value, separators=(",", ":"), default=str))}


def reveal_step_config(value):
    if value is None:
        return None
    if "encrypted" in value:
        return json.loads(decrypt(value["encrypted"]))
    return copy.deepcopy(value)


def _masked_url(value):
    try:
        parts = urlsplit(value)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode([(key, MASK if is_sensitive_name(key) else val) for key, val in parse_qsl(parts.query, keep_blank_values=True)]), ""))
    except ValueError:
        return MASK


def masked_step_config(value):
    value = reveal_step_config(value)
    if value is None:
        return None
    if "request" in value:
        request = value["request"]
        request["authentication_config"] = mask_auth(request.get("authentication_config", {}))
        request["headers"] = mask_key_values(request.get("headers", []))
        request["query_parameters"] = mask_key_values(request.get("query_parameters", []))
        request["url"] = _masked_url(request.get("url", ""))
        # Arbitrary request bodies may carry credentials under application-specific keys.
        if request.get("body"):
            request["body"] = MASK
    if "value" in value and (value.get("is_secret") or is_sensitive_name(value.get("variable_name", ""))):
        value["value"] = MASK
    if "expected" in value and is_sensitive_name(value.get("target") or ""):
        value["expected"] = MASK
    for assertion in value.get("assertions", []):
        if is_sensitive_name(assertion.get("target") or ""):
            assertion["expected"] = MASK
    return value


def _restore_masks(value, old):
    if value == MASK:
        if old is None:
            raise ValidationAppError("A masked value cannot be used for a new secret. Enter its value.")
        return old
    if isinstance(value, dict):
        return {key: _restore_masks(item, old.get(key) if isinstance(old, dict) else None) for key, item in value.items()}
    if isinstance(value, list):
        result = []
        for index, item in enumerate(value):
            previous = old[index] if isinstance(old, list) and index < len(old) else None
            if isinstance(item, dict) and "key" in item:
                previous = next((row for row in (old or []) if row.get("key") == item["key"]), None)
            result.append(_restore_masks(item, previous))
        return result
    return value


def step_out(step):
    result = StepOut.model_validate(step)
    result.config = masked_step_config(step.config)
    result.condition = masked_step_config(step.condition)
    return result


def case_out(case):
    return CaseOut.model_validate({**{key: getattr(case, key) for key in CaseOut.model_fields if key != "steps"}, "steps": [step_out(step) for step in sorted(case.steps, key=lambda row: row.order_index)]})


def suite_out(suite):
    return SuiteOut.model_validate({**{key: getattr(suite, key) for key in SuiteOut.model_fields if key != "cases"}, "cases": [case_out(case) for case in sorted(suite.cases, key=lambda row: row.order_index)]})


def _page(items, total, page, page_size):
    return {"items": items, "total": total, "page": page, "page_size": page_size, "total_pages": math.ceil(total / page_size)}


def list_suites(db, project_id, user, page=1, page_size=20, status=None, search=None):
    get_project_for_read(db, project_id, user)
    conditions = [AutomationTestSuite.project_id == project_id]
    conditions.append(AutomationTestSuite.status == status if status else AutomationTestSuite.status != "ARCHIVED")
    if search:
        conditions.append(AutomationTestSuite.name.ilike(f"%{search}%"))
    total = db.scalar(select(func.count(AutomationTestSuite.id)).where(*conditions)) or 0
    rows = db.scalars(select(AutomationTestSuite).where(*conditions).order_by(AutomationTestSuite.updated_at.desc()).offset((page - 1) * page_size).limit(page_size))
    return _page([suite_out(row) for row in rows], total, page, page_size)


def create_suite(db, project_id, payload, user):
    _manage(db, project_id, user)
    _environment(db, payload.environment_id, project_id)
    if payload.max_retries > get_settings().AUTOMATION_MAX_RETRIES:
        raise ValidationAppError("Retry count exceeds the configured limit.")
    suite = AutomationTestSuite(project_id=project_id, created_by=user.id, **payload.model_dump(mode="python"))
    db.add(suite)
    db.flush()
    audit(db, project_id, user.id, "SUITE_CREATED", "suite", suite.id)
    db.commit()
    return suite_out(suite)


def update_suite(db, suite_id, payload, user):
    suite = get_suite(db, suite_id, user, True)
    _editable(db, suite)
    data = {key: getattr(suite, key) for key in SuiteCreate.model_fields}
    data.update(payload.model_dump(exclude_unset=True))
    try:
        validated = SuiteCreate.model_validate(data)
    except ValidationError as exc:
        raise ValidationAppError("Invalid suite configuration.") from exc
    _environment(db, validated.environment_id, suite.project_id)
    if validated.max_retries > get_settings().AUTOMATION_MAX_RETRIES:
        raise ValidationAppError("Retry count exceeds the configured limit.")
    for key, value in validated.model_dump().items():
        setattr(suite, key, value)
    if suite.status in {"DISABLED", "ARCHIVED"}:
        db.execute(update(AutomationSchedule).where(AutomationSchedule.suite_id == suite.id).values(enabled=False, next_run_at=None))
    audit(db, suite.project_id, user.id, "SUITE_UPDATED", "suite", suite.id)
    db.commit()
    return suite_out(suite)


def delete_suite(db, suite_id, user):
    suite = get_suite(db, suite_id, user, True)
    _editable(db, suite)
    suite.status = "ARCHIVED"
    db.execute(update(AutomationSchedule).where(AutomationSchedule.suite_id == suite.id).values(enabled=False, next_run_at=None))
    audit(db, suite.project_id, user.id, "SUITE_ARCHIVED", "suite", suite.id)
    db.commit()


def _case(db, case_id, user):
    case = db.get(AutomationTestCase, case_id)
    if case is None:
        raise NotFoundError("Test case not found.")
    suite = get_suite(db, case.suite_id, user, True)
    _editable(db, suite)
    return case, suite


def create_case(db, suite_id, payload, user):
    suite = get_suite(db, suite_id, user, True)
    _editable(db, suite)
    if len(suite.cases) >= get_settings().AUTOMATION_MAX_CASES:
        raise ValidationAppError("Suite case limit exceeded.")
    if payload.timeout > get_settings().AUTOMATION_MAX_RUN_SECONDS:
        raise ValidationAppError("Case timeout exceeds the maximum run duration.")
    data = payload.model_dump()
    data["order_index"] = len(suite.cases)
    case = AutomationTestCase(project_id=suite.project_id, suite_id=suite.id, **data)
    db.add(case)
    db.flush()
    audit(db, suite.project_id, user.id, "CASE_CREATED", "case", case.id)
    db.commit()
    return case_out(case)


def update_case(db, case_id, payload, user):
    case, suite = _case(db, case_id, user)
    data = {key: getattr(case, key) for key in CaseCreate.model_fields}
    data.update(payload.model_dump(exclude_unset=True))
    try:
        validated = CaseCreate.model_validate(data)
    except ValidationError as exc:
        raise ValidationAppError("Invalid test case configuration.") from exc
    if validated.timeout > get_settings().AUTOMATION_MAX_RUN_SECONDS:
        raise ValidationAppError("Case timeout exceeds the maximum run duration.")
    for key, value in validated.model_dump().items():
        setattr(case, key, value)
    audit(db, suite.project_id, user.id, "CASE_UPDATED", "case", case.id)
    db.commit()
    return case_out(case)


def delete_case(db, case_id, user):
    case, suite = _case(db, case_id, user)
    audit(db, suite.project_id, user.id, "CASE_DELETED", "case", case.id)
    db.delete(case)
    db.commit()


def _validate_step(db, payload, suite):
    if payload.api_request_id:
        _source(db, payload.api_request_id, suite.project_id)
    if payload.step_type == "DELAY" and payload.config["seconds"] > get_settings().AUTOMATION_MAX_DELAY_SECONDS:
        raise ValidationAppError("Delay exceeds the configured limit.")


def create_step(db, case_id, payload, user):
    case, suite = _case(db, case_id, user)
    if sum(len(row.steps) for row in suite.cases) >= get_settings().AUTOMATION_MAX_STEPS:
        raise ValidationAppError("Suite step limit exceeded.")
    _validate_step(db, payload, suite)
    data = payload.model_dump()
    data["config"] = protect_step_config(_restore_masks(data["config"], None))
    data["condition"] = protect_step_config(data["condition"]) if data["condition"] else None
    data["order_index"] = len(case.steps)
    step = AutomationTestStep(case_id=case.id, **data)
    db.add(step)
    db.flush()
    audit(db, suite.project_id, user.id, "STEP_CREATED", "step", step.id)
    db.commit()
    return step_out(step)


def update_step(db, step_id, payload, user):
    step = db.get(AutomationTestStep, step_id)
    if step is None:
        raise NotFoundError("Test step not found.")
    case, suite = _case(db, step.case_id, user)
    data = {key: getattr(step, key) for key in StepCreate.model_fields}
    data["config"] = reveal_step_config(step.config)
    data["condition"] = reveal_step_config(step.condition)
    incoming = payload.model_dump(exclude_unset=True)
    if "config" in incoming:
        incoming["config"] = _restore_masks(incoming["config"], data["config"])
    if "condition" in incoming:
        incoming["condition"] = _restore_masks(incoming["condition"], data["condition"])
    data.update(incoming)
    try:
        validated = StepCreate.model_validate(data)
    except ValidationError as exc:
        raise ValidationAppError("Invalid step configuration.") from exc
    _validate_step(db, validated, suite)
    data = validated.model_dump()
    data["config"] = protect_step_config(data["config"])
    data["condition"] = protect_step_config(data["condition"]) if data["condition"] else None
    for key, value in data.items():
        setattr(step, key, value)
    audit(db, suite.project_id, user.id, "STEP_UPDATED", "step", step.id)
    db.commit()
    return step_out(step)


def delete_step(db, step_id, user):
    step = db.get(AutomationTestStep, step_id)
    if step is None:
        raise NotFoundError("Test step not found.")
    case, suite = _case(db, step.case_id, user)
    audit(db, suite.project_id, user.id, "STEP_DELETED", "step", step.id)
    db.delete(step)
    db.commit()


def reorder(db, resource_id, ids, user, steps=False):
    if steps:
        case, suite = _case(db, resource_id, user)
        rows = case.steps
    else:
        suite = get_suite(db, resource_id, user, True)
        _editable(db, suite)
        rows = suite.cases
    if len(set(ids)) != len(ids) or set(ids) != {row.id for row in rows}:
        raise ValidationAppError("Reordering must include every item exactly once.")
    positions = {item: position for position, item in enumerate(ids)}
    for row in rows:
        row.order_index = positions[row.id]
    audit(db, suite.project_id, user.id, "STEPS_REORDERED" if steps else "CASES_REORDERED", "suite", suite.id)
    db.commit()
    return suite_out(suite)


def _request_snapshot(source):
    data = {key: getattr(source, key) for key in RequestCreate.model_fields if key not in {"assertions", "extractors"}}
    data["headers"] = reveal_key_values(source.headers)
    data["query_parameters"] = reveal_key_values(source.query_parameters)
    data["authentication_config"] = reveal_auth(source.authentication_config)
    data["body"] = decrypt(source.body) if source.body else source.body
    data["assertions"] = [{key: getattr(row, key) for key in ("assertion_type", "operator", "target", "expected_value", "enabled")} for row in sorted(source.assertions, key=lambda row: row.position)]
    data["extractors"] = [{key: getattr(row, key) for key in ("source", "path", "variable_name", "enabled")} for row in sorted(source.extractors, key=lambda row: row.position)]
    return RequestCreate.model_validate(data).model_dump(mode="json")


def snapshot_suite(db, suite, environment, confirm_production=False):
    cases = []
    for case in sorted(suite.cases, key=lambda row: row.order_index):
        steps = []
        for step in sorted(case.steps, key=lambda row: row.order_index):
            config = reveal_step_config(step.config)
            if step.api_request_id:
                config = {"request": _request_snapshot(_source(db, step.api_request_id, suite.project_id))}
            steps.append({"id": str(step.id), "name": step.name, "step_type": step.step_type, "enabled": step.enabled,
                          "order_index": step.order_index, "condition": reveal_step_config(step.condition), "config": config})
        cases.append({"id": str(case.id), "name": case.name, "enabled": case.enabled, "timeout": case.timeout,
                      "order_index": case.order_index, "steps": steps})
    variables = environment.variables if environment else {}
    return {"suite_id": str(suite.id), "name": suite.name, "max_retries": suite.max_retries, "auto_create_bugs": suite.auto_create_bugs,
            "allowed_hosts": suite.allowed_hosts, "environment_id": str(environment.id) if environment else None,
            "environment_classification": environment.classification if environment else "QA",
            "environment_variables": {key: decrypt(value.get("value", "")) for key, value in variables.items()},
            "runtime_variables": {}, "secret_variable_names": [key for key, value in variables.items() if value.get("is_secret") or is_sensitive_name(key)],
            "production_confirmed": confirm_production, "cases": cases}


def recover_stale_runs(db):
    now = _now()
    settings = get_settings()
    stale = or_(
        (AutomationRun.status == "QUEUED") & (AutomationRun.created_at < now - timedelta(seconds=settings.AUTOMATION_QUEUE_TIMEOUT_SECONDS)),
        (AutomationRun.status == "RUNNING") & (or_(AutomationRun.heartbeat_at < now - timedelta(seconds=settings.AUTOMATION_STALE_RUN_SECONDS), AutomationRun.heartbeat_at.is_(None))),
    )
    db.execute(update(AutomationRun).where(stale).values(status="FAILED", completed_at=now, error_message="Automation worker heartbeat or queue timeout expired."))


def create_run(db, suite_id, payload: StartRunInput, user, trigger_type="MANUAL", schedule_id=None, enqueue=True):
    with _sqlite_start_lock:
        # The transaction lock also serializes global/user concurrency checks across API and scheduler processes.
        if db.bind.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(5141485505)"))
        suite = get_suite(db, suite_id, user, True)
        _editable(db, suite)
        if suite.status not in {"ACTIVE", "DRAFT"}:
            raise ConflictError("Only draft or active suites can run.")
        if trigger_type == "SCHEDULED" and suite.status != "ACTIVE":
            raise ConflictError("Scheduled suites must be active.")
        settings = get_settings()
        environment = _environment(db, payload.environment_id or suite.environment_id, suite.project_id)
        if environment and environment.classification == "PRODUCTION":
            if trigger_type == "SCHEDULED" or not settings.AUTOMATION_ALLOW_PRODUCTION or user.role != UserRole.ADMIN or not payload.confirm_production:
                raise ForbiddenError("Production automation requires server enablement, an administrator and explicit confirmation; production schedules are disabled.")
        if not suite.allowed_hosts:
            raise ValidationAppError("Configure at least one allowed host before executing this suite.")
        enabled_cases = [case for case in suite.cases if case.enabled]
        if not enabled_cases or not any(step.enabled for case in enabled_cases for step in case.steps):
            raise ValidationAppError("The suite must contain an enabled case and step.")
        if len(suite.cases) > settings.AUTOMATION_MAX_CASES or sum(len(case.steps) for case in suite.cases) > settings.AUTOMATION_MAX_STEPS or suite.max_retries > settings.AUTOMATION_MAX_RETRIES:
            raise ValidationAppError("Suite exceeds the configured execution limits.")
        recover_stale_runs(db)
        active = [AutomationRun.status.in_(ACTIVE_STATUSES)]
        for conditions, limit in ((active, settings.AUTOMATION_MAX_CONCURRENT_RUNS),
                                  (active + [AutomationRun.project_id == suite.project_id], settings.AUTOMATION_MAX_CONCURRENT_PER_PROJECT),
                                  (active + [AutomationRun.triggered_by == user.id], settings.AUTOMATION_MAX_CONCURRENT_PER_USER)):
            if (db.scalar(select(func.count(AutomationRun.id)).where(*conditions)) or 0) >= limit:
                raise ConflictError("Automation concurrency limit reached. Wait for an active run to finish.")
        snapshot = snapshot_suite(db, suite, environment, payload.confirm_production)
        run = AutomationRun(project_id=suite.project_id, suite_id=suite.id, environment_id=environment.id if environment else None,
                            triggered_by=user.id, trigger_type=trigger_type, schedule_id=schedule_id, status="QUEUED",
                            config_snapshot=protect_step_config(snapshot), total_cases=len(suite.cases),
                            total_steps=sum(len(case.steps) for case in suite.cases))
        db.add(run)
        db.flush()
        audit(db, suite.project_id, user.id, "AUTOMATION_EXECUTED", "run", run.id)
        db.commit()
        if enqueue:
            try:
                queue.enqueue_run(run.id)
            except (redis.RedisError, OSError) as exc:
                run.status = "FAILED"
                run.error_message = "Automation queue unavailable. Run was not started."
                run.completed_at = _now()
                db.commit()
                raise QueueUnavailableError() from exc
        return run


def get_run(db, run_id, user, manage=False):
    run = db.scalar(select(AutomationRun).options(selectinload(AutomationRun.results)).where(AutomationRun.id == run_id))
    if run is None:
        raise NotFoundError("Automation run not found.")
    (_manage if manage else get_project_for_read)(db, run.project_id, user)
    return run


def run_out(db, run, detail=False):
    data = RunOut.model_validate(run).model_dump()
    data["suite_name"] = run.suite.name
    environment = db.get(ApiEnvironment, run.environment_id) if run.environment_id else None
    data["environment_name"] = environment.name if environment else None
    if detail:
        data["results"] = run.results
        bugs = db.scalars(select(Bug).where(Bug.discovered_from_automation_run_id == run.id, Bug.is_archived.is_(False)))
        data["linked_bugs"] = [{"id": str(bug.id), "bug_key": bug.bug_key, "title": bug.title, "status": bug.status.value} for bug in bugs]
        return RunDetail.model_validate(data)
    return RunOut.model_validate(data)


def _run_filters(project_id, suite_id=None, environment_id=None, status=None, created_from=None, created_to=None):
    conditions = [AutomationRun.project_id == project_id]
    for column, value in ((AutomationRun.suite_id, suite_id), (AutomationRun.environment_id, environment_id), (AutomationRun.status, status)):
        if value is not None:
            conditions.append(column == value)
    if created_from:
        conditions.append(AutomationRun.created_at >= datetime.combine(created_from, time.min, tzinfo=timezone.utc))
    if created_to:
        conditions.append(AutomationRun.created_at < datetime.combine(created_to, time.min, tzinfo=timezone.utc) + timedelta(days=1))
    return conditions


def list_runs(db, project_id, user, page=1, page_size=20, **filters):
    get_project_for_read(db, project_id, user)
    conditions = _run_filters(project_id, **filters)
    total = db.scalar(select(func.count(AutomationRun.id)).where(*conditions)) or 0
    rows = db.scalars(select(AutomationRun).where(*conditions).order_by(AutomationRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    return _page([run_out(db, row) for row in rows], total, page, page_size)


def stop_run(db, run_id, user):
    run = get_run(db, run_id, user, True)
    if run.status in ACTIVE_STATUSES:
        run.stop_requested = True
        if run.status == "QUEUED":
            run.status = "CANCELLED"
            run.completed_at = _now()
        audit(db, run.project_id, user.id, "AUTOMATION_STOPPED", "run", run.id)
        db.commit()
        try:
            queue.request_stop(run.id)
        except (redis.RedisError, OSError):
            pass  # The durable database cancellation flag is also checked by the worker.
    return run_out(db, run)


def _validate_schedule(db, payload, suite):
    environment = _environment(db, payload.environment_id or suite.environment_id, suite.project_id)
    if environment and environment.classification == "PRODUCTION":
        raise ForbiddenError("Production environments cannot be scheduled.")
    if payload.enabled and suite.status != "ACTIVE":
        raise ConflictError("Activate the suite before enabling its schedule.")
    if payload.enabled and not suite.allowed_hosts:
        raise ValidationAppError("Configure allowed hosts before enabling a schedule.")
    return next_execution(payload.cron_expression, payload.timezone)


def create_schedule(db, project_id, payload, user):
    _manage(db, project_id, user)
    suite = get_suite(db, payload.suite_id, user, True)
    if suite.project_id != project_id:
        raise NotFoundError("Suite not found in this project.")
    next_run = _validate_schedule(db, payload, suite)
    schedule = AutomationSchedule(project_id=project_id, created_by=user.id, next_run_at=next_run if payload.enabled else None, **payload.model_dump())
    db.add(schedule)
    db.flush()
    audit(db, project_id, user.id, "SCHEDULE_CREATED", "schedule", schedule.id)
    db.commit()
    return ScheduleOut.model_validate(schedule)


def _schedule(db, schedule_id, user):
    schedule = db.get(AutomationSchedule, schedule_id)
    if schedule is None:
        raise NotFoundError("Automation schedule not found.")
    _manage(db, schedule.project_id, user)
    return schedule


def update_schedule(db, schedule_id, payload, user):
    schedule = _schedule(db, schedule_id, user)
    data = {key: getattr(schedule, key) for key in ScheduleCreate.model_fields}
    data.update(payload.model_dump(exclude_unset=True))
    try:
        validated = ScheduleCreate.model_validate(data)
    except ValidationError as exc:
        raise ValidationAppError("Invalid schedule configuration.") from exc
    suite = get_suite(db, schedule.suite_id, user, True)
    next_run = _validate_schedule(db, validated, suite)
    action = "SCHEDULE_UPDATED" if schedule.enabled == validated.enabled else ("SCHEDULE_ENABLED" if validated.enabled else "SCHEDULE_DISABLED")
    for key, value in validated.model_dump().items():
        setattr(schedule, key, value)
    schedule.next_run_at = next_run if schedule.enabled else None
    schedule.last_error = None
    audit(db, schedule.project_id, user.id, action, "schedule", schedule.id)
    db.commit()
    return ScheduleOut.model_validate(schedule)


def delete_schedule(db, schedule_id, user):
    schedule = _schedule(db, schedule_id, user)
    audit(db, schedule.project_id, user.id, "SCHEDULE_DELETED", "schedule", schedule.id)
    db.delete(schedule)
    db.commit()


def list_schedules(db, project_id, user, page=1, page_size=20):
    get_project_for_read(db, project_id, user)
    conditions = [AutomationSchedule.project_id == project_id]
    total = db.scalar(select(func.count(AutomationSchedule.id)).where(*conditions)) or 0
    rows = db.scalars(select(AutomationSchedule).where(*conditions).order_by(AutomationSchedule.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    return _page([ScheduleOut.model_validate(row) for row in rows], total, page, page_size)


def statistics(db, project_id, user, **filters):
    get_project_for_read(db, project_id, user)
    conditions = _run_filters(project_id, **filters)
    counts = dict(db.execute(select(AutomationRun.status, func.count(AutomationRun.id)).where(*conditions).group_by(AutomationRun.status)).all())
    completed = counts.get("PASSED", 0) + counts.get("FAILED", 0)
    recent = db.scalars(select(AutomationRun).where(*conditions).order_by(AutomationRun.created_at.desc()).limit(10))
    failures = db.scalars(select(AutomationRun).where(*conditions, AutomationRun.status == "FAILED").order_by(AutomationRun.created_at.desc()).limit(10))
    trends = db.execute(select(func.date(AutomationRun.created_at), func.count(AutomationRun.id)).where(*conditions, AutomationRun.status == "FAILED").group_by(func.date(AutomationRun.created_at)).order_by(func.date(AutomationRun.created_at))).all()
    return {"total_suites": db.scalar(select(func.count(AutomationTestSuite.id)).where(AutomationTestSuite.project_id == project_id, AutomationTestSuite.status != "ARCHIVED")) or 0,
            "active_schedules": db.scalar(select(func.count(AutomationSchedule.id)).where(AutomationSchedule.project_id == project_id, AutomationSchedule.enabled.is_(True))) or 0,
            "total_runs": sum(counts.values()), "pass_rate": counts.get("PASSED", 0) * 100 / completed if completed else 0,
            "failure_rate": counts.get("FAILED", 0) * 100 / completed if completed else 0,
            "average_duration_ms": db.scalar(select(func.avg(AutomationRun.duration_ms)).where(*conditions, AutomationRun.status.in_({"PASSED", "FAILED"}))) or 0,
            "recent_runs": [run_out(db, row) for row in recent], "recent_failures": [run_out(db, row) for row in failures],
            "failed_trends": [{"date": str(day), "count": count} for day, count in trends]}


def list_audit(db, project_id, user, page=1, page_size=20):
    get_project_for_read(db, project_id, user)
    total = db.scalar(select(func.count(AutomationAuditLog.id)).where(AutomationAuditLog.project_id == project_id)) or 0
    rows = db.scalars(select(AutomationAuditLog).where(AutomationAuditLog.project_id == project_id).order_by(AutomationAuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    return _page([{key: getattr(row, key) for key in ("id", "project_id", "user_id", "action", "resource_type", "resource_id", "created_at")} for row in rows], total, page, page_size)
