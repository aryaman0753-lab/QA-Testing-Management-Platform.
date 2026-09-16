from fastapi.testclient import TestClient

from app.api_testing.engine import ExecutionOutcome
from app.database.models.api_testing import ExecutionStatus
from tests.conftest import TestingSessionLocal, auth_headers, register_user


def set_role(email: str, role: str):
    from app.database.models.user import User, UserRole
    db = TestingSessionLocal()
    try:
        db.query(User).filter(User.email == email).one().role = UserRole(role); db.commit()
    finally: db.close()


def project(client: TestClient, token: str, key="APIT"):
    response = client.post("/api/v1/projects", json={"name": "API Project", "key": key}, headers=auth_headers(token))
    assert response.status_code == 201; return response.json()


def collection(client, project_id, token, name="ECOM API"):
    response = client.post(f"/api/v1/projects/{project_id}/api/collections", json={"name": name, "description": "Functional tests"}, headers=auth_headers(token))
    assert response.status_code == 201, response.text; return response.json()


def request_payload(name="Get Users", url="https://example.com/users"):
    return {
        "name": name, "method": "GET", "url": url,
        "headers": [{"key": "Authorization", "value": "secret-token", "enabled": True}],
        "query_parameters": [{"key": "page", "value": "{{page}}", "enabled": True}],
        "body_type": "NONE", "authentication_type": "BEARER", "authentication_config": {"token": "secret-token"},
        "assertions": [{"assertion_type": "STATUS_CODE", "operator": "EQUALS", "expected_value": "200"}],
        "extractors": [{"source": "JSON_PATH", "path": "$.token", "variable_name": "access_token"}],
    }


def saved_request(client, collection_id, token, **overrides):
    payload = request_payload(); payload.update(overrides)
    response = client.post(f"/api/v1/api/collections/{collection_id}/requests", json=payload, headers=auth_headers(token))
    assert response.status_code == 201, response.text; return response.json()


def test_collection_request_crud_and_secret_masking(client: TestClient):
    qa = register_user(client, "api-crud@example.com"); proj = project(client, qa["access_token"]); coll = collection(client, proj["id"], qa["access_token"])
    saved = saved_request(client, coll["id"], qa["access_token"])
    assert saved["headers"][0]["value"] == "********" and saved["authentication_config"]["token"] == "********"
    detail = client.get(f"/api/v1/api/collections/{coll['id']}", headers=auth_headers(qa["access_token"]))
    assert detail.status_code == 200 and detail.json()["request_count"] == 1
    payload = request_payload(name="List Users Updated"); payload["headers"][0]["value"] = "********"; payload["authentication_config"]["token"] = "********"
    updated = client.put(f"/api/v1/api/requests/{saved['id']}", json=payload, headers=auth_headers(qa["access_token"]))
    assert updated.status_code == 200 and updated.json()["name"] == "List Users Updated"
    assert client.delete(f"/api/v1/api/requests/{saved['id']}", headers=auth_headers(qa["access_token"])).status_code == 204


def test_environment_encryption_masking_and_update(client: TestClient):
    qa = register_user(client, "api-env@example.com"); proj = project(client, qa["access_token"], "ENV")
    created = client.post(f"/api/v1/projects/{proj['id']}/api/environments", json={"name": "QA", "variables": [{"name": "base_url", "value": "https://qa.example.com"}, {"name": "access_token", "value": "top-secret", "is_secret": True}]}, headers=auth_headers(qa["access_token"]))
    assert created.status_code == 201 and created.json()["variables"][1]["value"] == "********"
    from app.database.models.api_testing import ApiEnvironment
    db = TestingSessionLocal()
    try: assert db.get(ApiEnvironment, created.json()["id"]).variables["access_token"]["value"].startswith("enc:")
    finally: db.close()
    updated = client.put(f"/api/v1/api/environments/{created.json()['id']}", json={"name": "QA", "variables": [{"name": "access_token", "value": "********", "is_secret": True}]}, headers=auth_headers(qa["access_token"]))
    assert updated.status_code == 200 and updated.json()["variables"][0]["value"] == "********"


