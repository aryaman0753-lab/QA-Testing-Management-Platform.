"""Small, typed predicate language shared by assertions and conditions."""
import json
from typing import Any

from app.api_testing.jsonpath import MISSING, json_path_get
from app.api_testing.secrets import MASK, is_sensitive_name
from app.common.exceptions import ValidationAppError


def actual_value(spec: dict, response, variables: dict) -> Any:
    source = spec.get("source")
    target = spec.get("target", "") or ""
    if source == "VARIABLE":
        return variables.get(target, MISSING)
    if response is None:
        raise ValidationAppError("This step requires a preceding HTTP response.")
    if source == "STATUS_CODE":
        return response.status_code
    if source == "RESPONSE_TIME":
        return response.response_time_ms
    if source == "BODY":
        return response.body
    if source == "HEADER":
        return {key.lower(): value for key, value in response.headers.items()}.get(target.lower(), MISSING)
    if source == "JSON_PATH":
        try:
            return json_path_get(json.loads(response.body), target)
        except (ValueError, TypeError):
            return MISSING
    raise ValidationAppError("Unknown assertion source.")


def compare(actual, expected, operator: str, numeric=False) -> bool:
    if operator == "EXISTS":
        return actual is not MISSING and actual is not None
    if actual is MISSING:
        return False
    if operator in {"GREATER_THAN", "LESS_THAN"} or numeric:
        try:
            left, right = float(actual), float(expected)
        except (ValueError, TypeError):
            return False
    else:
        left = json.dumps(actual, sort_keys=True) if isinstance(actual, (dict, list)) else str(actual)
        right = str(expected)
    if operator == "EQUALS":
        return left == right
    if operator == "NOT_EQUALS":
        return left != right
    if operator == "GREATER_THAN":
        return left > right
    if operator == "LESS_THAN":
        return left < right
    if operator == "CONTAINS":
        return str(right) in str(left)
    if operator == "NOT_CONTAINS":
        return str(right) not in str(left)
    raise ValidationAppError("Unknown assertion operator.")


def evaluate_condition(spec: dict, response, variables) -> bool:
    resolved = variables.resolve(spec)
    return compare(actual_value(resolved, response, variables.values), resolved.get("expected"), resolved.get("operator", "EQUALS"), resolved.get("source") in {"STATUS_CODE", "RESPONSE_TIME"})


def evaluate_assertions(specs: list[dict], response, variables) -> list[dict]:
    results = []
    for raw in specs:
        spec = variables.resolve(raw)
        actual = actual_value(spec, response, variables.values)
        passed = compare(actual, spec.get("expected"), spec.get("operator", "EQUALS"), spec.get("source") in {"STATUS_CODE", "RESPONSE_TIME"})
        sensitive = is_sensitive_name(spec.get("target") or "") or spec.get("source") == "BODY"
        safe_actual = variables.sanitize(actual)
        if isinstance(safe_actual, (dict, list)):
            safe_actual = json.dumps(safe_actual, sort_keys=True)
        elif safe_actual is not MISSING:
            safe_actual = str(safe_actual)
        results.append(variables.sanitize({
            "source": spec.get("source"), "operator": spec.get("operator"), "target": spec.get("target"),
            "expected": MASK if sensitive else spec.get("expected"),
            "actual": MASK if sensitive else None if actual is MISSING else safe_actual,
            "passed": passed, "failure_message": None if passed else "Assertion did not match the expected value.",
        }))
    return results
