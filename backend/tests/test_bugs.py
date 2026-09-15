from fastapi.testclient import TestClient

from tests.conftest import TestingSessionLocal, auth_headers, make_admin, register_user


def create_project(client: TestClient, token: str, key: str = "BUGS") -> dict:
    response = client.post("/api/v1/projects", json={"name": "Bug Project", "key": key}, headers=auth_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


def add_member(client: TestClient, project_id: str, owner_token: str, user_id: str) -> None:
    response = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": user_id, "project_role": "MEMBER"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 201, response.text


def bug_payload(title: str = "Checkout fails", **overrides) -> dict:
    payload = {
        "title": title,
        "description": "The checkout action displays an unexpected error.",
        "steps_to_reproduce": ["Open cart", "Click checkout"],
        "expected_result": "Order screen appears.",
        "actual_result": "An error appears.",
        "severity": "HIGH",
        "priority": "URGENT",
        "environment": "QA",
    }
    payload.update(overrides)
    return payload


def create_bug(client: TestClient, project_id: str, token: str, **overrides) -> dict:
    response = client.post(
        f"/api/v1/projects/{project_id}/bugs",
        json=bug_payload(**overrides),
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def set_role(email: str, role: str) -> None:
    from app.database.models.user import User, UserRole
    db = TestingSessionLocal()
    try:
        db.query(User).filter(User.email == email).one().role = UserRole(role)
        db.commit()
    finally:
        db.close()


def test_bug_creation_allocates_project_specific_human_keys(client: TestClient):
    qa = register_user(client, "qa-bugs@example.com")
    first_project = create_project(client, qa["access_token"], "ECOM")
    second_project = create_project(client, qa["access_token"], "WEB")

    first = create_bug(client, first_project["id"], qa["access_token"])
    second = create_bug(client, first_project["id"], qa["access_token"], title="Second issue")
    other = create_bug(client, second_project["id"], qa["access_token"])

    assert (first["bug_key"], second["bug_key"], other["bug_key"]) == ("ECOM-001", "ECOM-002", "WEB-001")
    assert first["reporter"]["email"] == "qa-bugs@example.com"
    assert first["history"][0]["action"] == "CREATED"


def test_bug_creation_validates_required_fields_and_role(client: TestClient):
    qa = register_user(client, "qa-validation@example.com")
    developer = register_user(client, "dev-validation@example.com")
    set_role("dev-validation@example.com", "DEVELOPER")
    project = create_project(client, qa["access_token"], "VALID")
    add_member(client, project["id"], qa["access_token"], developer["user"]["id"])

    invalid = client.post(f"/api/v1/projects/{project['id']}/bugs", json=bug_payload(title=" "), headers=auth_headers(qa["access_token"]))
    forbidden = client.post(f"/api/v1/projects/{project['id']}/bugs", json=bug_payload(), headers=auth_headers(developer["access_token"]))
    assert invalid.status_code == 422
    assert forbidden.status_code == 403


def test_list_search_filter_sort_and_pagination(client: TestClient):
    qa = register_user(client, "qa-list@example.com")
    project = create_project(client, qa["access_token"], "LIST")
    create_bug(client, project["id"], qa["access_token"], title="Payment goal failure", severity="CRITICAL")
    create_bug(client, project["id"], qa["access_token"], title="Small layout issue", severity="LOW", priority="LOW")
    create_bug(client, project["id"], qa["access_token"], title="Another issue", severity="MEDIUM")

    response = client.get(
        f"/api/v1/projects/{project['id']}/bugs",
        params={"search": "goal", "severity": "CRITICAL", "page": 1, "page_size": 1, "sort_by": "bug_number", "sort_order": "asc"},
        headers=auth_headers(qa["access_token"]),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1 and body["total_pages"] == 1
    assert body["items"][0]["bug_key"] == "LIST-001"


def test_assignee_must_be_project_member(client: TestClient):
    qa = register_user(client, "qa-assign@example.com")
    member = register_user(client, "member-assign@example.com")
    outsider = register_user(client, "outsider-assign@example.com")
    project = create_project(client, qa["access_token"], "ASGN")
    add_member(client, project["id"], qa["access_token"], member["user"]["id"])
    bug = create_bug(client, project["id"], qa["access_token"])

    rejected = client.patch(f"/api/v1/bugs/{bug['id']}/assignee", json={"assigned_to": outsider["user"]["id"]}, headers=auth_headers(qa["access_token"]))
    accepted = client.patch(f"/api/v1/bugs/{bug['id']}/assignee", json={"assigned_to": member["user"]["id"]}, headers=auth_headers(qa["access_token"]))
    assert rejected.status_code == 422
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ASSIGNED"


def test_status_workflow_and_invalid_transition(client: TestClient):
    qa = register_user(client, "qa-status@example.com")
    developer = register_user(client, "dev-status@example.com")
    set_role("dev-status@example.com", "DEVELOPER")
    project = create_project(client, qa["access_token"], "FLOW")
    add_member(client, project["id"], qa["access_token"], developer["user"]["id"])
    bug = create_bug(client, project["id"], qa["access_token"], assigned_to=developer["user"]["id"])

    invalid = client.patch(f"/api/v1/bugs/{bug['id']}/status", json={"status": "CLOSED"}, headers=auth_headers(qa["access_token"]))
    assert invalid.status_code == 422
    for status in ["IN_PROGRESS", "FIXED"]:
        response = client.patch(f"/api/v1/bugs/{bug['id']}/status", json={"status": status}, headers=auth_headers(developer["access_token"]))
        assert response.status_code == 200, response.text
    for status in ["QA_VERIFICATION", "VERIFIED", "CLOSED"]:
        response = client.patch(f"/api/v1/bugs/{bug['id']}/status", json={"status": status}, headers=auth_headers(qa["access_token"]))
        assert response.status_code == 200, response.text
    assert response.json()["closed_at"] is not None
    assert len([row for row in response.json()["history"] if row["action"] == "STATUS_CHANGED"]) >= 5


def test_qa_can_reopen_failed_verification(client: TestClient):
    qa = register_user(client, "qa-reopen@example.com")
    project = create_project(client, qa["access_token"], "OPEN")
    bug = create_bug(client, project["id"], qa["access_token"])
    make_admin("qa-reopen@example.com")
    for status in ["IN_PROGRESS", "FIXED", "QA_VERIFICATION"]:
        response = client.patch(f"/api/v1/bugs/{bug['id']}/status", json={"status": status}, headers=auth_headers(qa["access_token"]))
        assert response.status_code == 200
    set_role("qa-reopen@example.com", "QA_ENGINEER")
    response = client.patch(f"/api/v1/bugs/{bug['id']}/status", json={"status": "REOPENED"}, headers=auth_headers(qa["access_token"]))
    assert response.status_code == 200 and response.json()["status"] == "REOPENED"


def test_comments_owner_edit_delete_and_history(client: TestClient):
    qa = register_user(client, "qa-comments@example.com")
    member = register_user(client, "member-comments@example.com")
    project = create_project(client, qa["access_token"], "COMM")
    add_member(client, project["id"], qa["access_token"], member["user"]["id"])
    bug = create_bug(client, project["id"], qa["access_token"])
    created = client.post(f"/api/v1/bugs/{bug['id']}/comments", json={"comment": "Investigating this."}, headers=auth_headers(member["access_token"]))
    assert created.status_code == 201
    comment_id = created.json()["id"]
    denied = client.put(f"/api/v1/bugs/{bug['id']}/comments/{comment_id}", json={"comment": "Changed"}, headers=auth_headers(qa["access_token"]))
    edited = client.put(f"/api/v1/bugs/{bug['id']}/comments/{comment_id}", json={"comment": "Updated note"}, headers=auth_headers(member["access_token"]))
    deleted = client.delete(f"/api/v1/bugs/{bug['id']}/comments/{comment_id}", headers=auth_headers(member["access_token"]))
    assert denied.status_code == 403 and edited.status_code == 200 and deleted.status_code == 204


def test_updates_create_audit_history(client: TestClient):
    qa = register_user(client, "qa-history@example.com")
    project = create_project(client, qa["access_token"], "HIST")
    bug = create_bug(client, project["id"], qa["access_token"])
    response = client.patch(f"/api/v1/bugs/{bug['id']}", json={"severity": "CRITICAL", "title": "Updated checkout issue"}, headers=auth_headers(qa["access_token"]))
    assert response.status_code == 200
    changed = {(row["field_name"], row["new_value"]) for row in response.json()["history"] if row["action"] == "FIELD_CHANGED"}
    assert ("severity", "CRITICAL") in changed and ("title", "Updated checkout issue") in changed


def test_attachment_validation_and_authorization(client: TestClient, tmp_path, monkeypatch):
    from app.bugs import service
    monkeypatch.setattr(service.settings, "ATTACHMENT_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(service.settings, "MAX_ATTACHMENT_SIZE_MB", 1)
    qa = register_user(client, "qa-files@example.com")
    pm = register_user(client, "pm-files@example.com")
    set_role("pm-files@example.com", "PROJECT_MANAGER")
    project = create_project(client, qa["access_token"], "FILE")
    add_member(client, project["id"], qa["access_token"], pm["user"]["id"])
    bug = create_bug(client, project["id"], qa["access_token"])
    png = b"\x89PNG\r\n\x1a\n" + b"test-image"
    allowed = client.post(f"/api/v1/bugs/{bug['id']}/attachments", files={"file": ("evidence.png", png, "application/octet-stream")}, headers=auth_headers(qa["access_token"]))
    invalid = client.post(f"/api/v1/bugs/{bug['id']}/attachments", files={"file": ("payload.exe", b"MZ", "application/octet-stream")}, headers=auth_headers(qa["access_token"]))
    forbidden = client.post(f"/api/v1/bugs/{bug['id']}/attachments", files={"file": ("note.txt", b"hello", "text/plain")}, headers=auth_headers(pm["access_token"]))
    oversized = client.post(f"/api/v1/bugs/{bug['id']}/attachments", files={"file": ("large.txt", b"a" * (1024 * 1024 + 1), "text/plain")}, headers=auth_headers(qa["access_token"]))
    assert allowed.status_code == 201, allowed.text
    assert invalid.status_code == 422 and forbidden.status_code == 403 and oversized.status_code == 422
    downloaded = client.get(allowed.json()["download_url"], headers=auth_headers(qa["access_token"]))
    assert downloaded.status_code == 200 and downloaded.content == png


def test_dashboard_analytics_and_csv_report(client: TestClient):
    qa = register_user(client, "qa-report@example.com")
    project = create_project(client, qa["access_token"], "REPT")
    create_bug(client, project["id"], qa["access_token"])
    analytics = client.get(f"/api/v1/projects/{project['id']}/bugs/analytics", headers=auth_headers(qa["access_token"]))
    report = client.get(f"/api/v1/projects/{project['id']}/bugs/report.csv", headers=auth_headers(qa["access_token"]))
    assert analytics.status_code == 200 and analytics.json()["total"] == 1
    assert report.status_code == 200 and "REPT-001" in report.text


def test_developer_only_sees_assigned_bugs_and_edits_technical_fields(client: TestClient):
    qa = register_user(client, "qa-devscope@example.com")
    developer = register_user(client, "dev-scope@example.com")
    set_role("dev-scope@example.com", "DEVELOPER")
    project = create_project(client, qa["access_token"], "SCOPE")
    add_member(client, project["id"], qa["access_token"], developer["user"]["id"])
    assigned = create_bug(client, project["id"], qa["access_token"], assigned_to=developer["user"]["id"])
    hidden = create_bug(client, project["id"], qa["access_token"], title="Not assigned")

    listed = client.get(f"/api/v1/projects/{project['id']}/bugs", headers=auth_headers(developer["access_token"]))
    hidden_detail = client.get(f"/api/v1/bugs/{hidden['id']}", headers=auth_headers(developer["access_token"]))
    technical = client.patch(f"/api/v1/bugs/{assigned['id']}", json={"actual_result": "Stack trace captured."}, headers=auth_headers(developer["access_token"]))
    triage = client.patch(f"/api/v1/bugs/{assigned['id']}", json={"severity": "CRITICAL"}, headers=auth_headers(developer["access_token"]))
    assert listed.status_code == 200 and listed.json()["total"] == 1
    assert hidden_detail.status_code == 404
    assert technical.status_code == 200 and triage.status_code == 403


def test_admin_soft_archives_bug_and_can_retrieve_audit(client: TestClient):
    admin = register_user(client, "archive-admin@example.com")
    make_admin("archive-admin@example.com")
    project = create_project(client, admin["access_token"], "ARCH")
    bug = create_bug(client, project["id"], admin["access_token"])
    archived = client.delete(f"/api/v1/bugs/{bug['id']}", headers=auth_headers(admin["access_token"]))
    normal = client.get(f"/api/v1/bugs/{bug['id']}", headers=auth_headers(admin["access_token"]))
    audit = client.get(f"/api/v1/bugs/{bug['id']}?include_archived=true", headers=auth_headers(admin["access_token"]))
    listed = client.get(f"/api/v1/projects/{project['id']}/bugs", headers=auth_headers(admin["access_token"]))
    assert archived.status_code == 204 and normal.status_code == 404
    assert audit.status_code == 200 and audit.json()["history"][0]["action"] == "ARCHIVED"
    assert listed.json()["total"] == 0
