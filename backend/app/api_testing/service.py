import json
import math
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api_testing.assertions import AssertionEngine, ResponseSnapshot
from app.api_testing.engine import ApiExecutionService, ExecutionOutcome
from app.api_testing.jsonpath import MISSING, json_path_get
from app.api_testing.schemas import (
    ApiAnalytics, BugFromResultCreate, CollectionCreate, CollectionDetail,
    CollectionOut, EnvironmentCreate, EnvironmentOut, ExecuteInput,
    HealthCheckInput, HealthCheckResult, PaginatedRuns, RequestCreate,
    RequestOut, ResultOut, RunDetail, RunListItem,
)
from app.api_testing.secrets import (
    MASK, decrypt, encrypt, mask_auth, mask_key_values, mask_response_headers,
    protect_auth, protect_key_values,
)
from app.bugs import service as bug_service
from app.bugs.schemas import BugDetail
from app.common.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.database.models.api_testing import (
    ApiAssertion, ApiAuditLog, ApiCollection, ApiEnvironment, ApiExtractor,
    ApiRequest, ApiTestResult, ApiTestRun, AssertionOperator, AssertionType,
    AuthenticationType, BodyType, ExecutionStatus, HttpMethod,
)
from app.database.models.bug import BugHistory
from app.database.models.bug import BugPriority, BugSeverity
from app.database.models.project import Project
from app.database.models.project_member import ProjectMember
from app.database.models.user import User, UserRole
from app.projects.service import get_project_for_read

MANAGE_ROLES = {UserRole.ADMIN, UserRole.QA_ENGINEER}
EXECUTE_ROLES = {UserRole.ADMIN, UserRole.QA_ENGINEER, UserRole.DEVELOPER}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _audit(db: Session, project_id: uuid.UUID, user: User, action: str, resource_type: str, resource_id: uuid.UUID | None) -> None:
    db.add(ApiAuditLog(project_id=project_id, user_id=user.id, action=action, resource_type=resource_type, resource_id=resource_id))


def _require_project_read(db: Session, project_id: uuid.UUID, user: User) -> Project:
    return get_project_for_read(db, project_id, user)


def _require_manage(db: Session, project_id: uuid.UUID, user: User) -> Project:
    project = _require_project_read(db, project_id, user)
    if user.role not in MANAGE_ROLES:
        raise ForbiddenError("Only administrators and QA engineers can modify API tests.")
    return project


def _require_execute(db: Session, project_id: uuid.UUID, user: User) -> Project:
    project = _require_project_read(db, project_id, user)
    if user.role not in EXECUTE_ROLES:
        raise ForbiddenError("You do not have permission to execute API tests.")
    return project


def _collection_query():
    return select(ApiCollection).options(selectinload(ApiCollection.requests).selectinload(ApiRequest.assertions), selectinload(ApiCollection.requests).selectinload(ApiRequest.extractors))


def get_collection(db: Session, collection_id: uuid.UUID, user: User, manage: bool = False) -> ApiCollection:
    collection = db.scalar(_collection_query().where(ApiCollection.id == collection_id, ApiCollection.is_archived.is_(False)))
    if collection is None:
        raise NotFoundError("API collection not found.")
    (_require_manage if manage else _require_project_read)(db, collection.project_id, user)
    collection.requests.sort(key=lambda item: (item.position, item.created_at))
    return collection


def _request_query():
    return select(ApiRequest).options(joinedload(ApiRequest.collection), selectinload(ApiRequest.assertions), selectinload(ApiRequest.extractors))


def get_request(db: Session, request_id: uuid.UUID, user: User, manage: bool = False) -> ApiRequest:
    request = db.scalar(_request_query().where(ApiRequest.id == request_id, ApiRequest.is_archived.is_(False)))
    if request is None or request.collection.is_archived:
        raise NotFoundError("API request not found.")
    (_require_manage if manage else _require_project_read)(db, request.project_id, user)
    request.assertions.sort(key=lambda item: item.position)
    request.extractors.sort(key=lambda item: item.position)
    return request


