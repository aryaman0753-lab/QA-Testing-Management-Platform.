import asyncio
import json
import socket
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.api_testing.engine import ExecutionOutcome
from app.api_testing.secrets import MASK
from app.automation.assertions import evaluate_assertions
from app.automation.engine import ApiAutomationEngine
from app.automation.security import request_url_validator, validate_automation_target
from app.automation.variables import AutomationVariables
from app.common.exceptions import ValidationAppError
from app.core.config import get_settings
from app.database.models.api_testing import ExecutionStatus


def response(code=200, body='{"data":{"id":123,"token":"super-secret-token"}}', headers=None, error=None, status=ExecutionStatus.PASS):
    return ExecutionOutcome(status=status, request_name="Request", method="GET", resolved_url="https://qa.example.com/users", status_code=code, response_time_ms=15, body=body, headers=headers or {}, error_message=error)


class FakeExecutor:
    def __init__(self, responses=None):
        self.responses = list(responses or [response()])
        self.requests = []

    async def execute(self, request, **kwargs):
        self.requests.append(request)
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]


def step(kind, config, **kwargs):
    return {"id": str(uuid.uuid4()), "name": kind, "step_type": kind, "config": config, "enabled": True, **kwargs}


def snapshot(steps, **kwargs):
    steps = [{**entry, "order_index": index} for index, entry in enumerate(steps)]
    return {"name": "Workflow", "allowed_hosts": ["qa.example.com"], "max_retries": 0,
            "environment_variables": {"base_url": "https://qa.example.com"},
            "cases": [{"id": str(uuid.uuid4()), "name": "Lifecycle", "enabled": True, "timeout": 60, "steps": steps}], **kwargs}


def request_step(method="GET", **kwargs):
    return step("HTTP_REQUEST", {"request": {"name": "Get user", "method": method, "url": "${base_url}/users", **kwargs}})


def test_chaining_extraction_header_prefix_assertions_conditions_and_secret_masking():
    executor = FakeExecutor([response(headers={"Authorization": "Bearer header-token"}), response(body='{"id":123}')])
    data = snapshot([
        request_step(),
        step("EXTRACT_VARIABLE", {"source": "JSON_PATH", "path": "$.data.id", "variable_name": "user_id"}),
        step("EXTRACT_VARIABLE", {"source": "HEADER", "path": "Authorization", "variable_name": "token", "strip_prefix": "Bearer ", "is_secret": True}),
        step("HTTP_REQUEST", {"request": {"name": "Read created user", "url": "{{base_url}}/users/${user_id}", "authentication_type": "BEARER", "authentication_config": {"token": "${token}"}}}),
        step("ASSERTION", {"assertions": [{"source": "STATUS_CODE", "operator": "EQUALS", "expected": "200"}, {"source": "JSON_PATH", "target": "$.id", "operator": "EQUALS", "expected": "123"}]}),
        step("CONDITION", {"source": "STATUS_CODE", "operator": "EQUALS", "expected": "404"}),
        step("SET_VARIABLE", {"variable_name": "ignored", "value": "wrong"}),
        step("SET_VARIABLE", {"variable_name": "finished", "value": "yes"}),
    ])
    outcome = asyncio.run(ApiAutomationEngine(executor).run(data))
    assert outcome.status == "PASSED" and outcome.passed_steps == 7 and outcome.skipped_steps == 1
    assert executor.requests[1].url == "https://qa.example.com/users/123"
    assert executor.requests[1].authentication_config["token"] == "header-token"
    persisted = json.dumps(outcome.results, default=str)
    assert "header-token" not in persisted and "super-secret-token" not in persisted
    assert outcome.results[1]["extracted_variables"] == {"user_id": MASK}


def test_variable_precedence_and_missing_variables():
    variables = AutomationVariables({"value": "environment"}, {"value": "runtime"})
    variables.assign("value", "extracted")
    assert variables.resolve("${value}/{{value}}") == "runtime/runtime"
    with pytest.raises(ValidationAppError):
        variables.resolve("${missing}")


def test_short_extracted_values_are_redacted_from_urls_and_nested_assertion_actuals():
    variables = AutomationVariables()
    variables.assign("user_id", "123")
    assert variables.sanitize_url("https://qa.example.com/users/123?token=abc") == "https://qa.example.com/users/********"
    variables.discover_response_secrets('{"data":{"token":"abc","name":"visible"}}', {})
    result = evaluate_assertions(
        [{"source": "JSON_PATH", "target": "$.data", "operator": "EXISTS"}],
        response(body='{"data":{"token":"abc","name":"visible"}}'),
        variables,
    )[0]
    assert "abc" not in result["actual"]
    assert "visible" in result["actual"]


