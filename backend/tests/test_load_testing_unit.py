import asyncio
import subprocess
import sys
import textwrap
from types import SimpleNamespace

import pytest

from app.api_testing.outbound_security import PinnedUrl
from app.common.exceptions import ValidationAppError
from app.load_testing import security
from app.load_testing.thresholds import Summary, evaluate_thresholds
from app.load_testing.state import transition_run
from app.database.models.load_testing import LoadTestStatus


def test_threshold_evaluation_pass_and_multiple_failures():
    summary = Summary(total_requests=1000, failed_requests=30, requests_per_second=80, failure_rate=3, avg_response_time=400, p95_response_time=1200, p99_response_time=1600)
    results = evaluate_thresholds(summary, {"max_p95_ms": 1000, "max_p99_ms": 2000, "max_failure_rate": 2, "max_average_ms": 500, "min_rps": 100, "max_error_count": 50})
    by_key = {row["key"]: row for row in results}
    assert not by_key["max_p95_ms"]["passed"] and by_key["max_p99_ms"]["passed"]
    assert not by_key["max_failure_rate"]["passed"] and not by_key["min_rps"]["passed"]
    assert by_key["max_average_ms"]["passed"] and by_key["max_error_count"]["passed"]


def test_run_state_machine_accepts_valid_and_rejects_terminal_transitions():
    run = SimpleNamespace(status=LoadTestStatus.QUEUED)
    transition_run(run, LoadTestStatus.STARTING)
    transition_run(run, LoadTestStatus.RUNNING)
    transition_run(run, LoadTestStatus.COMPLETED)
    with pytest.raises(ValueError, match="COMPLETED -> RUNNING"):
        transition_run(run, LoadTestStatus.RUNNING)


def test_load_target_requires_allowlist_and_uses_dedicated_private_policy(monkeypatch):
    seen = {}
    async def fake_validate(url, allow_private=None):
        seen.update(url=url, allow_private=allow_private)
        return PinnedUrl(url, url, "qa.example.com", "qa.example.com", "93.184.216.34", 1)
    monkeypatch.setattr(security, "validate_and_pin_url", fake_validate)
    with pytest.raises(ValidationAppError, match="allowlist"):
        asyncio.run(security.validate_load_target("https://evil.example.net", ["qa.example.com"], True))
    asyncio.run(security.validate_load_target("https://api.qa.example.com/users", ["qa.example.com"], True))
    assert seen == {"url": "https://api.qa.example.com/users", "allow_private": False}


def test_metadata_and_localhost_are_rejected_even_when_named_in_allowlist():
    with pytest.raises(ValidationAppError, match="private"):
        asyncio.run(security.validate_load_target("http://169.254.169.254/latest/meta-data", ["169.254.169.254"], True))
    with pytest.raises(ValidationAppError, match="Local"):
        asyncio.run(security.validate_load_target("http://localhost/test", ["localhost"], True))


def test_locust_engine_runs_in_isolated_abstraction_and_collects_metrics():
    # Locust applies gevent monkey patches at import time. Run the real smoke test
    # in its own process so it cannot alter FastAPI/AnyIO's test runtime.
    script = textwrap.dedent("""
        from workers.load_testing.locust_engine import EngineConfig, LocustLoadTestEngine
        from gevent.pywsgi import WSGIServer

        def app(environ, start_response):
            body = b'{"ok":true}'
            start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
            return [body]

        server = WSGIServer(("127.0.0.1", 0), app, log=None)
        server.start()
        try:
            config = EngineConfig(url=f"http://127.0.0.1:{server.server_port}/health", method="GET", headers={}, params=[], request_kwargs={}, users=1, spawn_rate=1, duration_seconds=1, timeout_seconds=2, target_rps=2)
            samples = []
            result = LocustLoadTestEngine().start(config, lambda: False, samples.append)
            assert not result.cancelled and result.summary.total_requests >= 1 and result.summary.failed_requests == 0
            assert result.status_distribution.get("2xx", 0) >= 1 and samples
            print("LOCUST_SMOKE_OK")
        finally:
            server.stop()
    """)
    completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=20, check=False)
    assert completed.returncode == 0, completed.stderr
    assert "LOCUST_SMOKE_OK" in completed.stdout
