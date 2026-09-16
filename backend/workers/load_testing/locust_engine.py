from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from time import monotonic
from typing import Callable
from urllib.parse import urlsplit

import gevent
from locust import HttpUser, constant_throughput, task
from locust.env import Environment
from locust.runners import STATE_STOPPED
from requests.adapters import HTTPAdapter

from app.core.config import get_settings


@dataclass
class EngineConfig:
    url: str
    method: str
    headers: dict[str, str]
    params: list[tuple[str, str]]
    request_kwargs: dict
    users: int
    spawn_rate: float
    duration_seconds: int
    timeout_seconds: float
    target_rps: float | None = None
    tls_hostname: str | None = None


@dataclass
class MetricSnapshot:
    active_users: int = 0
    requests_per_second: float = 0
    failure_rate: float = 0
    avg_response_time: float = 0
    p50: float = 0
    p90: float = 0
    p95: float = 0
    p99: float = 0
    total_requests: int = 0
    failed_requests: int = 0


@dataclass
class EndpointSnapshot:
    method: str
    path: str
    request_count: int
    failure_count: int
    rps: float
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p50: float
    p90: float
    p95: float
    p99: float


@dataclass
class ErrorSnapshot:
    method: str
    path: str
    error_type: str
    status_code: int | None
    message: str
    count: int


@dataclass
class EngineResult:
    cancelled: bool
    summary: MetricSnapshot
    min_response_time: float
    max_response_time: float
    p75: float
    endpoints: list[EndpointSnapshot] = field(default_factory=list)
    errors: list[ErrorSnapshot] = field(default_factory=list)
    status_distribution: dict[str, int] = field(default_factory=dict)


class LoadTestEngine(ABC):
    @abstractmethod
    def start(self, config: EngineConfig, should_stop: Callable[[], bool], on_metric: Callable[[MetricSnapshot], None]) -> EngineResult: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def status(self) -> str: ...

    @abstractmethod
    def metrics(self) -> MetricSnapshot: ...


class PinnedTLSAdapter(HTTPAdapter):
    """Connect to a validated IP while checking the certificate for the logical host."""

    def __init__(self, tls_hostname: str, *args, **kwargs):
        self.tls_hostname = tls_hostname
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        pool_kwargs.update(assert_hostname=self.tls_hostname, server_hostname=self.tls_hostname)
        return super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)


def _percentile(stats, value: float) -> float:
    return round(float(stats.get_response_time_percentile(value) or 0), 2)


def _snapshot(runner) -> MetricSnapshot:
    stats = runner.stats.total
    total = stats.num_requests or 0; failed = stats.num_failures or 0
    return MetricSnapshot(
        active_users=runner.user_count, requests_per_second=round(float(stats.current_rps or 0), 2),
        failure_rate=round((failed / total * 100) if total else 0, 2), avg_response_time=round(float(stats.avg_response_time or 0), 2),
        p50=_percentile(stats, .50), p90=_percentile(stats, .90), p95=_percentile(stats, .95), p99=_percentile(stats, .99),
        total_requests=total, failed_requests=failed,
    )


class LocustLoadTestEngine(LoadTestEngine):
    def __init__(self):
        self.runner = None

    def start(self, config: EngineConfig, should_stop: Callable[[], bool], on_metric: Callable[[MetricSnapshot], None]) -> EngineResult:
        parsed = urlsplit(config.url); host = f"{parsed.scheme}://{parsed.netloc}"; path = parsed.path or "/"
        query = parsed.query; request_path = f"{path}?{query}" if query else path
        max_size = get_settings().LOAD_TEST_MAX_RESPONSE_SIZE_BYTES
        per_user_rate = config.target_rps / config.users if config.target_rps else None

        def on_start(user):
            user.client.trust_env = False
            if parsed.scheme == "https" and config.tls_hostname:
                user.client.mount("https://", PinnedTLSAdapter(config.tls_hostname))

        def execute(user):
            kwargs = dict(config.request_kwargs)
            if "content" in kwargs: kwargs["data"] = kwargs.pop("content")
            with user.client.request(config.method, request_path, headers=config.headers, params=config.params, timeout=config.timeout_seconds,
                                     allow_redirects=False, stream=True, name=f"{config.method} {path}", catch_response=True, **kwargs) as response:
                size = 0
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    size += len(chunk)
                    if size > max_size:
                        response.failure("Response exceeded configured size limit")
                        break
                if response.is_redirect or response.is_permanent_redirect:
                    response.failure("Redirect responses are not followed by load tests")
                response.close()

        attrs = {"host": host, "on_start": on_start, "perform_request": task(execute)}
        if per_user_rate: attrs["wait_time"] = constant_throughput(per_user_rate)
        DynamicUser = type("QAHubLoadUser", (HttpUser,), attrs)
        environment = Environment(user_classes=[DynamicUser]); self.runner = environment.create_local_runner()
        status_counts: dict[str, int] = {}; captured_errors: dict[tuple, ErrorSnapshot] = {}

        @environment.events.request.add_listener
        def record(request_type=None, name=None, response=None, exception=None, **kwargs):
            status = getattr(response, "status_code", None)
            bucket = f"{status // 100}xx" if status else "network"
            status_counts[bucket] = status_counts.get(bucket, 0) + 1
            if exception or (status and status >= 400):
                if exception:
                    raw = type(exception).__name__; category = "Timeout" if "Timeout" in raw else "Connection Error"
                else: category = f"HTTP {status // 100}xx"
                message = category if status else "Network request failed"
                key = (request_type or config.method, name or path, category, status, message)
                if key not in captured_errors: captured_errors[key] = ErrorSnapshot(key[0], key[1], key[2], key[3], key[4], 0)
                captured_errors[key].count += 1

        self.runner.start(user_count=config.users, spawn_rate=config.spawn_rate)
        started = monotonic(); last_metric = 0.0; cancelled = False
        interval = max(.5, get_settings().LOAD_TEST_METRICS_INTERVAL_SECONDS)
        while monotonic() - started < config.duration_seconds:
            if should_stop(): cancelled = True; break
            if monotonic() - last_metric >= interval:
                on_metric(_snapshot(self.runner)); last_metric = monotonic()
            gevent.sleep(min(.25, interval))
        self.runner.quit(); on_metric(_snapshot(self.runner))
        total = self.runner.stats.total
        endpoints = [EndpointSnapshot(method=entry.method, path=entry.name, request_count=entry.num_requests, failure_count=entry.num_failures,
            rps=round(float(entry.current_rps or 0), 2), avg_response_time=round(float(entry.avg_response_time or 0), 2),
            min_response_time=round(float(entry.min_response_time or 0), 2), max_response_time=round(float(entry.max_response_time or 0), 2),
            p50=_percentile(entry, .50), p90=_percentile(entry, .90), p95=_percentile(entry, .95), p99=_percentile(entry, .99))
            for entry in self.runner.stats.entries.values()]
        return EngineResult(cancelled=cancelled, summary=_snapshot(self.runner), min_response_time=round(float(total.min_response_time or 0), 2),
            max_response_time=round(float(total.max_response_time or 0), 2), p75=_percentile(total, .75), endpoints=endpoints,
            errors=list(captured_errors.values()), status_distribution=status_counts)

    def stop(self) -> None:
        if self.runner: self.runner.quit()

    def status(self) -> str:
        return self.runner.state if self.runner else STATE_STOPPED

    def metrics(self) -> MetricSnapshot:
        return _snapshot(self.runner) if self.runner else MetricSnapshot()
