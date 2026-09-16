import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app.api_testing.assertions import AssertionEngine, ResponseSnapshot
from app.api_testing.engine import ApiExecutionService
from app.api_testing.outbound_security import PinnedUrl, validate_and_pin_url
from app.api_testing.variables import VariableResolver
from app.common.exceptions import ValidationAppError
from app.database.models.api_testing import AssertionOperator, AssertionType, AuthenticationType, BodyType, HttpMethod


def assertion(kind, operator, expected=None, target=None):
    return SimpleNamespace(assertion_type=kind, operator=operator, expected_value=expected, target=target, enabled=True)


def request(**overrides):
    values = dict(name="Request", method=HttpMethod.GET, url="https://example.test/users", headers=[], query_parameters=[], body=None, body_type=BodyType.NONE, authentication_type=AuthenticationType.NONE, authentication_config={})
    values.update(overrides)
    return SimpleNamespace(**values)


def test_variable_resolution_precedence_and_missing():
    resolver = VariableResolver({"host": "env", "same": "environment"}, {"token": "extracted", "same": "extracted"}, {"same": "runtime"})
    assert resolver.resolve("{{host}}/{{token}}/{{ same }}") == "env/extracted/runtime"
    with pytest.raises(ValidationAppError, match="missing"):
        resolver.resolve("{{missing}}")
    assert resolver.redact_sensitive_values("https://example.test/extracted") == "https://example.test/********"


def test_assertion_engine_supported_assertions():
    response = ResponseSnapshot(200, 120.5, {"content-type": "application/json", "x-id": "42"}, '{"user":{"email":"qa@example.com","roles":["qa"]}}')
    assertions = [
        assertion(AssertionType.STATUS_CODE, AssertionOperator.EQUALS, "200"),
        assertion(AssertionType.RESPONSE_TIME, AssertionOperator.LESS_THAN, "1000"),
        assertion(AssertionType.BODY_CONTAINS, AssertionOperator.CONTAINS, "qa@example.com"),
        assertion(AssertionType.JSON_PATH, AssertionOperator.EXISTS, target="$.user.email"),
        assertion(AssertionType.HEADER_EXISTS, AssertionOperator.EXISTS, target="Content-Type"),
        assertion(AssertionType.HEADER_EQUALS, AssertionOperator.EQUALS, "42", "X-ID"),
        assertion(AssertionType.JSON_VALUE_EQUALS, AssertionOperator.EQUALS, "qa@example.com", "$.user.email"),
        assertion(AssertionType.JSON_VALUE_CONTAINS, AssertionOperator.CONTAINS, "qa", "$.user.roles[0]"),
    ]
    results = AssertionEngine().evaluate(response, assertions)
    assert len(results) == 8 and all(item["passed"] for item in results)


def test_ssrf_rejects_loopback_and_embedded_credentials():
    with pytest.raises(ValidationAppError, match="private"):
        asyncio.run(validate_and_pin_url("http://127.0.0.1/admin"))
    with pytest.raises(ValidationAppError, match="credentials"):
        asyncio.run(validate_and_pin_url("https://user:pass@example.com"))


def test_execution_builds_methods_params_headers_json_and_auth():
    captured = {}

    def handler(incoming: httpx.Request):
        captured.update(method=incoming.method, url=str(incoming.url), headers=dict(incoming.headers), body=incoming.content)
        return httpx.Response(201, json={"ok": True}, headers={"X-Result": "yes"})

    transport = httpx.MockTransport(handler)
    factory = lambda **kwargs: httpx.AsyncClient(transport=transport, timeout=kwargs["timeout"], follow_redirects=False)

    async def validator(url):
        return PinnedUrl(url, url, "api.example.test", "api.example.test", "93.184.216.34", 1.2)

    definition = request(
        method=HttpMethod.POST, url="https://api.example.test/{{resource}}",
        headers=[{"key": "Accept", "value": "application/json", "enabled": True}],
        query_parameters=[{"key": "page", "value": "{{page}}", "enabled": True}],
        body='{"name":"{{name}}"}', body_type=BodyType.JSON,
        authentication_type=AuthenticationType.BEARER, authentication_config={"token": "{{token}}"},
    )
    outcome = asyncio.run(ApiExecutionService(factory, validator).execute(definition, {"resource": "users"}, runtime_variables={"page": "2", "name": "Aryaman", "token": "secret"}))
    assert outcome.status_code == 201 and outcome.body == '{"ok":true}'
    assert captured["method"] == "POST" and "page=2" in captured["url"]
    assert captured["headers"]["authorization"] == "Bearer secret"
    assert b"Aryaman" in captured["body"]


@pytest.mark.parametrize("method", [HttpMethod.GET, HttpMethod.PUT, HttpMethod.PATCH, HttpMethod.DELETE, HttpMethod.HEAD, HttpMethod.OPTIONS])
def test_execution_supports_http_methods(method):
    transport = httpx.MockTransport(lambda incoming: httpx.Response(204))
    factory = lambda **kwargs: httpx.AsyncClient(transport=transport)
    async def validator(url): return PinnedUrl(url, url, "example.test", "example.test", "93.184.216.34", 0)
    outcome = asyncio.run(ApiExecutionService(factory, validator).execute(request(method=method)))
    assert outcome.status_code == 204


def test_execution_form_basic_auth_timeout_and_response_limit(monkeypatch):
    seen = {}
    def form_handler(incoming):
        seen.update(headers=dict(incoming.headers), body=incoming.content)
        return httpx.Response(200, text="ok")
    async def validator(url): return PinnedUrl(url, url, "example.test", "example.test", "93.184.216.34", 0)
    factory = lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(form_handler))
    form_request = request(method=HttpMethod.POST, body='{"user":"qa"}', body_type=BodyType.FORM_URLENCODED, authentication_type=AuthenticationType.BASIC, authentication_config={"username": "u", "password": "p"})
    assert asyncio.run(ApiExecutionService(factory, validator).execute(form_request)).status_code == 200
    assert seen["headers"]["authorization"].startswith("Basic ") and b"user=qa" in seen["body"]

    timeout_factory = lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(lambda incoming: (_ for _ in ()).throw(httpx.ReadTimeout("timeout", request=incoming))))
    assert asyncio.run(ApiExecutionService(timeout_factory, validator).execute(request())).status.value == "TIMEOUT"

    from app.api_testing import engine
    monkeypatch.setattr(engine.get_settings(), "API_MAX_RESPONSE_SIZE_MB", 0)
    large_factory = lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(lambda incoming: httpx.Response(200, content=b"x")))
    outcome = asyncio.run(ApiExecutionService(large_factory, validator).execute(request()))
    assert outcome.status.value == "ERROR" and "maximum size" in outcome.error_message


def test_redirect_destination_is_revalidated():
    transport = httpx.MockTransport(lambda incoming: httpx.Response(302, headers={"Location": "http://127.0.0.1/secret"}))
    factory = lambda **kwargs: httpx.AsyncClient(transport=transport)
    async def validator(url):
        if "127.0.0.1" in url: raise ValidationAppError("Private redirect blocked.")
        return PinnedUrl(url, url, "public.example", "public.example", "93.184.216.34", 0)
    outcome = asyncio.run(ApiExecutionService(factory, validator).execute(request(url="https://public.example")))
    assert outcome.status.value == "ERROR" and "blocked" in outcome.error_message
