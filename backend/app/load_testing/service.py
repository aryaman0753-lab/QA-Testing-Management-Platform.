import csv
import io
import math
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import redis
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api_testing.secrets import MASK, decrypt, mask_auth, mask_key_values, protect_auth, protect_key_values
from app.api_testing.variables import VariableResolver
from app.bugs import service as bug_service
from app.bugs.schemas import BugDetail
from app.common.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.core.config import get_settings
from app.database.models.api_testing import ApiEnvironment, ApiRequest
from app.database.models.bug import BugHistory, BugPriority, BugSeverity
from app.database.models.load_testing import (
    EnvironmentClassification, LoadTargetType, LoadTest, LoadTestAuditLog, LoadTestResultStatus,
    LoadTestRun, LoadTestStatus,
)
from app.database.models.project import Project
from app.database.models.user import User, UserRole
from app.load_testing.queue import get_load_queue
from app.load_testing.schemas import (
    AllowlistSettings, BugFromLoadRunCreate, ComparisonOut, LoadRunDetail,
    LoadRunOut, LoadTestCreate, LoadTestOut, PaginatedLoadRuns, Thresholds,
)
from app.load_testing.security import validate_load_target
from app.load_testing.state import transition_run
from app.projects.service import get_project_for_read

MANAGE_ROLES = {UserRole.ADMIN, UserRole.QA_ENGINEER}
ACTIVE_STATUSES = {LoadTestStatus.QUEUED, LoadTestStatus.STARTING, LoadTestStatus.RUNNING, LoadTestStatus.STOPPING}


class QueueUnavailableError(AppError):
    status_code = 503
    detail = "The load-test queue is unavailable. Try again later."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _audit(db: Session, project_id: uuid.UUID, user_id: uuid.UUID, action: str, resource_type: str, resource_id: uuid.UUID | None) -> None:
    db.add(LoadTestAuditLog(project_id=project_id, user_id=user_id, action=action, resource_type=resource_type, resource_id=resource_id))


def _read(db: Session, project_id: uuid.UUID, user: User) -> Project:
    return get_project_for_read(db, project_id, user)


def _manage(db: Session, project_id: uuid.UUID, user: User) -> Project:
    project = _read(db, project_id, user)
    if user.role not in MANAGE_ROLES:
        raise ForbiddenError("Only administrators and QA engineers can manage load tests.")
    return project


def _test_query():
    return select(LoadTest).options(joinedload(LoadTest.environment), joinedload(LoadTest.api_request))


def get_test(db: Session, test_id: uuid.UUID, user: User, manage: bool = False) -> LoadTest:
    item = db.scalar(_test_query().where(LoadTest.id == test_id, LoadTest.is_archived.is_(False)))
    if item is None:
        raise NotFoundError("Load test not found.")
    (_manage if manage else _read)(db, item.project_id, user)
    return item


def _effective_request(item: LoadTest):
    return item.api_request or item


def load_test_out(item: LoadTest) -> LoadTestOut:
    source = _effective_request(item)
    return LoadTestOut.model_validate({
        "id": item.id, "project_id": item.project_id, "name": item.name, "description": item.description, "target_type": item.target_type,
        "api_request_id": item.api_request_id, "environment_id": item.environment_id,
        "environment_name": item.environment.name, "environment_classification": item.environment.classification,
        "target_url": source.url if item.api_request else item.target_url,
        "request_method": source.method if item.api_request else item.request_method,
        "headers": mask_key_values(source.headers), "query_parameters": mask_key_values(source.query_parameters),
        "body": source.body, "body_type": source.body_type, "authentication_type": source.authentication_type,
        "authentication_config": mask_auth(source.authentication_config), "profile": item.profile,
        "virtual_users": item.virtual_users, "spawn_rate": item.spawn_rate, "duration_seconds": item.duration_seconds,
        "timeout_seconds": item.timeout_seconds, "target_rps": item.target_rps, "thresholds": item.thresholds,
        "status": item.status, "created_by": item.created_by, "created_at": item.created_at, "updated_at": item.updated_at,
    })