def collection_out(collection: ApiCollection, detail: bool = False):
    payload = CollectionOut.model_validate(collection).model_dump()
    payload["request_count"] = len([item for item in collection.requests if not item.is_archived])
    if detail:
        payload["requests"] = [request_out(item) for item in collection.requests if not item.is_archived]
        return CollectionDetail.model_validate(payload)
    return CollectionOut.model_validate(payload)


def request_out(request: ApiRequest) -> RequestOut:
    data = {
        "id": request.id, "project_id": request.project_id, "collection_id": request.collection_id,
        "name": request.name, "description": request.description, "method": request.method,
        "url": request.url, "headers": mask_key_values(request.headers),
        "query_parameters": mask_key_values(request.query_parameters), "body": request.body,
        "body_type": request.body_type, "authentication_type": request.authentication_type,
        "authentication_config": mask_auth(request.authentication_config), "assertions": request.assertions,
        "extractors": request.extractors, "position": request.position, "created_by": request.created_by,
        "created_at": request.created_at, "updated_at": request.updated_at,
    }
    return RequestOut.model_validate(data)


def create_collection(db: Session, project_id: uuid.UUID, payload: CollectionCreate, user: User) -> CollectionOut:
    _require_manage(db, project_id, user)
    existing = db.scalar(select(ApiCollection).where(ApiCollection.project_id == project_id, func.lower(ApiCollection.name) == payload.name.lower()))
    if existing:
        raise ConflictError("A collection with this name already exists in the project.")
    collection = ApiCollection(project_id=project_id, created_by=user.id, **payload.model_dump())
    db.add(collection); db.flush(); _audit(db, project_id, user, "COLLECTION_CREATED", "collection", collection.id); db.commit()
    return collection_out(get_collection(db, collection.id, user))


def list_collections(db: Session, project_id: uuid.UUID, user: User) -> list[CollectionOut]:
    _require_project_read(db, project_id, user)
    rows = list(db.scalars(_collection_query().where(ApiCollection.project_id == project_id, ApiCollection.is_archived.is_(False)).order_by(ApiCollection.name)))
    return [collection_out(row) for row in rows]


def update_collection(db: Session, collection_id: uuid.UUID, payload: CollectionCreate, user: User) -> CollectionOut:
    collection = get_collection(db, collection_id, user, manage=True)
    duplicate = db.scalar(select(ApiCollection).where(ApiCollection.project_id == collection.project_id, func.lower(ApiCollection.name) == payload.name.lower(), ApiCollection.id != collection.id))
    if duplicate:
        raise ConflictError("A collection with this name already exists in the project.")
    collection.name = payload.name; collection.description = payload.description
    _audit(db, collection.project_id, user, "COLLECTION_UPDATED", "collection", collection.id); db.commit()
    return collection_out(get_collection(db, collection.id, user))


def archive_collection(db: Session, collection_id: uuid.UUID, user: User) -> None:
    collection = get_collection(db, collection_id, user, manage=True)
    collection.is_archived = True
    for request in collection.requests:
        request.is_archived = True
    _audit(db, collection.project_id, user, "COLLECTION_ARCHIVED", "collection", collection.id); db.commit()


def _preserve_masked_items(incoming: list[dict], current: list[dict] | None) -> list[dict]:
    existing = {str(item.get("key", "")).lower(): item.get("value", "") for item in current or []}
    result = []
    for item in incoming:
        copied = dict(item)
        if copied.get("value") == MASK and str(copied.get("key", "")).lower() in existing:
            copied["value"] = existing[str(copied.get("key", "")).lower()]
        result.append(copied)
    return result