def test_permissions_and_project_isolation(client: TestClient):
    qa = register_user(client, "api-owner@example.com"); outsider = register_user(client, "api-outsider@example.com"); developer = register_user(client, "api-dev@example.com"); set_role("api-dev@example.com", "DEVELOPER")
    proj = project(client, qa["access_token"], "PERM"); coll = collection(client, proj["id"], qa["access_token"])
    hidden = client.get(f"/api/v1/api/collections/{coll['id']}", headers=auth_headers(outsider["access_token"]))
    denied = client.post(f"/api/v1/api/collections/{coll['id']}/requests", json=request_payload(), headers=auth_headers(developer["access_token"]))
    assert hidden.status_code == 404 and denied.status_code == 404


def test_execution_run_assertions_history_analytics_and_bug_link(client: TestClient, monkeypatch):
    from app.api_testing import service
    async def fake_execute(self, request, *args, **kwargs):
        return ExecutionOutcome(status=ExecutionStatus.PASS, request_name=request.name, method=request.method.value, resolved_url="https://example.com/users", status_code=500, response_time_ms=25, response_size=20, content_type="application/json", headers={"content-type": "application/json", "set-cookie": "secret"}, body='{"token":"abc"}', timing={"total_ms": 25})
    monkeypatch.setattr(service.ApiExecutionService, "execute", fake_execute)
    qa = register_user(client, "api-run@example.com"); proj = project(client, qa["access_token"], "RUN"); coll = collection(client, proj["id"], qa["access_token"]); saved = saved_request(client, coll["id"], qa["access_token"])
    run = client.post(f"/api/v1/api/requests/{saved['id']}/execute", json={"runtime_variables": {"page": "1"}}, headers=auth_headers(qa["access_token"]))
    assert run.status_code == 200, run.text
    data = run.json(); result = data["results"][0]
    assert data["run_key"] == "API-RUN-001" and data["status"] == "FAIL"
    assert result["assertions_failed"] == 1 and result["response_headers"]["set-cookie"] == "********"
    history = client.get(f"/api/v1/api/runs?project_id={proj['id']}", headers=auth_headers(qa["access_token"]))
    metrics = client.get(f"/api/v1/projects/{proj['id']}/api/analytics", headers=auth_headers(qa["access_token"]))
    assert history.json()["total"] == 1 and metrics.json()["total_runs"] == 1
    suggestion = client.get(f"/api/v1/api/results/{result['id']}/bug-suggestion", headers=auth_headers(qa["access_token"]))
    assert "Get Users" in suggestion.json()["title"]
    bug = client.post(f"/api/v1/api/results/{result['id']}/bugs", json=suggestion.json(), headers=auth_headers(qa["access_token"]))
    assert bug.status_code == 201 and bug.json()["bug_key"] == "RUN-001"
    from app.database.models.bug import Bug
    db = TestingSessionLocal()
    try: assert str(db.get(Bug, bug.json()["id"]).discovered_from_test_result_id) == result["id"]
    finally: db.close()


def test_collection_execution_chains_extracted_variables(client: TestClient, monkeypatch):
    from app.api_testing import service
    seen = []
    async def fake_execute(self, request, environment_variables=None, extracted_variables=None, runtime_variables=None, **kwargs):
        seen.append(dict(extracted_variables or {}))
        body = '{"token":"chain-token"}' if request.name == "Login" else '{"ok":true}'
        return ExecutionOutcome(status=ExecutionStatus.PASS, request_name=request.name, method=request.method.value, resolved_url="https://example.com", status_code=200, response_time_ms=1, response_size=len(body), headers={}, body=body)
    monkeypatch.setattr(service.ApiExecutionService, "execute", fake_execute)
    qa = register_user(client, "api-chain@example.com"); proj = project(client, qa["access_token"], "CHAIN"); coll = collection(client, proj["id"], qa["access_token"])
    saved_request(client, coll["id"], qa["access_token"], name="Login", query_parameters=[])
    profile = saved_request(client, coll["id"], qa["access_token"], name="Profile", query_parameters=[], extractors=[])
    run = client.post(f"/api/v1/api/collections/{coll['id']}/execute", json={}, headers=auth_headers(qa["access_token"]))
    assert run.status_code == 200, run.text
    assert run.json()["requests_total"] == 2 and seen[1]["access_token"] == "chain-token"
    seen.clear()
    selected = client.post(f"/api/v1/api/collections/{coll['id']}/execute", json={"request_ids": [profile["id"]]}, headers=auth_headers(qa["access_token"]))
    assert selected.status_code == 200 and selected.json()["requests_total"] == 1 and len(seen) == 1
