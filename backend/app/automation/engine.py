"""Sequential API workflow engine. HTTP and persistence remain replaceable adapters."""
import asyncio
import inspect
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import monotonic
from types import SimpleNamespace

from pydantic import ValidationError

from app.api_testing.assertions import AssertionEngine, ResponseSnapshot
from app.api_testing.engine import ApiExecutionService
from app.api_testing.jsonpath import MISSING, json_path_get
from app.api_testing.schemas import RequestCreate
from app.api_testing.secrets import MASK, is_sensitive_name
from app.automation.assertions import evaluate_assertions, evaluate_condition
from app.automation.security import request_url_validator
from app.automation.variables import AutomationVariables
from app.common.exceptions import ValidationAppError
from app.core.config import get_settings


def now():
    return datetime.now(timezone.utc)


class ExecutionCancelled(Exception):
    pass


class ExecutionDeadline(Exception):
    pass


@dataclass
class AutomationOutcome:
    status: str = "PASSED"
    duration_ms: float = 0
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    skipped_cases: int = 0
    total_steps: int = 0
    passed_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0
    error_message: str | None = None
    results: list[dict] = field(default_factory=list)


class AutomationEngine(ABC):
    @abstractmethod
    async def run(self, snapshot: dict, on_result=None, is_cancelled=None) -> AutomationOutcome:
        """Execute a frozen suite and publish sanitized attempts as they finish."""


