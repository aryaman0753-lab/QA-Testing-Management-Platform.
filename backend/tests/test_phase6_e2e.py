"""Release-path API E2E: functional test -> automation -> bug -> CI -> webhook -> report."""
from datetime import datetime, timezone

from app.api_testing.engine import ExecutionOutcome
from app.database.models.api_testing import ExecutionStatus
from app.database.models.automation import AutomationRun
from tests.conftest import TestingSessionLocal, auth_headers, register_user


def test_release_quality_workflow(client, monkeypatch):
    from app.api_testing import service as api_service
    from app.automation import queue

    async def fake_execute(self, request, **kwargs):
        return ExecutionOutcome(status=ExecutionStatus.PASS, request_name=request.name, method=request.method.value, resolved_url="https://qa.example.com/health", status_code=200, response_time_ms=18, response_size=2, headers={}, body="{}")
    monkeypatch.setattr(api_service.ApiExecutionService, "execute", fake_execute)
    queued = []; monkeypatch.setattr(queue, "enqueue_run", queued.append)

    account = register_user(client, "release-e2e@example.com"); headers = auth_headers(account["access_token"])
    project = client.post("/api/v1/projects", json={"name": "Release E2E", "key": "E2E"}, headers=headers).json()
    collection = client.post(f"/api/v1/projects/{project['id']}/api/collections", json={"name": "Smoke"}, headers=headers).json()
    request = client.post(f"/api/v1/api/collections/{collection['id']}/requests", json={"name": "Health", "method": "GET", "url": "https://qa.example.com/health", "body_type": "NONE", "authentication_type": "NONE", "assertions": [{"assertion_type": "STATUS_CODE", "operator": "EQUALS", "expected_value": "200"}]}, headers=headers).json()
    executed = client.post(f"/api/v1/api/requests/{request['id']}/execute", json={}, headers=headers)
    assert executed.status_code == 200

    suite = client.post(f"/api/v1/projects/{project['id']}/automation/suites", json={"name": "release-smoke", "status": "ACTIVE", "allowed_hosts": ["qa.example.com"]}, headers=headers).json()
    case = client.post(f"/api/v1/automation/suites/{suite['id']}/cases", json={"name": "Health"}, headers=headers).json()
    assert client.post(f"/api/v1/automation/cases/{case['id']}/steps", json={"name": "Health", "step_type": "HTTP_REQUEST", "api_request_id": request["id"], "config": {}}, headers=headers).status_code == 201
    manual = client.post(f"/api/v1/automation/suites/{suite['id']}/run", json={}, headers=headers).json()
    with TestingSessionLocal() as db:
        run = db.get(AutomationRun, manual["id"]); run.status = "PASSED"; run.passed_cases = 1; run.completed_at = datetime.now(timezone.utc); db.commit()

    hook = client.post(f"/api/v1/projects/{project['id']}/integrations/webhooks", json={"name": "release-events", "url": "https://hooks.example.com/qahub", "secret": "release-signing-secret", "events": ["bug.created"]}, headers=headers)
    assert hook.status_code == 201
    bug = client.post(f"/api/v1/projects/{project['id']}/bugs", json={"title": "Release observation", "description": "Captured during release verification.", "steps_to_reproduce": ["Run release smoke"], "severity": "MEDIUM", "priority": "MEDIUM"}, headers=headers)
    assert bug.status_code == 201

    key = client.post(f"/api/v1/projects/{project['id']}/integrations/api-keys", json={"name": "release-pipeline"}, headers=headers).json()["token"]
    ci = client.post("/api/v1/ci/test-runs", json={"project": "E2E", "suite": "release-smoke", "ci_provider": "generic", "commit_sha": "abc123"}, headers={"X-QAHub-API-Key": key})
    assert ci.status_code == 202 and len(queued) == 2
    deliveries = client.get(f"/api/v1/projects/{project['id']}/integrations/webhook-deliveries", headers=headers).json()
    report = client.get(f"/api/v1/projects/{project['id']}/reports/qa", headers=headers).json()
    assert deliveries[0]["event"] == "bug.created"
    assert report["api_testing"]["requests_executed"] == 1
    assert report["bugs"]["open"] == 1