def _validate_limits(payload: LoadTestCreate) -> None:
    settings = get_settings()
    if payload.virtual_users > settings.LOAD_TEST_MAX_USERS:
        raise ValidationAppError(f"Virtual users cannot exceed {settings.LOAD_TEST_MAX_USERS}.")
    if payload.spawn_rate > settings.LOAD_TEST_MAX_SPAWN_RATE:
        raise ValidationAppError(f"Spawn rate cannot exceed {settings.LOAD_TEST_MAX_SPAWN_RATE:g} users/second.")
    if payload.duration_seconds > settings.LOAD_TEST_MAX_DURATION_SECONDS:
        raise ValidationAppError(f"Duration cannot exceed {settings.LOAD_TEST_MAX_DURATION_SECONDS} seconds.")
    if payload.target_rps and payload.target_rps > settings.LOAD_TEST_MAX_TARGET_RPS:
        raise ValidationAppError(f"Target RPS cannot exceed {settings.LOAD_TEST_MAX_TARGET_RPS:g}.")
    if payload.spawn_rate > payload.virtual_users * 10:
        raise ValidationAppError("Spawn rate is disproportionately high for the configured user count.")


def _environment(db: Session, environment_id: uuid.UUID, project_id: uuid.UUID) -> ApiEnvironment:
    environment = db.get(ApiEnvironment, environment_id)
    if environment is None or environment.project_id != project_id:
        raise ValidationAppError("Environment must belong to this project.")
    return environment


def _source_request(db: Session, request_id: uuid.UUID | None, project_id: uuid.UUID) -> ApiRequest | None:
    if request_id is None:
        return None
    request = db.get(ApiRequest, request_id)
    if request is None or request.project_id != project_id or request.is_archived:
        raise ValidationAppError("Source API request must be active and belong to this project.")
    return request


def _preserve_masked(incoming: list[dict], current: list[dict]) -> list[dict]:
    existing = {str(row.get("key", "")).lower(): row.get("value", "") for row in current}
    rows = []
    for row in incoming:
        copied = dict(row)
        if copied.get("value") == MASK:
            copied["value"] = existing.get(str(copied.get("key", "")).lower(), MASK)
        rows.append(copied)
    return rows


def _apply(item: LoadTest, payload: LoadTestCreate, current: LoadTest | None = None) -> None:
    item.name = payload.name; item.description = payload.description; item.target_type = LoadTargetType.API_REQUEST if payload.api_request_id else LoadTargetType.URL; item.api_request_id = payload.api_request_id; item.environment_id = payload.environment_id
    item.target_url = payload.target_url; item.request_method = payload.request_method; item.body = payload.body; item.body_type = payload.body_type
    item.authentication_type = payload.authentication_type; item.profile = payload.profile; item.virtual_users = payload.virtual_users
    item.spawn_rate = payload.spawn_rate; item.duration_seconds = payload.duration_seconds; item.timeout_seconds = payload.timeout_seconds
    item.target_rps = payload.target_rps; item.thresholds = payload.thresholds.model_dump(exclude_none=True)
    if payload.api_request_id:
        item.headers = []; item.query_parameters = []; item.authentication_config = {}
    else:
        headers = _preserve_masked([row.model_dump() for row in payload.headers], current.headers if current else [])
        params = _preserve_masked([row.model_dump() for row in payload.query_parameters], current.query_parameters if current else [])
        auth = dict(payload.authentication_config)
        if current:
            auth = {key: current.authentication_config.get(key, value) if value == MASK else value for key, value in auth.items()}
        item.headers = protect_key_values(headers); item.query_parameters = protect_key_values(params)
        item.authentication_config = protect_auth(payload.authentication_type.value, auth)


def create_test(db: Session, project_id: uuid.UUID, payload: LoadTestCreate, user: User) -> LoadTestOut:
    _manage(db, project_id, user); _validate_limits(payload); _environment(db, payload.environment_id, project_id); _source_request(db, payload.api_request_id, project_id)
    if db.scalar(select(LoadTest.id).where(LoadTest.project_id == project_id, func.lower(LoadTest.name) == payload.name.lower(), LoadTest.is_archived.is_(False))):
        raise ConflictError("A load test with this name already exists in the project.")
    item = LoadTest(project_id=project_id, name=payload.name, environment_id=payload.environment_id, target_url=payload.target_url, request_method=payload.request_method, created_by=user.id)
    _apply(item, payload); db.add(item); db.flush(); _audit(db, project_id, user.id, "LOAD_TEST_CREATED", "load_test", item.id); db.commit()
    return load_test_out(get_test(db, item.id, user))


