import json

from sqlalchemy import select

from app.automation.service import reveal_step_config
from app.database.models.automation import AutomationTestStep
from tests.conftest import TestingSessionLocal, auth_headers, register_user


def create_project(client, token, key="AUTO"):
    response = client.post(
        "/api/v1/projects",
        json={"name": "Automation Project", "key": key},
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def suite_payload(**changes):
    payload = {
        "name": "Account lifecycle",
        "description": "Login, create, read and delete a user",
        "status": "ACTIVE",
        "allowed_hosts": ["qa.example.com"],
        "max_retries": 2,
        "auto_create_bugs": True,
    }
    payload.update(changes)
    return payload


def request_step(**changes):
    payload = {
        "name": "Login",
        "step_type": "HTTP_REQUEST",
        "enabled": True,
        "order_index": 0,
        "config": {"request": {
            "name": "Login request",
            "method": "POST",
            "url": "https://qa.example.com/login?api_key=secret-query",
            "headers": [{"key": "Authorization", "value": "Bearer top-secret", "enabled": True}],
            "query_parameters": [],
            "body_type": "JSON",
            "body": '{"password":"top-secret"}',
            "authentication_type": "BEARER",
            "authentication_config": {"token": "top-secret"},
            "assertions": [],
            "extractors": [],
            "position": 0,
        }},
    }
    payload.update(changes)
    return payload


def test_suite_case_step_crud_masks_secrets_reorders_and_audits(client):
    qa = register_user(client, "automation-api@example.com")
    headers = auth_headers(qa["access_token"])
    project = create_project(client, qa["access_token"])

    created = client.post(
        f"/api/v1/projects/{project['id']}/automation/suites",
        json=suite_payload(), headers=headers,
    )
    assert created.status_code == 201, created.text
    suite = created.json()
    case_one = client.post(
        f"/api/v1/automation/suites/{suite['id']}/cases",
        json={"name": "Login flow", "description": "", "timeout": 45}, headers=headers,
    )
    case_two = client.post(
        f"/api/v1/automation/suites/{suite['id']}/cases",
        json={"name": "Cleanup", "description": "", "timeout": 30}, headers=headers,
    )
    assert case_one.status_code == case_two.status_code == 201

    step = client.post(
        f"/api/v1/automation/cases/{case_one.json()['id']}/steps",
        json=request_step(), headers=headers,
    )
    assert step.status_code == 201, step.text
    returned = step.json()["config"]["request"]
    serialized = json.dumps(returned)
    assert "top-secret" not in serialized and "secret-query" not in serialized
    assert returned["authentication_config"]["token"] == "********"
    assert returned["body"] == "********"

    with TestingSessionLocal() as db:
        stored = db.scalar(select(AutomationTestStep).where(AutomationTestStep.id == step.json()["id"]))
        assert "top-secret" not in json.dumps(stored.config)
        assert reveal_step_config(stored.config)["request"]["authentication_config"]["token"] == "top-secret"

    returned["name"] = "Login request updated"
    updated = client.patch(
        f"/api/v1/automation/steps/{step.json()['id']}",
        json={"name": "Updated login", "config": {"request": returned}}, headers=headers,
    )
    assert updated.status_code == 200, updated.text
    with TestingSessionLocal() as db:
        stored = db.scalar(select(AutomationTestStep).where(AutomationTestStep.id == step.json()["id"]))
        assert reveal_step_config(stored.config)["request"]["authentication_config"]["token"] == "top-secret"

    reordered = client.put(
        f"/api/v1/automation/suites/{suite['id']}/cases/reorder",
        json={"ids": [case_two.json()["id"], case_one.json()["id"]]}, headers=headers,
    )
    assert reordered.status_code == 200
    assert [item["id"] for item in reordered.json()["cases"]] == [case_two.json()["id"], case_one.json()["id"]]

    listed = client.get(f"/api/v1/projects/{project['id']}/automation/suites", headers=headers)
    detail = client.get(f"/api/v1/automation/suites/{suite['id']}", headers=headers)
    audit = client.get(f"/api/v1/projects/{project['id']}/automation/audit", headers=headers)
    assert listed.status_code == detail.status_code == audit.status_code == 200
    assert listed.json()["total"] == 1 and len(detail.json()["cases"]) == 2
    assert {entry["action"] for entry in audit.json()["items"]} >= {"SUITE_CREATED", "CASE_CREATED", "STEP_CREATED", "STEP_UPDATED", "CASES_REORDERED"}

    assert client.delete(f"/api/v1/automation/steps/{step.json()['id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/automation/cases/{case_two.json()['id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/automation/suites/{suite['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/projects/{project['id']}/automation/suites", headers=headers).json()["total"] == 0


def test_run_schedule_statistics_permissions_and_project_isolation(client, monkeypatch):
    from app.automation import queue

    queued = []
    monkeypatch.setattr(queue, "enqueue_run", queued.append)
    monkeypatch.setattr(queue, "request_stop", lambda run_id: None)
    qa = register_user(client, "automation-run-api@example.com")
    headers = auth_headers(qa["access_token"])
    project = create_project(client, qa["access_token"], "ARUN")
    suite = client.post(
        f"/api/v1/projects/{project['id']}/automation/suites",
        json=suite_payload(name="Scheduled smoke"), headers=headers,
    ).json()
    case = client.post(
        f"/api/v1/automation/suites/{suite['id']}/cases",
        json={"name": "Health", "timeout": 20}, headers=headers,
    ).json()
    assert client.post(
        f"/api/v1/automation/cases/{case['id']}/steps",
        json=request_step(name="Health", config={"request": {"name": "Health", "url": "https://qa.example.com/health"}}),
        headers=headers,
    ).status_code == 201

    schedule = client.post(
        f"/api/v1/projects/{project['id']}/automation/schedules",
        json={"suite_id": suite["id"], "cron_expression": "*/5 * * * *", "timezone": "UTC", "enabled": True},
        headers=headers,
    )
    assert schedule.status_code == 201, schedule.text
    invalid_cron = client.post(
        f"/api/v1/projects/{project['id']}/automation/schedules",
        json={"suite_id": suite["id"], "cron_expression": "bad cron", "timezone": "UTC"}, headers=headers,
    )
    assert invalid_cron.status_code == 422

    started = client.post(f"/api/v1/automation/suites/{suite['id']}/run", json={}, headers=headers)
    assert started.status_code == 202, started.text
    assert started.json()["status"] == "QUEUED" and len(queued) == 1
    duplicate = client.post(f"/api/v1/automation/suites/{suite['id']}/run", json={}, headers=headers)
    assert duplicate.status_code == 409
    stopped = client.post(f"/api/v1/automation/runs/{started.json()['id']}/stop", headers=headers)
    assert stopped.status_code == 200 and stopped.json()["status"] == "CANCELLED"

    history = client.get(f"/api/v1/projects/{project['id']}/automation/runs?status=CANCELLED", headers=headers)
    detail = client.get(f"/api/v1/automation/runs/{started.json()['id']}", headers=headers)
    results = client.get(f"/api/v1/automation/runs/{started.json()['id']}/results", headers=headers)
    stats = client.get(f"/api/v1/projects/{project['id']}/automation/statistics", headers=headers)
    assert history.status_code == detail.status_code == results.status_code == stats.status_code == 200
    assert history.json()["total"] == 1 and results.json() == [] and stats.json()["total_runs"] == 1

    viewer = register_user(client, "automation-viewer@example.com")
    add_viewer = client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": viewer["user"]["id"], "project_role": "VIEWER"}, headers=headers,
    )
    assert add_viewer.status_code == 201, add_viewer.text
    viewer_headers = auth_headers(viewer["access_token"])
    assert client.get(f"/api/v1/automation/suites/{suite['id']}", headers=viewer_headers).status_code == 200
    assert client.patch(f"/api/v1/automation/suites/{suite['id']}", json={"name": "Forbidden"}, headers=viewer_headers).status_code == 403

    outsider = register_user(client, "automation-outsider@example.com")
    outsider_headers = auth_headers(outsider["access_token"])
    assert client.get(f"/api/v1/automation/suites/{suite['id']}", headers=outsider_headers).status_code == 404
    assert client.get(f"/api/v1/projects/{project['id']}/automation/runs", headers=outsider_headers).status_code == 404

    paused = client.patch(f"/api/v1/automation/schedules/{schedule.json()['id']}", json={"enabled": False}, headers=headers)
    assert paused.status_code == 200 and paused.json()["next_run_at"] is None
    assert client.delete(f"/api/v1/automation/schedules/{schedule.json()['id']}", headers=headers).status_code == 204
