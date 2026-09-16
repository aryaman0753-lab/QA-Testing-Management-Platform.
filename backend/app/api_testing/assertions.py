import json
from dataclasses import dataclass
from typing import Any

from app.api_testing.jsonpath import MISSING, json_path_get
from app.api_testing.secrets import MASK, is_sensitive_name
from app.database.models.api_testing import AssertionOperator, AssertionType


@dataclass
class ResponseSnapshot:
    status_code: int | None
    response_time_ms: float
    headers: dict[str, str]
    body: str

    def json(self) -> Any:
        return json.loads(self.body)


class AssertionEngine:
    def evaluate(self, response: ResponseSnapshot, assertions: list) -> list[dict]:
        return [self._evaluate_one(response, assertion) for assertion in assertions if assertion.enabled]

    def _evaluate_one(self, response: ResponseSnapshot, assertion) -> dict:
        kind = assertion.assertion_type
        operator = assertion.operator
        target = assertion.target or ""
        expected = assertion.expected_value
        actual: Any = None
        try:
            if kind == AssertionType.STATUS_CODE:
                actual = response.status_code
                passed = self._compare(actual, expected, operator, numeric=True)
            elif kind == AssertionType.RESPONSE_TIME:
                actual = round(response.response_time_ms, 2)
                passed = self._compare(actual, expected, operator, numeric=True)
            elif kind == AssertionType.BODY_CONTAINS:
                actual = "response body"
                passed = (expected or "") in response.body
                if operator == AssertionOperator.NOT_CONTAINS:
                    passed = not passed
            elif kind in {AssertionType.JSON_PATH, AssertionType.JSON_VALUE_EQUALS, AssertionType.JSON_VALUE_CONTAINS}:
                actual = json_path_get(response.json(), target)
                if kind == AssertionType.JSON_PATH:
                    passed = actual is not MISSING
                    if operator == AssertionOperator.NOT_EXISTS:
                        passed = not passed
                elif actual is MISSING:
                    passed = False
                elif kind == AssertionType.JSON_VALUE_CONTAINS:
                    passed = (expected or "") in str(actual)
                else:
                    passed = self._compare(actual, expected, operator)
            elif kind in {AssertionType.HEADER_EXISTS, AssertionType.HEADER_EQUALS}:
                headers = {key.lower(): value for key, value in response.headers.items()}
                actual = headers.get(target.lower(), MISSING)
                if kind == AssertionType.HEADER_EXISTS:
                    passed = actual is not MISSING
                    if operator == AssertionOperator.NOT_EXISTS:
                        passed = not passed
                else:
                    passed = actual is not MISSING and self._compare(actual, expected, operator)
            else:
                raise ValueError("Unsupported assertion type.")
            display_actual = MASK if is_sensitive_name(target) and actual is not MISSING else (None if actual is MISSING else str(actual))
            description = f"{kind.value.replace('_', ' ').title()} {operator.value.replace('_', ' ').lower()}"
            return {"assertion_type": kind.value, "passed": bool(passed), "description": description, "expected": expected, "actual": display_actual}
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return {"assertion_type": kind.value, "passed": False, "description": f"Assertion error: {exc}", "expected": expected, "actual": None}

    @staticmethod
    def _compare(actual: Any, expected: str | None, operator: AssertionOperator, numeric: bool = False) -> bool:
        if numeric:
            left, right = float(actual), float(expected or "")
        else:
            left, right = str(actual).lower(), str(expected).lower()
        if operator == AssertionOperator.EQUALS:
            return left == right
        if operator == AssertionOperator.NOT_EQUALS:
            return left != right
        if operator == AssertionOperator.LESS_THAN:
            return left < right
        if operator == AssertionOperator.GREATER_THAN:
            return left > right
        if operator == AssertionOperator.CONTAINS:
            return str(right) in str(left)
        if operator == AssertionOperator.NOT_CONTAINS:
            return str(right) not in str(left)
        raise ValueError("Operator is not valid for this assertion.")