def list_tests(db: Session, project_id: uuid.UUID, user: User) -> list[LoadTestOut]:
    _read(db, project_id, user)
    return [load_test_out(item) for item in db.scalars(_test_query().where(LoadTest.project_id == project_id, LoadTest.is_archived.is_(False)).order_by(LoadTest.updated_at.desc()))]


def update_test(db: Session, test_id: uuid.UUID, payload: LoadTestCreate, user: User) -> LoadTestOut:
    item = get_test(db, test_id, user, manage=True); _validate_limits(payload); _environment(db, payload.environment_id, item.project_id); _source_request(db, payload.api_request_id, item.project_id)
    active = db.scalar(select(func.count(LoadTestRun.id)).where(LoadTestRun.load_test_id == item.id, LoadTestRun.status.in_(ACTIVE_STATUSES))) or 0
    if active:
        raise ConflictError("A load test cannot be edited while it has an active run.")
    _apply(item, payload, current=item); _audit(db, item.project_id, user.id, "LOAD_TEST_UPDATED", "load_test", item.id); db.commit()
    return load_test_out(get_test(db, item.id, user))


def archive_test(db: Session, test_id: uuid.UUID, user: User) -> None:
    item = get_test(db, test_id, user, manage=True)
    if db.scalar(select(func.count(LoadTestRun.id)).where(LoadTestRun.load_test_id == item.id, LoadTestRun.status.in_(ACTIVE_STATUSES))):
        raise ConflictError("Stop the active run before archiving this test.")
    item.is_archived = True; _audit(db, item.project_id, user.id, "LOAD_TEST_ARCHIVED", "load_test", item.id); db.commit()


def get_settings_for_project(db: Session, project_id: uuid.UUID, user: User) -> AllowlistSettings:
    project = _read(db, project_id, user)
    return AllowlistSettings(enabled=project.load_allowlist_enabled, allowed_hosts=project.load_allowed_hosts)


def update_settings(db: Session, project_id: uuid.UUID, payload: AllowlistSettings, user: User) -> AllowlistSettings:
    project = _manage(db, project_id, user)
    cleaned = sorted({host.strip().lower().rstrip(".") for host in payload.allowed_hosts if host.strip()})
    if any("://" in host or "/" in host for host in cleaned):
        raise ValidationAppError("Allowed hosts must be hostnames, not URLs.")
    project.load_allowlist_enabled = payload.enabled; project.load_allowed_hosts = cleaned
    _audit(db, project_id, user.id, "LOAD_ALLOWLIST_UPDATED", "project", project.id); db.commit()
    return AllowlistSettings(enabled=project.load_allowlist_enabled, allowed_hosts=project.load_allowed_hosts)


def _environment_values(environment: ApiEnvironment) -> dict[str, str]:
    return {key: decrypt(row.get("value", "")) if row.get("is_secret") else row.get("value", "") for key, row in environment.variables.items()}


def _resolved_url(item: LoadTest) -> str:
    source = _effective_request(item)
    return VariableResolver(_environment_values(item.environment)).resolve(source.url if item.api_request else item.target_url)


def recover_stale_runs(db: Session) -> int:
    cutoff = _now() - timedelta(seconds=get_settings().LOAD_TEST_STALE_RUN_SECONDS)
    rows = list(db.scalars(select(LoadTestRun).where(
        LoadTestRun.status.in_(ACTIVE_STATUSES),
        or_(LoadTestRun.heartbeat_at < cutoff, (LoadTestRun.heartbeat_at.is_(None) & (LoadTestRun.created_at < cutoff))),
    )))
    for row in rows:
        transition_run(row, LoadTestStatus.FAILED); row.result_status = LoadTestResultStatus.ERROR; row.completed_at = _now(); row.error_message = "Load worker heartbeat expired."
    if rows: db.commit()
    return len(rows)