class ApiAutomationEngine(AutomationEngine):
    def __init__(self, executor=None):
        self.executor = executor

    async def _bounded(self, awaitable, deadline, cancelled):
        task = asyncio.create_task(awaitable)
        try:
            while not task.done():
                if cancelled and cancelled():
                    raise ExecutionCancelled
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise ExecutionDeadline
                await asyncio.wait({task}, timeout=min(0.2, remaining))
            return await task
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def run(self, snapshot: dict, on_result=None, is_cancelled=None) -> AutomationOutcome:
        settings = get_settings()
        started = monotonic()
        deadline = started + settings.AUTOMATION_MAX_RUN_SECONDS
        variables = AutomationVariables(snapshot.get("environment_variables"), snapshot.get("runtime_variables"), snapshot.get("secret_variable_names"))
        outcome = AutomationOutcome()
        retry_limit = min(int(snapshot.get("max_retries", 0)), settings.AUTOMATION_MAX_RETRIES)
        cases = sorted(snapshot.get("cases", []), key=lambda row: row.get("order_index", 0))
        outcome.total_cases = len(cases)
        outcome.total_steps = sum(len(case.get("steps", [])) for case in cases)
        if outcome.total_cases > settings.AUTOMATION_MAX_CASES or outcome.total_steps > settings.AUTOMATION_MAX_STEPS:
            outcome.status, outcome.error_message = "FAILED", "Suite exceeds the configured execution size limit."
            return outcome

        async def publish(result):
            result = variables.sanitize(result)
            outcome.results.append(result)
            if on_result:
                called = on_result(result)
                if inspect.isawaitable(called):
                    await called
            return result

        cancelled_run = False
        expired_run = False
        for case in cases:
            case_deadline = min(deadline, monotonic() + float(case.get("timeout", 60)))
            case_failed = False
            case_executed = False
            response = None
            guard = True
            steps = sorted(case.get("steps", []), key=lambda row: row.get("order_index", 0))
            for step in steps:
                base = {
                    "case_id": case.get("id"), "step_id": step.get("id"), "case_name": case.get("name", "Test case"),
                    "step_name": step.get("name", "Step"), "step_type": step.get("step_type", ""),
                    "order_index": step.get("order_index", 0), "attempt": 1, "is_final": True,
                    "request_method": None, "resolved_url": None, "status_code": None, "response_time_ms": 0,
                    "assertions": [], "extracted_variables": {}, "error_message": None, "error_kind": None,
                    "started_at": now(), "completed_at": now(),
                }
                if is_cancelled and is_cancelled():
                    cancelled_run = True
                expired_run = expired_run or monotonic() >= deadline
                skip = case_failed or cancelled_run or expired_run or not case.get("enabled", True) or not step.get("enabled", True)
                if not skip:
                    try:
                        skip = not guard or bool(step.get("condition") and not evaluate_condition(step["condition"], response, variables))
                    except (ValidationAppError, ValueError, TypeError):
                        await publish({**base, "status": "FAILED", "error_kind": "CONFIGURATION", "error_message": "The step condition is invalid or requires a response."})
                        outcome.failed_steps += 1
                        case_failed, case_executed = True, True
                        guard = True
                        continue
                guard = True
                if skip:
                    await publish({**base, "status": "SKIPPED"})
                    outcome.skipped_steps += 1
                    continue
                case_executed = True
                for attempt in range(1, retry_limit + 2):
                    result = {**base, "attempt": attempt, "started_at": now(), "assertions": [], "extracted_variables": {}}
                    can_retry = False
                    try:
                        if monotonic() >= case_deadline:
                            raise ExecutionDeadline
                        config = variables.resolve(step.get("config", {}))
                        kind = step.get("step_type")
                        if kind == "HTTP_REQUEST":
                            definition = RequestCreate.model_validate(config.get("request", {}))
                            request = SimpleNamespace(**definition.model_dump())
                            auth = request.authentication_config
                            auth_kind = request.authentication_type.value
                            if (auth_kind == "BEARER" and not auth.get("token")) or (auth_kind == "BASIC" and (not auth.get("username") or not auth.get("password"))) or (auth_kind == "API_KEY" and not auth.get("value")):
                                raise ValidationAppError("Authentication configuration is incomplete.")
                            for key, value in auth.items():
                                if key in {"token", "password", "value", "client_secret"}:
                                    variables.remember_secret(value)
                            for header in request.headers:
                                if is_sensitive_name(header["key"]):
                                    variables.remember_secret(header["value"])
                            variables.discover_response_secrets(request.body or "", {})
                            executor = self.executor or ApiExecutionService(url_validator=request_url_validator(snapshot.get("allowed_hosts", [])))
                            response = await self._bounded(executor.execute(request, timeout_seconds=min(settings.API_MAX_TIMEOUT_SECONDS, max(0.01, case_deadline - monotonic()))), case_deadline, is_cancelled)
                            variables.discover_response_secrets(response.body, response.headers)
                            result.update(request_method=request.method.value, resolved_url=variables.sanitize_url(response.resolved_url), status_code=response.status_code, response_time_ms=response.response_time_ms)
                            status = getattr(response.status, "value", response.status)
                            if response.error_message:
                                message = response.error_message.lower()
                                transient = status == "TIMEOUT" or "unable to connect" in message or "could not be completed" in message
                                result.update(status="FAILED", error_kind="TIMEOUT" if status == "TIMEOUT" else "NETWORK" if transient else "CONFIGURATION", error_message="The HTTP request timed out." if status == "TIMEOUT" else "The HTTP request could not be completed." if transient else "The request failed configuration or destination validation.")
                                can_retry = transient
                            elif response.status_code is None or response.status_code >= 400:
                                result.update(status="FAILED", error_kind="HTTP", error_message=f"HTTP request returned status {response.status_code}.")
                                can_retry = response.status_code is not None and response.status_code >= 500
                            else:
                                legacy = AssertionEngine().evaluate(ResponseSnapshot(response.status_code, response.response_time_ms, response.headers, response.body), definition.assertions)
                                for assertion, entry in zip([a for a in definition.assertions if a.enabled], legacy):
                                    if is_sensitive_name(assertion.target or "") or assertion.assertion_type.value.startswith("BODY"):
                                        entry["expected"], entry["actual"] = MASK, MASK
                                result["assertions"] = variables.sanitize(legacy)
                                result["status"] = "PASSED" if all(item["passed"] for item in legacy) else "FAILED"
                                if result["status"] == "FAILED":
                                    result.update(error_kind="ASSERTION", error_message="One or more request assertions failed.")
                                    can_retry = True
                                if result["status"] == "PASSED":
                                    for extractor in definition.extractors:
                                        if extractor.enabled:
                                            self._extract({"source": extractor.source.value, "path": extractor.path, "variable_name": extractor.variable_name}, response, variables)
                                            result["extracted_variables"][extractor.variable_name] = MASK
                            # Replaying mutations requires a fresh manual run; retries are read-only.
                            can_retry = can_retry and request.method.value in {"GET", "HEAD", "OPTIONS"}
                        elif kind == "ASSERTION":
                            result["assertions"] = evaluate_assertions(config.get("assertions", []), response, variables)
                            if not result["assertions"]:
                                raise ValidationAppError("At least one assertion is required.")
                            result["status"] = "PASSED" if all(item["passed"] for item in result["assertions"]) else "FAILED"
                            if result["status"] == "FAILED":
                                result.update(error_kind="ASSERTION", error_message="One or more assertions failed.")
                        elif kind == "EXTRACT_VARIABLE":
                            self._extract(config, response, variables)
                            result.update(status="PASSED", extracted_variables={config["variable_name"]: MASK})
                        elif kind == "SET_VARIABLE":
                            variables.assign(config["variable_name"], config.get("value", ""), config.get("is_secret", False))
                            result.update(status="PASSED", extracted_variables={config["variable_name"]: MASK})
                        elif kind == "DELAY":
                            seconds = float(config.get("seconds", 0))
                            if not 0 <= seconds <= settings.AUTOMATION_MAX_DELAY_SECONDS:
                                raise ValidationAppError("Delay exceeds the configured limit.")
                            await self._bounded(asyncio.sleep(seconds), case_deadline, is_cancelled)
                            result["status"] = "PASSED"
                        elif kind == "CONDITION":
                            guard = evaluate_condition(config, response, variables)
                            result["status"] = "PASSED"
                        else:
                            raise ValidationAppError("Unsupported automation step type.")
                    except ExecutionCancelled:
                        cancelled_run = True
                        result.update(status="CANCELLED", error_kind="CANCELLED", error_message="Execution was cancelled.")
                    except ExecutionDeadline:
                        expired_run = monotonic() >= deadline
                        result.update(status="FAILED", error_kind="TIMEOUT", error_message="The execution time limit was exceeded.")
                    except (ValidationAppError, ValidationError, ValueError, TypeError, KeyError):
                        result.update(status="FAILED", error_kind="CONFIGURATION", error_message="Step configuration is invalid or references a missing variable or response value.")
                    result["completed_at"] = now()
                    result["is_final"] = not (result["status"] == "FAILED" and can_retry and attempt <= retry_limit)
                    await publish(result)
                    if result["is_final"]:
                        if result["status"] == "PASSED":
                            outcome.passed_steps += 1
                        elif result["status"] == "FAILED":
                            outcome.failed_steps += 1
                            case_failed = True
                        else:
                            outcome.skipped_steps += 1
                        break
            if case_failed:
                outcome.failed_cases += 1
            elif case_executed and not cancelled_run:
                outcome.passed_cases += 1
            else:
                outcome.skipped_cases += 1
        outcome.status = "CANCELLED" if cancelled_run else "FAILED" if outcome.failed_steps or expired_run else "PASSED"
        if expired_run:
            outcome.error_message = "The suite execution time limit was exceeded."
        outcome.duration_ms = round((monotonic() - started) * 1000, 2)
        return outcome

    @staticmethod
    def _extract(config, response, variables):
        if response is None:
            raise ValidationAppError("Extraction requires a preceding response.")
        if config.get("source") in {"HEADER", "RESPONSE_HEADER"}:
            value = {key.lower(): item for key, item in response.headers.items()}.get(config["path"].lower(), MISSING)
        elif config.get("source") in {"JSON_PATH", "JSON_BODY"}:
            value = json_path_get(json.loads(response.body), config["path"])
        else:
            raise ValidationAppError("Unsupported extraction source.")
        if value is MISSING:
            raise ValidationAppError("The extraction path does not exist.")
        prefix = config.get("strip_prefix")
        if prefix and isinstance(value, str) and value.startswith(prefix):
            value = value[len(prefix):]
        variables.assign(config["variable_name"], value, config.get("is_secret", False))
