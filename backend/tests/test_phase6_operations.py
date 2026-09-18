import hashlib

from app.database.models.operations import ProjectApiKey, Webhook
from tests.conftest import TestingSessionLocal, auth_headers, make_admin, register_user


def _project(client, token):
    response = client.post("/api/v1/projects", json={"name": "Release Quality", "key": "REL"}, headers=auth_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


def _suite(client, project_id, headers):
    suite = client.post(f"/api/v1/projects/{project_id}/automation/suites", json={"name": "smoke-tests", "status": "ACTIVE", "allowed_hosts": ["qa.example.com"]}, headers=headers).json()
    case = client.post(f"/api/v1/automation/suites/{suite['id']}/cases", json={"name": "health"}, headers=headers).json()
    response = client.post(f"/api/v1/automation/cases/{case['id']}/steps", json={"name": "GET health", "step_type": "HTTP_REQUEST", "config": {"request": {"name": "health", "method": "GET", "url": "https://qa.example.com/health"}}}, headers=headers)
    assert response.status_code == 201, response.text
    return suite


def test_ci_api_key_is_one_time_and_can_trigger_by_suite_name(client, monkeypatch):
    from app.automation import queue
    queued = []; monkeypatch.setattr(queue, "enqueue_run", queued.append)
    user = register_user(client, "ci-owner@example.com"); headers = auth_headers(user["access_token"])
    project = _project(client, user["access_token"]); suite = _suite(client, project["id"], headers)
    created = client.post(f"/api/v1/projects/{project['id']}/integrations/api-keys", json={"name": "GitHub Actions"}, headers=headers)
    assert created.status_code == 201, created.text
    token = created.json()["token"]
    listed = client.get(f"/api/v1/projects/{project['id']}/integrations/api-keys", headers=headers)
    assert listed.status_code == 200 and "token" not in listed.json()[0]
    with TestingSessionLocal() as db:
        stored = db.get(ProjectApiKey, created.json()["id"])
        assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert token not in stored.token_hash
    triggered = client.post("/api/v1/ci/test-runs", json={"project": "REL", "suite": "smoke-tests", "commit_sha": "abc123", "branch": "main", "build_number": "42", "ci_provider": "github"}, headers={"X-QAHub-API-Key": token})
    assert triggered.status_code == 202, triggered.text
    assert triggered.json()["status"] == "QUEUED" and queued
    status = client.get(f"/api/v1/ci/test-runs/{triggered.json()['run_id']}", headers={"X-QAHub-API-Key": token})
    assert status.status_code == 200 and status.json()["suite_id"] == suite["id"]
    assert client.get(f"/api/v1/ci/test-runs/{triggered.json()['run_id']}").status_code == 401


def test_webhook_secret_is_hidden_and_events_create_delivery_and_notification(client):
    user = register_user(client, "hooks@example.com"); headers = auth_headers(user["access_token"]); project = _project(client, user["access_token"])
    created = client.post(f"/api/v1/projects/{project['id']}/integrations/webhooks", json={"name": "ChatOps", "url": "https://hooks.example.com/qahub", "secret": "a-long-test-secret", "events": ["bug.created"]}, headers=headers)
    assert created.status_code == 201, created.text
    assert "secret" not in created.text
    with TestingSessionLocal() as db:
        hook = db.get(Webhook, created.json()["id"])
        assert hook.secret_encrypted.startswith("enc:") and "a-long-test-secret" not in hook.secret_encrypted
    bug = client.post(f"/api/v1/projects/{project['id']}/bugs", json={"title": "Checkout error", "description": "The checkout request fails.", "steps_to_reproduce": ["Open checkout"], "severity": "HIGH", "priority": "HIGH"}, headers=headers)
    assert bug.status_code == 201, bug.text
    deliveries = client.get(f"/api/v1/projects/{project['id']}/integrations/webhook-deliveries", headers=headers)
    assert deliveries.status_code == 200 and deliveries.json()[0]["event"] == "bug.created"
    assert "payload" not in deliveries.json()[0]
    notifications = client.get("/api/v1/notifications", headers=headers)
    assert notifications.status_code == 200 and notifications.json()[0]["event"] == "bug.created"
    preferences = client.put("/api/v1/notifications/preferences", json={"project_id": None, "in_app_enabled": False, "email_enabled": False, "webhook_enabled": False, "events": []}, headers=headers)
    assert preferences.status_code == 200
    second = client.post(f"/api/v1/projects/{project['id']}/bugs", json={"title": "Suppressed activity", "description": "Channels are disabled.", "steps_to_reproduce": ["Create bug"], "severity": "LOW", "priority": "LOW"}, headers=headers)
    assert second.status_code == 201
    assert len(client.get(f"/api/v1/projects/{project['id']}/integrations/webhook-deliveries", headers=headers).json()) == 1
    assert len(client.get("/api/v1/notifications", headers=headers).json()) == 1


def test_reports_admin_monitoring_and_error_contract(client):
    user = register_user(client, "reporter@example.com"); headers = auth_headers(user["access_token"]); project = _project(client, user["access_token"])
    report = client.get(f"/api/v1/projects/{project['id']}/reports/qa", headers=headers)
    assert report.status_code == 200 and report.json()["project"]["key"] == "REL"
    for format, content_type in (("json", "application/json"), ("csv", "text/csv"), ("pdf", "application/pdf")):
        exported = client.get(f"/api/v1/projects/{project['id']}/reports/export?format={format}", headers=headers)
        assert exported.status_code == 200 and content_type in exported.headers["content-type"]
    assert client.get("/health/live").json() == {"status": "alive"}
    assert "qahub_process_up 1" in client.get("/metrics").text
    assert client.get("/api/v1/admin/system", headers=headers).status_code == 403
    make_admin("reporter@example.com")
    admin = client.get("/api/v1/admin/system", headers=headers)
    assert admin.status_code == 200 and admin.json()["version"] == "0.6.0"
    missing = client.get("/api/v1/automation/runs/00000000-0000-0000-0000-000000000000", headers=headers)
    assert missing.status_code == 404 and set(missing.json()) == {"error"}