def cleanup_expired_runs(db: Session) -> int:
    """Delete non-baseline terminal results after the configured retention period."""
    retention_days = get_settings().LOAD_TEST_RESULT_RETENTION_DAYS
    if retention_days is None:
        return 0
    cutoff = _now() - timedelta(days=retention_days)
    rows = list(db.scalars(select(LoadTestRun).where(
        LoadTestRun.status.in_({LoadTestStatus.COMPLETED, LoadTestStatus.FAILED, LoadTestStatus.CANCELLED}),
        LoadTestRun.is_baseline.is_(False), LoadTestRun.completed_at < cutoff,
    )))
    for row in rows:
        db.delete(row)
    if rows:
        db.commit()
    return len(rows)


def _check_concurrency(db: Session, item: LoadTest, user: User) -> None:
    settings = get_settings(); recover_stale_runs(db)
    user_count = db.scalar(select(func.count(LoadTestRun.id)).where(LoadTestRun.created_by == user.id, LoadTestRun.status.in_(ACTIVE_STATUSES))) or 0
    project_count = db.scalar(select(func.count(LoadTestRun.id)).where(LoadTestRun.project_id == item.project_id, LoadTestRun.status.in_(ACTIVE_STATUSES))) or 0
    global_count = db.scalar(select(func.count(LoadTestRun.id)).where(LoadTestRun.status.in_(ACTIVE_STATUSES))) or 0
    if user_count >= settings.LOAD_TEST_MAX_CONCURRENT_PER_USER: raise ConflictError("Your concurrent load-test limit has been reached.")
    if project_count >= settings.LOAD_TEST_MAX_CONCURRENT_PER_PROJECT: raise ConflictError("The project's concurrent load-test limit has been reached.")
    if global_count >= settings.LOAD_TEST_MAX_CONCURRENT_RUNS: raise ConflictError("The server's concurrent load-test limit has been reached.")


async def start_run(db: Session, test_id: uuid.UUID, user: User, confirm_production: bool = False) -> LoadRunOut:
    item = get_test(db, test_id, user, manage=True); settings = get_settings(); _check_concurrency(db, item, user)
    classification = EnvironmentClassification(item.environment.classification)
    if classification == EnvironmentClassification.PRODUCTION:
        if user.role != UserRole.ADMIN or not settings.LOAD_TEST_ALLOW_PRODUCTION:
            raise ForbiddenError("Production load testing requires an administrator and explicit server enablement.")
        if not confirm_production:
            raise ValidationAppError("Explicit production confirmation is required.")
        if item.virtual_users > settings.LOAD_TEST_PRODUCTION_MAX_USERS:
            raise ValidationAppError(f"Production load tests cannot exceed {settings.LOAD_TEST_PRODUCTION_MAX_USERS} virtual users.")
        if item.duration_seconds > settings.LOAD_TEST_PRODUCTION_MAX_DURATION_SECONDS:
            raise ValidationAppError(f"Production load tests cannot exceed {settings.LOAD_TEST_PRODUCTION_MAX_DURATION_SECONDS} seconds.")
        if item.target_rps and item.target_rps > settings.LOAD_TEST_PRODUCTION_MAX_TARGET_RPS:
            raise ValidationAppError(f"Production load tests cannot exceed {settings.LOAD_TEST_PRODUCTION_MAX_TARGET_RPS:g} RPS.")
    resolved_url = _resolved_url(item)
    project = db.scalar(select(Project).where(Project.id == item.project_id).with_for_update())
    await validate_load_target(resolved_url, project.load_allowed_hosts, project.load_allowlist_enabled)
    project.next_load_run_number += 1
    safe_target = urlsplit(resolved_url)._replace(query="", fragment="").geturl()
    run = LoadTestRun(load_test_id=item.id, project_id=item.project_id, run_number=project.next_load_run_number, status=LoadTestStatus.QUEUED,
        virtual_users=item.virtual_users, spawn_rate=item.spawn_rate, duration_seconds=item.duration_seconds, created_by=user.id,
        config_snapshot={"test_name": item.name, "environment_name": item.environment.name, "environment_classification": classification.value,
                         "target_url": safe_target, "method": _effective_request(item).method.value if item.api_request else item.request_method.value,
                         "virtual_users": item.virtual_users, "spawn_rate": item.spawn_rate, "duration_seconds": item.duration_seconds,
                         "timeout_seconds": item.timeout_seconds, "target_rps": item.target_rps, "thresholds": item.thresholds})
    db.add(run); db.flush(); _audit(db, item.project_id, user.id, "LOAD_RUN_QUEUED", "run", run.id); db.commit()
    try: get_load_queue().enqueue(run.id)
    except redis.RedisError as exc:
        transition_run(run, LoadTestStatus.FAILED); run.result_status = LoadTestResultStatus.ERROR; run.completed_at = _now(); run.error_message = "Load-test queue unavailable."; db.commit()
        raise QueueUnavailableError() from exc
    return run_out(get_run(db, run.id, user))


