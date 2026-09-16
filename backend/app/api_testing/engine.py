import base64
import json
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any
from urllib.parse import urljoin

import httpx

from app.api_testing.outbound_security import validate_and_pin_url, verify_connected_peer
from app.api_testing.secrets import reveal_auth, reveal_key_values
from app.api_testing.variables import VariableResolver
from app.common.exceptions import ValidationAppError
from app.core.config import get_settings
from app.database.models.api_testing import AuthenticationType, BodyType, ExecutionStatus, HttpMethod


class ResponseTooLargeError(Exception):
    pass


@dataclass
class ExecutionOutcome:
    status: ExecutionStatus
    request_name: str
    method: str
    resolved_url: str
    status_code: int | None = None
    response_time_ms: float = 0
    response_size: int = 0
    redirects: int = 0
    content_type: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    response_truncated: bool = False
    timing: dict[str, float] = field(default_factory=dict)
    error_message: str | None = None


class ApiExecutionService:
    """Reusable single-user functional HTTP executor; no load concurrency."""

    def __init__(self, client_factory=None, url_validator=None):
        self.client_factory = client_factory or httpx.AsyncClient
        self.url_validator = url_validator or validate_and_pin_url

    async def execute(
        self,
        request,
        environment_variables: dict[str, str] | None = None,
        extracted_variables: dict[str, str] | None = None,
        runtime_variables: dict[str, str] | None = None,
        timeout_seconds: float | None = None,
        verify_ssl: bool = True,
    ) -> ExecutionOutcome:
        settings = get_settings()
        timeout = timeout_seconds or settings.API_REQUEST_TIMEOUT_SECONDS
        if timeout > settings.API_MAX_TIMEOUT_SECONDS:
            return self._error(request, f"Timeout cannot exceed {settings.API_MAX_TIMEOUT_SECONDS:g} seconds.")
        if not verify_ssl and not settings.API_ALLOW_INSECURE_SSL:
            return self._error(request, "Disabling TLS verification is not permitted by server policy.")

        resolver = VariableResolver(environment_variables, extracted_variables, runtime_variables)
        try:
            logical_url = resolver.resolve(request.url)
            headers = self._build_headers(request, resolver)
            query = resolver.resolve_items(reveal_key_values(request.query_parameters))
            body_kwargs = self._build_body(request, resolver)
            auth_query = self._apply_auth(request, resolver, headers)
            query.extend(auth_query)
        except (ValidationAppError, ValueError, json.JSONDecodeError) as exc:
            return self._error(request, str(exc))

        started = perf_counter()
        redirects = 0
        dns_total = 0.0
        first_byte_ms = 0.0
        method = request.method.value
        current_url = logical_url
        current_query = query
        current_body = body_kwargs
        try:
            async with self.client_factory(
                verify=verify_ssl,
                follow_redirects=False,
                trust_env=False,
                timeout=httpx.Timeout(timeout),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            ) as client:
                while True:
                    pinned = await self.url_validator(current_url)
                    dns_total += pinned.dns_lookup_ms
                    outbound_headers = {key: value for key, value in headers.items() if key.lower() != "host"}
                    outbound_headers["Host"] = pinned.host_header
                    async with client.stream(
                        method,
                        pinned.network_url,
                        headers=outbound_headers,
                        params=current_query,
                        extensions={"sni_hostname": pinned.sni_hostname},
                        **current_body,
                    ) as response:
                        verify_connected_peer(response, pinned.ip)
                        first_byte_ms = (perf_counter() - started) * 1000
                        if response.status_code in {301, 302, 303, 307, 308} and response.headers.get("location"):
                            if redirects >= settings.API_MAX_REDIRECTS:
                                return self._error(request, "Maximum redirect count exceeded.", started, redirects)
                            current_url = urljoin(pinned.logical_url, response.headers["location"])
                            redirects += 1
                            current_query = []
                            if response.status_code == 303 or (response.status_code in {301, 302} and method == "POST"):
                                method, current_body = "GET", {}
                            continue

                        chunks: list[bytes] = []
                        size = 0
                        maximum = settings.API_MAX_RESPONSE_SIZE_MB * 1024 * 1024
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > maximum:
                                raise ResponseTooLargeError
                            chunks.append(chunk)
                        raw = b"".join(chunks)
                        retained = raw[: settings.API_RESPONSE_BODY_RETENTION_BYTES]
                        encoding = response.encoding or "utf-8"
                        text = retained.decode(encoding, errors="replace")
                        elapsed = (perf_counter() - started) * 1000
                        return ExecutionOutcome(
                            status=ExecutionStatus.PASS,
                            request_name=request.name,
                            method=request.method.value,
                            resolved_url=resolver.redact_sensitive_values(pinned.logical_url).split("?", 1)[0],
                            status_code=response.status_code,
                            response_time_ms=round(elapsed, 2),
                            response_size=size,
                            redirects=redirects,
                            content_type=response.headers.get("content-type"),
                            headers=dict(response.headers),
                            body=text,
                            response_truncated=len(raw) > len(retained),
                            timing={"dns_lookup_ms": round(dns_total, 2), "time_to_first_byte_ms": round(first_byte_ms, 2), "total_ms": round(elapsed, 2)},
                        )
        except httpx.TimeoutException:
            return self._error(request, f"Request timed out after {timeout:g} seconds.", started, redirects, ExecutionStatus.TIMEOUT)
        except ResponseTooLargeError:
            return self._error(request, f"Response exceeds the configured {settings.API_MAX_RESPONSE_SIZE_MB} MB maximum size.", started, redirects)
        except (httpx.ConnectError, httpx.NetworkError):
            return self._error(request, "Unable to connect to the validated destination.", started, redirects)
        except (ValidationAppError, httpx.InvalidURL) as exc:
            return self._error(request, str(exc), started, redirects)
        except httpx.HTTPError:
            return self._error(request, "The HTTP request could not be completed.", started, redirects)

    @staticmethod
    def _build_headers(request, resolver: VariableResolver) -> dict[str, str]:
        pairs = resolver.resolve_items(reveal_key_values(request.headers))
        return {key: value for key, value in pairs}

    @staticmethod
    def _build_body(request, resolver: VariableResolver) -> dict[str, Any]:
        if request.body_type == BodyType.NONE or request.method in {HttpMethod.GET, HttpMethod.HEAD, HttpMethod.OPTIONS}:
            return {}
        body = resolver.resolve(request.body or "")
        if request.body_type == BodyType.JSON:
            try:
                return {"json": json.loads(body)}
            except json.JSONDecodeError as exc:
                raise ValidationAppError(f"Request body is not valid JSON: {exc.msg}.") from exc
        if request.body_type == BodyType.FORM_URLENCODED:
            try:
                value = json.loads(body)
            except json.JSONDecodeError as exc:
                raise ValidationAppError("Form URL encoded body must be a JSON object of key/value pairs.") from exc
            if not isinstance(value, dict):
                raise ValidationAppError("Form URL encoded body must be a JSON object.")
            return {"data": {str(key): str(item) for key, item in value.items()}}
        if request.body_type == BodyType.MULTIPART_FORM_DATA:
            try:
                value = json.loads(body)
            except json.JSONDecodeError as exc:
                raise ValidationAppError("Multipart body must be a JSON object of text fields.") from exc
            if not isinstance(value, dict):
                raise ValidationAppError("Multipart body must be a JSON object.")
            return {"files": {str(key): (None, str(item)) for key, item in value.items()}}
        return {"content": body.encode("utf-8")}

    @staticmethod
    def _apply_auth(request, resolver: VariableResolver, headers: dict[str, str]) -> list[tuple[str, str]]:
        config = {key: resolver.resolve(value) for key, value in reveal_auth(request.authentication_config).items()}
        if request.authentication_type == AuthenticationType.BEARER:
            headers["Authorization"] = f"Bearer {config.get('token', '')}"
        elif request.authentication_type == AuthenticationType.BASIC:
            encoded = base64.b64encode(f"{config.get('username', '')}:{config.get('password', '')}".encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        elif request.authentication_type == AuthenticationType.API_KEY:
            key, value = config.get("key", "X-API-Key"), config.get("value", "")
            if config.get("location", "header") == "query":
                return [(key, value)]
            headers[key] = value
        return []

    @staticmethod
    def _error(request, message: str, started: float | None = None, redirects: int = 0, status: ExecutionStatus = ExecutionStatus.ERROR) -> ExecutionOutcome:
        elapsed = (perf_counter() - started) * 1000 if started else 0
        return ExecutionOutcome(
            status=status,
            request_name=request.name,
            method=request.method.value,
            resolved_url=request.url.split("?", 1)[0],
            response_time_ms=round(elapsed, 2),
            redirects=redirects,
            error_message=message,
            timing={"total_ms": round(elapsed, 2)},
        )