@pytest.mark.parametrize("source,target,operator,expected", [
    ("STATUS_CODE", None, "NOT_EQUALS", "500"), ("STATUS_CODE", None, "GREATER_THAN", "199"),
    ("STATUS_CODE", None, "LESS_THAN", "300"), ("BODY", None, "CONTAINS", "123"),
    ("BODY", None, "NOT_CONTAINS", "missing"), ("JSON_PATH", "$.data.id", "EXISTS", None),
    ("JSON_PATH", "$.data.id", "CONTAINS", "12"), ("HEADER", "content-type", "EXISTS", None),
    ("HEADER", "content-type", "CONTAINS", "json"), ("RESPONSE_TIME", None, "LESS_THAN", "1000"),
])
def test_reusable_assertions(source, target, operator, expected):
    result = evaluate_assertions([{"source": source, "target": target, "operator": operator, "expected": expected}], response(headers={"Content-Type": "application/json"}), AutomationVariables())
    assert result[0]["passed"] and result[0]["failure_message"] is None


def test_retry_attempts_transient_failures_and_no_retry_for_mutations_or_configuration():
    executor = FakeExecutor([response(code=503), response()])
    outcome = asyncio.run(ApiAutomationEngine(executor).run(snapshot([request_step()], max_retries=2)))
    assert outcome.status == "PASSED" and outcome.passed_steps == 1 and outcome.failed_steps == 0
    assert [(entry["attempt"], entry["status"], entry["is_final"]) for entry in outcome.results] == [(1, "FAILED", False), (2, "PASSED", True)]
    for method, code in (("POST", 503), ("GET", 401), ("GET", 403)):
        executor = FakeExecutor([response(code=code), response()])
        outcome = asyncio.run(ApiAutomationEngine(executor).run(snapshot([request_step(method)], max_retries=2)))
        assert outcome.status == "FAILED" and len(executor.requests) == 1
    executor = FakeExecutor()
    outcome = asyncio.run(ApiAutomationEngine(executor).run(snapshot([request_step(url="${missing}/x")], max_retries=2)))
    assert len(outcome.results) == 1 and not executor.requests and outcome.results[0]["error_kind"] == "CONFIGURATION"


def test_failure_skips_remaining_case_steps_but_runs_next_case():
    executor = FakeExecutor([response(code=500), response()])
    data = snapshot([request_step(), step("SET_VARIABLE", {"variable_name": "skipped", "value": "yes"})])
    data["cases"].extend(snapshot([request_step()])["cases"])
    result = asyncio.run(ApiAutomationEngine(executor).run(data))
    assert result.status == "FAILED" and result.failed_cases == 1 and result.passed_cases == 1 and result.skipped_steps == 1


def test_stop_cancels_inflight_request_and_delay_and_case_deadline():
    class SlowExecutor:
        cancelled = False
        async def execute(self, request, **kwargs):
            try:
                await asyncio.sleep(30)
            finally:
                self.cancelled = True
    async def run_cancelled():
        flag = False
        async def stop():
            nonlocal flag
            await asyncio.sleep(0.02)
            flag = True
        stopper = asyncio.create_task(stop())
        executor = SlowExecutor()
        outcome = await ApiAutomationEngine(executor).run(snapshot([request_step()]), is_cancelled=lambda: flag)
        await stopper
        assert outcome.status == "CANCELLED" and executor.cancelled
    asyncio.run(run_cancelled())
    data = snapshot([step("DELAY", {"seconds": 1})])
    data["cases"][0]["timeout"] = 0.01
    outcome = asyncio.run(ApiAutomationEngine().run(data))
    assert outcome.status == "FAILED" and outcome.results[0]["error_kind"] == "TIMEOUT"