def _apply_request_payload(db: Session, request: ApiRequest, payload: RequestCreate, current: ApiRequest | None = None) -> None:
    request.name = payload.name; request.description = payload.description; request.method = payload.method; request.url = payload.url
    headers = _preserve_masked_items([item.model_dump() for item in payload.headers], current.headers if current else None)
    params = _preserve_masked_items([item.model_dump() for item in payload.query_parameters], current.query_parameters if current else None)
    request.headers = protect_key_values(headers); request.query_parameters = protect_key_values(params)
    request.body = payload.body; request.body_type = payload.body_type; request.authentication_type = payload.authentication_type
    auth = dict(payload.authentication_config)
    if current:
        for key, value in list(auth.items()):
            if value == MASK and key in current.authentication_config:
                auth[key] = current.authentication_config[key]
    request.authentication_config = protect_auth(payload.authentication_type.value, auth)
    request.position = payload.position
    request.assertions.clear(); request.extractors.clear(); db.flush()
    request.assertions.extend(ApiAssertion(position=index, **item.model_dump()) for index, item in enumerate(payload.assertions))
    request.extractors.extend(ApiExtractor(position=index, **item.model_dump()) for index, item in enumerate(payload.extractors))


def create_request(db: Session, collection_id: uuid.UUID, payload: RequestCreate, user: User) -> RequestOut:
    collection = get_collection(db, collection_id, user, manage=True)
    request = ApiRequest(project_id=collection.project_id, collection_id=collection.id, created_by=user.id, name=payload.name, url=payload.url, method=payload.method)
    db.add(request); db.flush(); _apply_request_payload(db, request, payload)
    _audit(db, collection.project_id, user, "REQUEST_CREATED", "request", request.id); db.commit()
    return request_out(get_request(db, request.id, user))


def list_requests(db: Session, collection_id: uuid.UUID, user: User) -> list[RequestOut]:
    collection = get_collection(db, collection_id, user)
    return [request_out(item) for item in collection.requests if not item.is_archived]


def update_request(db: Session, request_id: uuid.UUID, payload: RequestCreate, user: User) -> RequestOut:
    request = get_request(db, request_id, user, manage=True)
    _apply_request_payload(db, request, payload, current=request)
    _audit(db, request.project_id, user, "REQUEST_UPDATED", "request", request.id); db.commit()
    return request_out(get_request(db, request.id, user))


def archive_request(db: Session, request_id: uuid.UUID, user: User) -> None:
    request = get_request(db, request_id, user, manage=True); request.is_archived = True
    _audit(db, request.project_id, user, "REQUEST_ARCHIVED", "request", request.id); db.commit()


def _protect_variables(incoming, current: dict | None = None) -> dict:
    current = current or {}
    protected = {}
    for item in incoming:
        existing = current.get(item.name)
        value = item.value
        if item.is_secret:
            if value == MASK and existing:
                value = existing["value"]
            else:
                value = encrypt(value)
        protected[item.name] = {"value": value, "is_secret": item.is_secret}
    return protected


def environment_out(environment: ApiEnvironment) -> EnvironmentOut:
    variables = [{"name": key, "value": MASK if item.get("is_secret") and item.get("value") else item.get("value", ""), "is_secret": bool(item.get("is_secret"))} for key, item in environment.variables.items()]
    return EnvironmentOut.model_validate({"id": environment.id, "project_id": environment.project_id, "name": environment.name, "variables": variables, "classification": environment.classification, "created_by": environment.created_by, "created_at": environment.created_at, "updated_at": environment.updated_at})


def create_environment(db: Session, project_id: uuid.UUID, payload: EnvironmentCreate, user: User) -> EnvironmentOut:
    _require_manage(db, project_id, user)
    if db.scalar(select(ApiEnvironment).where(ApiEnvironment.project_id == project_id, func.lower(ApiEnvironment.name) == payload.name.lower())):
        raise ConflictError("An environment with this name already exists.")
    environment = ApiEnvironment(project_id=project_id, name=payload.name, variables=_protect_variables(payload.variables), classification=payload.classification.value, created_by=user.id)
    db.add(environment); db.flush(); _audit(db, project_id, user, "ENVIRONMENT_CREATED", "environment", environment.id); db.commit(); db.refresh(environment)
    return environment_out(environment)


