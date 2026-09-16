from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api_testing.outbound_security import PinnedUrl
from app.database.models.load_testing import LoadTestResultStatus, LoadTestRun, LoadTestStatus
from tests.conftest import TestingSessionLocal, auth_headers, make_admin, register_user


class FakeQueue:
    def __init__(self): self.enqueued = []; self.stopped = []
    def enqueue(self, run_id): self.enqueued.append(run_id)
    def request_stop(self, run_id): self.stopped.append(run_id)


def create_project(client, token, key="LOAD"):
    response = client.post("/api/v1/projects", json={"name": "Load Project", "key": key}, headers=auth_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


def create_environment(client, project_id, token, classification="QA"):
    response = client.post(f"/api/v1/projects/{project_id}/api/environments", json={"name": classification, "classification": classification, "variables": [{"name": "base_url", "value": "https://qa.example.com"}]}, headers=auth_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


def payload(environment_id, **overrides):
    data = {"name": "ECOM Baseline", "environment_id": environment_id, "target_url": "https://qa.example.com/users", "request_method": "GET",
        "headers": [{"key": "Authorization", "value": "secret-token", "enabled": True}], "query_parameters": [{"key": "page", "value": "1", "enabled": True}],
        "body_type": "NONE", "authentication_type": "BEARER", "authentication_config": {"token": "secret-token"},
        "profile": "BASELINE", "virtual_users": 10, "spawn_rate": 2, "duration_seconds": 30, "timeout_seconds": 10,
        "thresholds": {"max_p95_ms": 1000, "max_failure_rate": 2, "min_rps": 10}}
    data.update(overrides); return data


def test_definition_crud_limits_secrets_permissions_and_request_reuse(client: TestClient):
    qa = register_user(client, "load-owner@example.com"); project = create_project(client, qa["access_token"]); environment = create_environment(client, project["id"], qa["access_token"])
    created = client.post(f"/api/v1/projects/{project['id']}/load-tests", json=payload(environment["id"]), headers=auth_headers(qa["access_token"]))
    assert created.status_code == 201, created.text
    assert created.json()["headers"][0]["value"] == "********" and created.json()["authentication_config"]["token"] == "********"
    assert client.get(f"/api/v1/projects/{project['id']}/load-tests", headers=auth_headers(qa["access_token"])).json()[0]["name"] == "ECOM Baseline"
    too_many = client.post(f"/api/v1/projects/{project['id']}/load-tests", json=payload(environment["id"], name="Unsafe", virtual_users=101), headers=auth_headers(qa["access_token"]))
    assert too_many.status_code == 422 and "cannot exceed" in too_many.text
    outsider = register_user(client, "load-outsider@example.com")
    assert client.get(f"/api/v1/load-tests/{created.json()['id']}", headers=auth_headers(outsider["access_token"])).status_code == 404
    update = payload(environment["id"], name="ECOM Baseline Updated"); update["headers"][0]["value"] = "********"; update["authentication_config"]["token"] = "********"
    assert client.patch(f"/api/v1/load-tests/{created.json()['id']}", json=update, headers=auth_headers(qa["access_token"])).status_code == 200
    assert client.delete(f"/api/v1/load-tests/{created.json()['id']}", headers=auth_headers(qa["access_token"])).status_code == 204


def test_queue_start_concurrency_stop_history_reports_threshold_bug_and_baseline(client: TestClient, monkeypatch):
    from app.load_testing import service
    queue = FakeQueue(); monkeypatch.setattr(service, "get_load_queue", lambda: queue)
    async def valid(url, hosts, enabled): return PinnedUrl(url, url, "qa.example.com", "qa.example.com", "93.184.216.34", 1)
    monkeypatch.setattr(service, "validate_load_target", valid)
    qa = register_user(client, "load-run@example.com"); project = create_project(client, qa["access_token"], "LRUN"); environment = create_environment(client, project["id"], qa["access_token"])
    client.put(f"/api/v1/projects/{project['id']}/load-tests/settings", json={"enabled": True, "allowed_hosts": ["qa.example.com"]}, headers=auth_headers(qa["access_token"]))
    definition = client.post(f"/api/v1/projects/{project['id']}/load-tests", json=payload(environment["id"]), headers=auth_headers(qa["access_token"])).json()
    started = client.post(f"/api/v1/load-tests/{definition['id']}/run", json={}, headers=auth_headers(qa["access_token"]))
    assert started.status_code == 202 and started.json()["status"] == "QUEUED" and len(queue.enqueued) == 1
    second = client.post(f"/api/v1/load-tests/{definition['id']}/run", json={}, headers=auth_headers(qa["access_token"]))
    assert second.status_code == 409
    stopped = client.post(f"/api/v1/load-tests/runs/{started.json()['id']}/stop", headers=auth_headers(qa["access_token"]))
    assert stopped.status_code == 200 and stopped.json()["status"] == "STOPPING" and queue.stopped
    db = TestingSessionLocal()
    try:
        run = db.get(LoadTestRun, started.json()["id"]); run.status = LoadTestStatus.COMPLETED; run.result_status = LoadTestResultStatus.THRESHOLD_EXCEEDED
        run.total_requests = 1000; run.successful_requests = 970; run.failed_requests = 30; run.requests_per_second = 80; run.failure_rate = 3
        run.avg_response_time = 400; run.p50_response_time = 180; run.p90_response_time = 700; run.p95_response_time = 1200; run.p99_response_time = 1600
        run.started_at = datetime.now(timezone.utc); run.completed_at = datetime.now(timezone.utc)
        run.threshold_results = [{"key": "max_p95_ms", "label": "P95 response time", "measured": 1200, "operator": "<=", "threshold": 1000, "unit": "ms", "passed": False}]
        db.commit()
    finally: db.close()
    detail = client.get(f"/api/v1/load-tests/runs/{started.json()['id']}", headers=auth_headers(qa["access_token"]))
    history = client.get(f"/api/v1/projects/{project['id']}/load-tests/runs", headers=auth_headers(qa["access_token"]))
    assert detail.status_code == 200 and detail.json()["p95_response_time"] == 1200 and history.json()["total"] == 1
    assert client.get(f"/api/v1/load-tests/runs/{started.json()['id']}/report.csv", headers=auth_headers(qa["access_token"])).status_code == 200
    assert client.get(f"/api/v1/load-tests/runs/{started.json()['id']}/report.json", headers=auth_headers(qa["access_token"])).status_code == 200
    assert client.post(f"/api/v1/load-tests/runs/{started.json()['id']}/baseline", headers=auth_headers(qa["access_token"])).json()["is_baseline"]
    suggestion = client.get(f"/api/v1/load-tests/runs/{started.json()['id']}/bug-suggestion", headers=auth_headers(qa["access_token"]))
    bug = client.post(f"/api/v1/load-tests/runs/{started.json()['id']}/bugs", json=suggestion.json(), headers=auth_headers(qa["access_token"]))
    assert bug.status_code == 201 and bug.json()["discovered_from_load_test_run_id"] == started.json()["id"]
    candidate = client.post(f"/api/v1/load-tests/{definition['id']}/run", json={}, headers=auth_headers(qa["access_token"]))
    assert candidate.status_code == 202
    db = TestingSessionLocal()
    try:
        run = db.get(LoadTestRun, candidate.json()["id"]); run.status = LoadTestStatus.COMPLETED; run.result_status = LoadTestResultStatus.PASS
        run.total_requests = 1200; run.successful_requests = 1200; run.requests_per_second = 100; run.avg_response_time = 350
        run.p95_response_time = 900; run.p99_response_time = 1400; run.completed_at = datetime.now(timezone.utc)
        db.commit()
    finally: db.close()
    comparison = client.get(f"/api/v1/projects/{project['id']}/load-tests/runs/compare", params={"run_a": started.json()["id"], "run_b": candidate.json()["id"]}, headers=auth_headers(qa["access_token"]))
    assert comparison.status_code == 200
    assert comparison.json()["metrics"][0] == {"metric": "avg_response_time", "run_a": 400.0, "run_b": 350.0, "difference": -50.0, "percent_change": -12.5}


def test_production_requires_admin_server_enablement_and_confirmation(client: TestClient, monkeypatch):
    from app.load_testing import service
    queue = FakeQueue(); monkeypatch.setattr(service, "get_load_queue", lambda: queue)
    async def valid(url, hosts, enabled): return PinnedUrl(url, url, "prod.example.com", "prod.example.com", "93.184.216.34", 1)
    monkeypatch.setattr(service, "validate_load_target", valid)
    admin = register_user(client, "load-admin@example.com"); make_admin("load-admin@example.com")
    project = create_project(client, admin["access_token"], "PROD"); environment = create_environment(client, project["id"], admin["access_token"], "PRODUCTION")
    definition = client.post(f"/api/v1/projects/{project['id']}/load-tests", json=payload(environment["id"], target_url="https://prod.example.com"), headers=auth_headers(admin["access_token"])).json()
    denied = client.post(f"/api/v1/load-tests/{definition['id']}/run", json={"confirm_production": True}, headers=auth_headers(admin["access_token"]))
    assert denied.status_code == 403
    monkeypatch.setattr(service.get_settings(), "LOAD_TEST_ALLOW_PRODUCTION", True)
    confirmation = client.post(f"/api/v1/load-tests/{definition['id']}/run", json={}, headers=auth_headers(admin["access_token"]))
    assert confirmation.status_code == 422
    allowed = client.post(f"/api/v1/load-tests/{definition['id']}/run", json={"confirm_production": True}, headers=auth_headers(admin["access_token"]))
    assert allowed.status_code == 202