def test_public_ipv4_ssrf_metadata_private_policy_and_redirects(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "AUTOMATION_ALLOWED_HOSTS", "")
    def dns(address):
        monkeypatch.setattr(socket, "getaddrinfo", lambda *args: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))])
    dns("93.184.216.34")
    assert asyncio.run(validate_automation_target("https://qa.example.com", ["qa.example.com"])).ip == "93.184.216.34"
    with pytest.raises(ValidationAppError):
        asyncio.run(validate_automation_target("https://evil.example.com", ["qa.example.com"]))
    monkeypatch.setattr(settings, "AUTOMATION_ALLOW_PRIVATE_NETWORKS", True)
    for address in ("127.0.0.1", "169.254.169.254", "0.0.0.0"):
        dns(address)
        with pytest.raises(ValidationAppError):
            asyncio.run(validate_automation_target("https://qa.example.com", ["qa.example.com"]))
    dns("10.0.0.5")
    assert asyncio.run(validate_automation_target("https://qa.example.com")).ip == "10.0.0.5"
    monkeypatch.setattr(settings, "AUTOMATION_ALLOW_PRIVATE_NETWORKS", False)
    with pytest.raises(ValidationAppError):
        asyncio.run(validate_automation_target("https://qa.example.com"))
    dns("93.184.216.34")
    validator = request_url_validator(["*.example.com"])
    asyncio.run(validator("https://qa.example.com"))
    with pytest.raises(ValidationAppError, match="Cross-origin"):
        asyncio.run(validator("https://other.example.com"))


def provision_workflow(client, monkeypatch, auto_bugs=False):
    from app.automation import queue, service
    from app.automation.schemas import CaseCreate, StartRunInput, StepCreate, SuiteCreate
    from app.database.models.user import User
    from tests.conftest import TestingSessionLocal, auth_headers, register_user
    qa = register_user(client, f"workflow-{uuid.uuid4()}@example.com")
    project = client.post("/api/v1/projects", json={"name": "Automation", "key": "AUTO"}, headers=auth_headers(qa["access_token"])).json()
    monkeypatch.setattr(queue, "enqueue_run", lambda run_id: None)
    with TestingSessionLocal() as db:
        user = db.scalar(select(User).where(User.email == qa["user"]["email"]))
        suite = service.create_suite(db, uuid.UUID(project["id"]), SuiteCreate(name="Lifecycle", status="ACTIVE", allowed_hosts=["qa.example.com"], auto_create_bugs=auto_bugs), user)
        case = service.create_case(db, suite.id, CaseCreate(name="Read user"), user)
        service.create_step(db, case.id, StepCreate(name="Get user", step_type="HTTP_REQUEST", config={"request": {"name": "Get", "url": "https://qa.example.com/users"}}), user)
        run = service.create_run(db, suite.id, StartRunInput(), user)
        return run.id, suite.id, user.id


def test_worker_persists_final_results_and_deduplicates_automatic_bugs(client, monkeypatch):
    from app.automation import service
    from app.automation.schemas import StartRunInput
    from app.database.models.automation import AutomationRun, AutomationStepResult
    from app.database.models.bug import Bug
    from app.database.models.user import User
    from tests.conftest import TestingSessionLocal
    from workers.automation.runner import process_run
    run_id, suite_id, user_id = provision_workflow(client, monkeypatch, auto_bugs=True)
    process_run(run_id, TestingSessionLocal, ApiAutomationEngine(FakeExecutor([response(code=500)])))
    with TestingSessionLocal() as db:
        run = db.get(AutomationRun, run_id)
        assert run.status == "FAILED" and run.failed_steps == 1 and run.failed_cases == 1
        assert db.scalar(select(func.count(AutomationStepResult.id)).where(AutomationStepResult.run_id == run_id)) == 1
        bug = db.scalar(select(Bug))
        assert bug is not None and bug.discovered_from_automation_run_id == run_id
        assert bug.discovered_from_automation_step_result_id is not None
        next_run = service.create_run(db, suite_id, StartRunInput(), db.get(User, user_id))
        next_id = next_run.id
    process_run(next_id, TestingSessionLocal, ApiAutomationEngine(FakeExecutor([response(code=500)])))
    # Re-delivery of a queue ID must not execute an already completed run.
    untouched = FakeExecutor()
    process_run(next_id, TestingSessionLocal, ApiAutomationEngine(untouched))
    assert not untouched.requests
    with TestingSessionLocal() as db:
        assert db.scalar(select(func.count(Bug.id))) == 1


def test_worker_revalidates_permission_before_sending_request(client, monkeypatch):
    from app.database.models.automation import AutomationRun
    from app.database.models.user import User
    from tests.conftest import TestingSessionLocal
    from workers.automation.runner import process_run
    run_id, _, user_id = provision_workflow(client, monkeypatch)
    with TestingSessionLocal() as db:
        db.get(User, user_id).is_active = False
        db.commit()
    executor = FakeExecutor()
    process_run(run_id, TestingSessionLocal, ApiAutomationEngine(executor))
    assert not executor.requests
    with TestingSessionLocal() as db:
        assert db.get(AutomationRun, run_id).status == "FAILED"