def list_environments(db: Session, project_id: uuid.UUID, user: User) -> list[EnvironmentOut]:
    _require_project_read(db, project_id, user)
    return [environment_out(item) for item in db.scalars(select(ApiEnvironment).where(ApiEnvironment.project_id == project_id).order_by(ApiEnvironment.name))]


def get_environment(db: Session, environment_id: uuid.UUID, user: User, manage: bool = False) -> ApiEnvironment:
    environment = db.get(ApiEnvironment, environment_id)
    if environment is None:
        raise NotFoundError("API environment not found.")
    (_require_manage if manage else _require_project_read)(db, environment.project_id, user)
    return environment


def update_environment(db: Session, environment_id: uuid.UUID, payload: EnvironmentCreate, user: User) -> EnvironmentOut:
    environment = get_environment(db, environment_id, user, manage=True)
    environment.name = payload.name; environment.variables = _protect_variables(payload.variables, environment.variables); environment.classification = payload.classification.value
    _audit(db, environment.project_id, user, "ENVIRONMENT_UPDATED", "environment", environment.id); db.commit(); db.refresh(environment)
    return environment_out(environment)


def delete_environment(db: Session, environment_id: uuid.UUID, user: User) -> None:
    environment = get_environment(db, environment_id, user, manage=True)
    _audit(db, environment.project_id, user, "ENVIRONMENT_DELETED", "environment", environment.id); db.delete(environment); db.commit()


def _environment_values(environment: ApiEnvironment | None) -> dict[str, str]:
    if environment is None:
        return {}
    return {key: decrypt(item.get("value", "")) if item.get("is_secret") else item.get("value", "") for key, item in environment.variables.items()}


def _allocate_run(db: Session, project_id: uuid.UUID, user: User, collection_id=None, request_id=None, environment_id=None) -> ApiTestRun:
    project = db.scalar(select(Project).where(Project.id == project_id).with_for_update())
    project.next_api_run_number += 1
    run = ApiTestRun(project_id=project_id, run_number=project.next_api_run_number, collection_id=collection_id, request_id=request_id, environment_id=environment_id, created_by=user.id, status=ExecutionStatus.RUNNING)
    db.add(run); db.flush(); _audit(db, project_id, user, "TEST_EXECUTED", "run", run.id); db.commit()
    return run


def _extract(outcome: ExecutionOutcome, extractors: list) -> dict[str, str]:
    extracted = {}
    document = None
    for extractor in extractors:
        if not extractor.enabled:
            continue
        try:
            if extractor.source.value == "JSON_PATH":
                if document is None:
                    document = json.loads(outcome.body)
                value = json_path_get(document, extractor.path)
                if value is MISSING:
                    continue
            else:
                value = {key.lower(): item for key, item in outcome.headers.items()}.get(extractor.path.lower(), MISSING)
                if value is MISSING:
                    continue
            extracted[extractor.variable_name] = str(value)
        except (ValueError, json.JSONDecodeError):
            continue
    return extracted


def _store_result(db: Session, run: ApiTestRun, request: ApiRequest, outcome: ExecutionOutcome, extracted_runtime: dict[str, str]) -> ApiTestResult:
    assertion_results = []
    if outcome.status == ExecutionStatus.PASS:
        snapshot = ResponseSnapshot(outcome.status_code, outcome.response_time_ms, outcome.headers, outcome.body)
        assertion_results = AssertionEngine().evaluate(snapshot, request.assertions)
        if any(not item["passed"] for item in assertion_results):
            outcome.status = ExecutionStatus.FAIL
        extracted_runtime.update(_extract(outcome, request.extractors))
    passed = sum(1 for item in assertion_results if item["passed"])
    result = ApiTestResult(
        test_run_id=run.id, request_id=request.id, request_name=request.name, method=request.method.value,
        resolved_url=outcome.resolved_url, status=outcome.status, status_code=outcome.status_code,
        response_time_ms=outcome.response_time_ms, response_size=outcome.response_size, redirects=outcome.redirects,
        content_type=outcome.content_type, response_headers=mask_response_headers(outcome.headers), response_body=outcome.body,
        response_truncated=outcome.response_truncated, timing=outcome.timing, assertion_results=assertion_results,
        assertions_total=len(assertion_results), assertions_passed=passed, assertions_failed=len(assertion_results) - passed,
        extracted_variable_names=list(extracted_runtime.keys()), error_message=outcome.error_message,
    )
    db.add(result); db.flush(); return result