def _run_query():
    return select(LoadTestRun).options(joinedload(LoadTestRun.load_test), selectinload(LoadTestRun.metrics), selectinload(LoadTestRun.endpoints), selectinload(LoadTestRun.errors))


def get_run(db: Session, run_id: uuid.UUID, user: User) -> LoadTestRun:
    run = db.scalar(_run_query().where(LoadTestRun.id == run_id))
    if run is None: raise NotFoundError("Load-test run not found.")
    _read(db, run.project_id, user); return run


def run_out(run: LoadTestRun) -> LoadRunOut:
    values = {name: getattr(run, name) for name in LoadRunOut.model_fields if name not in {"run_key", "load_test_name"}}
    values.update(run_key=run.run_key, load_test_name=run.load_test.name)
    return LoadRunOut.model_validate(values)


def run_detail(run: LoadTestRun) -> LoadRunDetail:
    values = run_out(run).model_dump(); values.update(metrics=run.metrics, endpoints=run.endpoints, errors=run.errors)
    return LoadRunDetail.model_validate(values)


def list_runs(db: Session, project_id: uuid.UUID, user: User, page: int, page_size: int) -> PaginatedLoadRuns:
    _read(db, project_id, user); recover_stale_runs(db); cleanup_expired_runs(db)
    query = select(LoadTestRun).where(LoadTestRun.project_id == project_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(db.scalars(_run_query().where(LoadTestRun.project_id == project_id).order_by(LoadTestRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).unique())
    return PaginatedLoadRuns(items=[run_out(row) for row in rows], page=page, page_size=page_size, total=total, total_pages=math.ceil(total / page_size) if total else 0)


def stop_run(db: Session, run_id: uuid.UUID, user: User) -> LoadRunOut:
    run = get_run(db, run_id, user); _manage(db, run.project_id, user)
    if run.status not in {LoadTestStatus.QUEUED, LoadTestStatus.STARTING, LoadTestStatus.RUNNING}:
        raise ConflictError("Only a queued or running load test can be stopped.")
    transition_run(run, LoadTestStatus.STOPPING); _audit(db, run.project_id, user.id, "LOAD_RUN_STOP_REQUESTED", "run", run.id); db.commit()
    try: get_load_queue().request_stop(run.id)
    except redis.RedisError as exc: raise QueueUnavailableError() from exc
    return run_out(get_run(db, run.id, user))


def mark_baseline(db: Session, run_id: uuid.UUID, user: User) -> LoadRunOut:
    run = get_run(db, run_id, user); _manage(db, run.project_id, user)
    if run.status != LoadTestStatus.COMPLETED: raise ValidationAppError("Only completed runs can be baselines.")
    db.execute(update(LoadTestRun).where(LoadTestRun.load_test_id == run.load_test_id).values(is_baseline=False)); run.is_baseline = True
    _audit(db, run.project_id, user.id, "LOAD_BASELINE_SET", "run", run.id); db.commit(); return run_out(get_run(db, run.id, user))


def compare_runs(db: Session, project_id: uuid.UUID, run_a_id: uuid.UUID, run_b_id: uuid.UUID, user: User) -> ComparisonOut:
    _read(db, project_id, user); a, b = get_run(db, run_a_id, user), get_run(db, run_b_id, user)
    if a.project_id != project_id or b.project_id != project_id: raise NotFoundError("Load-test run not found.")
    fields = ["avg_response_time", "p95_response_time", "p99_response_time", "requests_per_second", "failure_rate", "total_requests"]
    metrics = []
    for field in fields:
        value_a, value_b = float(getattr(a, field)), float(getattr(b, field))
        difference = value_b - value_a
        metrics.append({"metric": field, "run_a": value_a, "run_b": value_b, "difference": difference,
                        "percent_change": (difference / value_a * 100) if value_a else None})
    return ComparisonOut(run_a=run_out(a), run_b=run_out(b), metrics=metrics)


def report_data(run: LoadTestRun) -> dict:
    def columns(row):
        return {column.name: getattr(row, column.name) for column in row.__table__.columns if column.name != "run_id"}
    return {"run": run_out(run).model_dump(mode="json"), "metrics": [columns(row) for row in run.metrics],
            "endpoints": [columns(row) for row in run.endpoints], "errors": [columns(row) for row in run.errors]}


def report_csv(run: LoadTestRun) -> str:
    output = io.StringIO(); writer = csv.writer(output); writer.writerow(["Metric", "Value"])
    summary = [
        ("Run", run.run_key), ("Run ID", run.id), ("Test", run.load_test.name),
        ("Environment", run.config_snapshot.get("environment_name")), ("Target", run.config_snapshot.get("target_url")),
        ("Method", run.config_snapshot.get("method")), ("Status", run.status.value),
        ("Result", run.result_status.value if run.result_status else ""), ("Started at", run.started_at),
        ("Completed at", run.completed_at), ("Users", run.virtual_users), ("Spawn rate", run.spawn_rate),
        ("Duration seconds", run.duration_seconds), ("Total requests", run.total_requests),
        ("Successful requests", run.successful_requests), ("Failed requests", run.failed_requests),
        ("RPS", run.requests_per_second), ("Failure rate", run.failure_rate), ("Average ms", run.avg_response_time),
        ("Minimum ms", run.min_response_time), ("Maximum ms", run.max_response_time),
        ("P50 ms", run.p50_response_time), ("P75 ms", run.p75_response_time), ("P90 ms", run.p90_response_time),
        ("P95 ms", run.p95_response_time), ("P99 ms", run.p99_response_time),
    ]
    for label, value in summary:
        writer.writerow([label, value])
    writer.writerow([]); writer.writerow(["Threshold", "Measured", "Operator", "Limit", "Unit", "Passed"])
    for row in run.threshold_results:
        writer.writerow([row.get("label"), row.get("measured"), row.get("operator"), row.get("threshold"), row.get("unit"), row.get("passed")])
    writer.writerow([]); writer.writerow(["Error type", "Method", "Path", "Status", "Message", "Count"])
    for row in run.errors:
        writer.writerow([row.error_type, row.method, row.path, row.status_code, row.message, row.count])
    return output.getvalue()


def bug_suggestion(db: Session, run_id: uuid.UUID, user: User) -> dict:
    run = get_run(db, run_id, user)
    failures = [row for row in run.threshold_results if not row.get("passed")]
    if not failures: raise ValidationAppError("This run has no threshold violations.")
    lines = ["Load test exceeded configured performance thresholds.", "", f"Test: {run.load_test.name}", f"Run: {run.run_key}", f"Endpoint: {run.config_snapshot.get('method')} {run.config_snapshot.get('target_url')}", "", "Threshold violations:"]
    lines.extend(f"- {row['label']}: measured {row['measured']} {row['unit']}; required {row['operator']} {row['threshold']} {row['unit']}" for row in failures)
    return {"title": f"Performance threshold exceeded — {run.load_test.name}", "description": "\n".join(lines), "steps_to_reproduce": [f"Run {run.run_key} with the recorded configuration"], "expected_result": "All configured performance thresholds should pass.", "actual_result": f"{len(failures)} performance threshold(s) were exceeded.", "severity": BugSeverity.MEDIUM, "priority": BugPriority.HIGH, "environment": run.config_snapshot.get("environment_name", "Load Test")}


def create_bug_from_run(db: Session, run_id: uuid.UUID, payload: BugFromLoadRunCreate, user: User) -> BugDetail:
    run = get_run(db, run_id, user); _manage(db, run.project_id, user)
    if not any(not row.get("passed") for row in run.threshold_results): raise ValidationAppError("A bug can only be linked to a threshold violation.")
    bug = bug_service.create_bug(db, run.project_id, payload, user); bug.discovered_from_load_test_run_id = run.id
    db.add(BugHistory(bug_id=bug.id, user_id=user.id, action="LOAD_SOURCE_LINKED", field_name="discovered_from_load_test_run_id", old_value=None, new_value=str(run.id), created_at=_now()))
    db.commit(); return BugDetail.model_validate(bug_service.get_bug(db, bug.id, user))
