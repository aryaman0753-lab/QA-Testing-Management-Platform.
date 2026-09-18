import contextvars
import hashlib
import re
import threading
import time
import uuid
from collections import Counter
from functools import lru_cache

import redis
from fastapi import Request

from app.core.config import get_settings

request_id_context = contextvars.ContextVar("request_id", default="-")
_metrics = Counter()
_metric_lock = threading.Lock()
_fallback_limits: dict[tuple[str, str, int], int] = {}


@lru_cache
def _rate_redis():
    settings = get_settings()
    return redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=0.2, socket_timeout=0.2)


def request_id() -> str:
    return request_id_context.get()


def record_request(method: str, path: str, status: int, duration: float) -> None:
    route = path.split("?")[0]
    route = re.sub(r"/[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,36}(?=/|$)", "/{id}", route)
    route = re.sub(r"/\d+(?=/|$)", "/{number}", route)
    with _metric_lock:
        _metrics[("requests", method, route, str(status))] += 1
        _metrics[("duration_ms", method, route)] += duration * 1000


def prometheus_metrics() -> str:
    lines = ["# HELP qahub_http_requests_total Total HTTP requests.", "# TYPE qahub_http_requests_total counter", "# HELP qahub_http_request_duration_ms_sum Cumulative HTTP request duration in milliseconds.", "# TYPE qahub_http_request_duration_ms_sum counter"]
    with _metric_lock:
        for key, value in sorted(_metrics.items(), key=lambda row: str(row[0])):
            if key[0] == "requests":
                _, method, route, status = key
                safe_route = route.replace('"', '')
                lines.append(f'qahub_http_requests_total{{method="{method}",route="{safe_route}",status="{status}"}} {value}')
            elif key[0] == "duration_ms":
                _, method, route = key
                safe_route = route.replace('"', '')
                lines.append(f'qahub_http_request_duration_ms_sum{{method="{method}",route="{safe_route}"}} {value:.3f}')
        lines.extend(["# HELP qahub_process_up QAHub API process availability.", "# TYPE qahub_process_up gauge", "qahub_process_up 1"])
    return "\n".join(lines) + "\n"


def limit_for_path(path: str):
    settings = get_settings()
    if path.endswith("/auth/login") or "/password/reset" in path: return "auth", settings.RATE_LIMIT_LOGIN_PER_MINUTE
    if path.endswith("/ci/test-runs"): return "ci", settings.RATE_LIMIT_CI_PER_MINUTE
    if path.endswith("/run") and ("/automation/" in path or "/load-tests/" in path): return "execution", settings.RATE_LIMIT_EXECUTION_PER_MINUTE
    if "/integrations/webhooks" in path: return "webhook", settings.RATE_LIMIT_WEBHOOK_CONFIG_PER_MINUTE
    return None


def allow_request(request: Request, category: str, limit: int) -> tuple[bool, int]:
    settings = get_settings(); window = int(time.time() // 60)
    address = request.client.host if request.client else "unknown"
    identity = hashlib.sha256(f"{address}:{category}".encode()).hexdigest()[:24]
    key = f"qahub:rate:{category}:{identity}:{window}"
    try:
        client = _rate_redis()
        count = int(client.incr(key))
        if count == 1: client.expire(key, 70)
        return count <= limit, max(0, limit - count)
    except (redis.RedisError, OSError):
        # Development stays usable without Redis. Production keeps a per-process safety net.
        if settings.ENVIRONMENT.lower() not in {"production", "prod"}: return True, limit
        if len(_fallback_limits) > 10_000:
            for stale in [item for item in _fallback_limits if item[2] < window - 1]:
                _fallback_limits.pop(stale, None)
        fallback_key = (category, identity, window)
        _fallback_limits[fallback_key] = _fallback_limits.get(fallback_key, 0) + 1
        return _fallback_limits[fallback_key] <= limit, max(0, limit - _fallback_limits[fallback_key])


def new_request_id(value: str | None) -> str:
    if value and len(value) <= 128 and all(char.isalnum() or char in "-_." for char in value): return value
    return str(uuid.uuid4())