def _finish_run(db: Session, run: ApiTestRun, started: datetime, results: list[ApiTestResult]) -> None:
    run.requests_total = len(results); run.requests_passed = sum(item.status == ExecutionStatus.PASS for item in results)
    run.requests_failed = len(results) - run.requests_passed
    if any(item.status == ExecutionStatus.TIMEOUT for item in results):
        run.status = ExecutionStatus.TIMEOUT
    elif any(item.status == ExecutionStatus.ERROR for item in results):
        run.status = ExecutionStatus.ERROR
    elif run.requests_failed:
        run.status = ExecutionStatus.FAIL
    else:
        run.status = ExecutionStatus.PASS
    run.completed_at = _now(); run.duration_ms = round((run.completed_at - started).total_seconds() * 1000, 2); db.commit()


async def execute_request(db: Session, request_id: uuid.UUID, payload: ExecuteInput, user: User) -> RunDetail:
    request = get_request(db, request_id, user); _require_execute(db, request.project_id, user)
    environment = get_environment(db, payload.environment_id, user) if payload.environment_id else None
    if environment and environment.project_id != request.project_id:
        raise ValidationAppError("Environment must belong to the request project.")
    started = _now(); run = _allocate_run(db, request.project_id, user, request_id=request.id, environment_id=payload.environment_id)
    outcome = await ApiExecutionService().execute(
        request,
        environment_variables=_environment_values(environment),
        runtime_variables=payload.runtime_variables,
        timeout_seconds=payload.timeout_seconds,
        verify_ssl=payload.verify_ssl,
    )
    result = _store_result(db, run, request, outcome, {}); _finish_run(db, run, started, [result])
    return get_run_detail(db, run.id, user)


async def execute_collection(db: Session, collection_id: uuid.UUID, payload: ExecuteInput, user: User) -> RunDetail:
    collection = get_collection(db, collection_id, user); _require_execute(db, collection.project_id, user)
    environment = get_environment(db, payload.environment_id, user) if payload.environment_id else None
    if environment and environment.project_id != collection.project_id:
        raise ValidationAppError("Environment must belong to the collection project.")
    requests = [item for item in collection.requests if not item.is_archived]
    if payload.request_ids is not None:
        if not payload.request_ids:
            raise ValidationAppError("Select at least one request.")
        selected_ids = set(payload.request_ids)
        available_ids = {item.id for item in requests}
        if selected_ids - available_ids:
            raise ValidationAppError("Every selected request must be active and belong to the collection.")
        requests = [item for item in requests if item.id in selected_ids]
    if not requests:
        raise ValidationAppError("Collection has no active requests.")
    started = _now(); run = _allocate_run(db, collection.project_id, user, collection_id=collection.id, environment_id=payload.environment_id)
    runtime: dict[str, str] = {}; results = []
    for request in requests:
        outcome = await ApiExecutionService().execute(
            request,
            environment_variables=_environment_values(environment),
            extracted_variables=runtime,
            runtime_variables=payload.runtime_variables,
            timeout_seconds=payload.timeout_seconds,
            verify_ssl=payload.verify_ssl,
        )
        results.append(_store_result(db, run, request, outcome, runtime))
    _finish_run(db, run, started, results)
    return get_run_detail(db, run.id, user)


def result_out(result: ApiTestResult) -> ResultOut:
    return ResultOut.model_validate({column: getattr(result, column) for column in ResultOut.model_fields})


def run_list_out(run: ApiTestRun) -> RunListItem:
    return RunListItem.model_validate({
        "id": run.id, "project_id": run.project_id, "run_number": run.run_number, "run_key": run.run_key,
        "collection_id": run.collection_id, "request_id": run.request_id,
        "collection_name": run.collection.name if run.collection else None,
        "request_name": run.request.name if run.request else None, "status": run.status,
        "requests_total": run.requests_total, "requests_passed": run.requests_passed,
        "requests_failed": run.requests_failed, "duration_ms": run.duration_ms,
        "created_by": run.created_by, "created_at": run.created_at, "completed_at": run.completed_at,
    })


def _run_query():
    return select(ApiTestRun).options(joinedload(ApiTestRun.collection), joinedload(ApiTestRun.request), selectinload(ApiTestRun.results))


def get_run(db: Session, run_id: uuid.UUID, user: User) -> ApiTestRun:
    run = db.scalar(_run_query().where(ApiTestRun.id == run_id))
    if run is None:
        raise NotFoundError("API test run not found.")
    _require_project_read(db, run.project_id, user); run.results.sort(key=lambda item: item.executed_at); return run


def get_run_detail(db: Session, run_id: uuid.UUID, user: User) -> RunDetail:
    run = get_run(db, run_id, user)
    data = run_list_out(run).model_dump(); data["results"] = [result_out(item) for item in run.results]
    return RunDetail.model_validate(data)


def list_runs(db: Session, user: User, project_id: uuid.UUID | None, page: int, page_size: int) -> PaginatedRuns:
    conditions = []
    if project_id:
        _require_project_read(db, project_id, user); conditions.append(ApiTestRun.project_id == project_id)
    elif user.role != UserRole.ADMIN:
        allowed = select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
        conditions.append(ApiTestRun.project_id.in_(allowed))
    total = db.scalar(select(func.count(ApiTestRun.id)).where(*conditions)) or 0
    rows = list(db.scalars(_run_query().where(*conditions).order_by(ApiTestRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size)))
    return PaginatedRuns(items=[run_list_out(row) for row in rows], page=page, page_size=page_size, total=total, total_pages=math.ceil(total / page_size))


async def health_check(db: Session, project_id: uuid.UUID, payload: HealthCheckInput, user: User) -> HealthCheckResult:
    _require_execute(db, project_id, user)
    request = SimpleNamespace(name="URL Health Check", method=HttpMethod.GET, url=payload.url, headers=[], query_parameters=[], body=None, body_type=BodyType.NONE, authentication_type=AuthenticationType.NONE, authentication_config={})
    outcome = await ApiExecutionService().execute(request, timeout_seconds=payload.timeout_seconds, verify_ssl=payload.verify_ssl)
    assertions = [SimpleNamespace(assertion_type=AssertionType.STATUS_CODE, operator=AssertionOperator.EQUALS, target=None, expected_value=str(payload.expected_status), enabled=True)]
    if payload.max_response_time_ms:
        assertions.append(SimpleNamespace(assertion_type=AssertionType.RESPONSE_TIME, operator=AssertionOperator.LESS_THAN, target=None, expected_value=str(payload.max_response_time_ms), enabled=True))
    results = []
    if outcome.status == ExecutionStatus.PASS:
        results = AssertionEngine().evaluate(ResponseSnapshot(outcome.status_code, outcome.response_time_ms, outcome.headers, outcome.body), assertions)
        if any(not item["passed"] for item in results): outcome.status = ExecutionStatus.FAIL
    return HealthCheckResult(status=outcome.status, status_code=outcome.status_code, response_time_ms=outcome.response_time_ms, response_size=outcome.response_size, redirects=outcome.redirects, content_type=outcome.content_type, error_message=outcome.error_message, assertions=results)


def analytics(db: Session, project_id: uuid.UUID, user: User) -> ApiAnalytics:
    _require_project_read(db, project_id, user)
    total_requests = db.scalar(select(func.count(ApiRequest.id)).where(ApiRequest.project_id == project_id, ApiRequest.is_archived.is_(False))) or 0
    total_runs = db.scalar(select(func.count(ApiTestRun.id)).where(ApiTestRun.project_id == project_id)) or 0
    passed = db.scalar(select(func.count(ApiTestRun.id)).where(ApiTestRun.project_id == project_id, ApiTestRun.status == ExecutionStatus.PASS)) or 0
    average = db.scalar(select(func.avg(ApiTestResult.response_time_ms)).join(ApiTestRun).where(ApiTestRun.project_id == project_id)) or 0
    slowest = db.execute(select(ApiTestResult.resolved_url, func.avg(ApiTestResult.response_time_ms).label("average")).join(ApiTestRun).where(ApiTestRun.project_id == project_id).group_by(ApiTestResult.resolved_url).order_by(func.avg(ApiTestResult.response_time_ms).desc()).limit(1)).first()
    pass_rate = round((passed / total_runs * 100) if total_runs else 0, 2)
    return ApiAnalytics(total_api_requests=total_requests, total_runs=total_runs, pass_rate=pass_rate, failure_rate=round(100 - pass_rate, 2) if total_runs else 0, average_response_time_ms=round(float(average), 2), slowest_endpoint=slowest[0] if slowest else None)


def get_result(db: Session, result_id: uuid.UUID, user: User) -> ApiTestResult:
    result = db.scalar(select(ApiTestResult).options(joinedload(ApiTestResult.run), joinedload(ApiTestResult.request)).where(ApiTestResult.id == result_id))
    if result is None:
        raise NotFoundError("API test result not found.")
    _require_project_read(db, result.run.project_id, user); return result


def create_bug_from_result(db: Session, result_id: uuid.UUID, payload: BugFromResultCreate, user: User) -> BugDetail:
    result = get_result(db, result_id, user)
    if user.role not in MANAGE_ROLES:
        raise ForbiddenError("Only administrators and QA engineers can create bugs from failures.")
    if result.status == ExecutionStatus.PASS:
        raise ValidationAppError("A passing result cannot be used to create a failure bug.")
    bug = bug_service.create_bug(db, result.run.project_id, payload, user)
    bug.discovered_from_test_result_id = result.id
    db.add(BugHistory(bug_id=bug.id, user_id=user.id, action="SOURCE_LINKED", field_name="discovered_from_test_result_id", old_value=None, new_value=str(result.id), created_at=_now()))
    db.commit()
    return BugDetail.model_validate(bug_service.get_bug(db, bug.id, user))


def bug_suggestion(db: Session, result_id: uuid.UUID, user: User) -> dict:
    result = get_result(db, result_id, user)
    failed = [item["description"] for item in result.assertion_results if not item.get("passed")]
    description = "\n".join([
        "Automated API test failure.", "", f"Run: {result.run.run_key}",
        f"Request: {result.request_name}", f"Endpoint: {result.method} {result.resolved_url}",
        f"Actual Status: {result.status_code if result.status_code is not None else result.status.value}",
        f"Response Time: {result.response_time_ms:.2f} ms", "",
        "Failed Assertions:", *(f"- {item}" for item in failed or [result.error_message or result.status.value]),
    ])
    return {
        "title": f"API test failed — {result.request_name}", "description": description,
        "steps_to_reproduce": [f"Run {result.run.run_key}", f"Execute {result.method} {result.resolved_url}"],
        "expected_result": "All configured API assertions should pass.",
        "actual_result": f"{result.assertions_failed} assertion(s) failed; execution status {result.status.value}.",
        "severity": BugSeverity.MEDIUM, "priority": BugPriority.HIGH,
        "environment": result.run.environment.name if result.run.environment else "API Test",
    }
