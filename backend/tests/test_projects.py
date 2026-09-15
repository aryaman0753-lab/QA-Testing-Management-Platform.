from fastapi.testclient import TestClient

from tests.conftest import auth_headers, make_admin, register_user


def _create_project(client: TestClient, token: str, name="E-Commerce Application", key="ecom"):
    return client.post(
        "/api/v1/projects",
        json={"name": name, "key": key, "description": "An online store."},
        headers=auth_headers(token),
    )


def test_create_project(client: TestClient):
    user = register_user(client, "owner@example.com")
    response = _create_project(client, user["access_token"])
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["key"] == "ECOM"  # lowercase input is normalized to uppercase
    assert body["status"] == "ACTIVE"


def test_create_project_rejects_bad_key(client: TestClient):
    user = register_user(client, "badkey@example.com")
    response = _create_project(client, user["access_token"], key="!!")
    assert response.status_code == 422


def test_duplicate_project_key_rejected(client: TestClient):
    user = register_user(client, "dupkey@example.com")
    _create_project(client, user["access_token"], key="DUP")
    response = _create_project(client, user["access_token"], name="Another", key="DUP")
    assert response.status_code == 409


def test_developer_cannot_create_project(client: TestClient):
    from app.database.models.user import UserRole
    from tests.conftest import TestingSessionLocal
    from app.database.models.user import User

    user = register_user(client, "dev@example.com")
    db = TestingSessionLocal()
    db.query(User).filter(User.email == "dev@example.com").update({"role": UserRole.DEVELOPER})
    db.commit()
    db.close()

    response = _create_project(client, user["access_token"], key="DEVX")
    assert response.status_code == 403


def test_list_projects_only_shows_member_projects(client: TestClient):
    owner = register_user(client, "owner2@example.com")
    outsider = register_user(client, "outsider@example.com")
    _create_project(client, owner["access_token"], key="MINE")

    response = client.get("/api/v1/projects", headers=auth_headers(outsider["access_token"]))
    assert response.status_code == 200
    assert response.json() == []

    response = client.get("/api/v1/projects", headers=auth_headers(owner["access_token"]))
    assert len(response.json()) == 1


def test_get_project(client: TestClient):
    owner = register_user(client, "getter@example.com")
    created = _create_project(client, owner["access_token"], key="GETP").json()

    response = client.get(f"/api/v1/projects/{created['id']}", headers=auth_headers(owner["access_token"]))
    assert response.status_code == 200
    assert response.json()["key"] == "GETP"


def test_get_project_not_found_for_non_member(client: TestClient):
    owner = register_user(client, "priv@example.com")
    outsider = register_user(client, "priv2@example.com")
    created = _create_project(client, owner["access_token"], key="PRIV").json()

    response = client.get(f"/api/v1/projects/{created['id']}", headers=auth_headers(outsider["access_token"]))
    assert response.status_code == 404


def test_update_project(client: TestClient):
    owner = register_user(client, "updater@example.com")
    created = _create_project(client, owner["access_token"], key="UPD").json()

    response = client.put(
        f"/api/v1/projects/{created['id']}",
        json={"name": "Renamed Project"},
        headers=auth_headers(owner["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Project"


def test_non_owner_cannot_update_project(client: TestClient):
    owner = register_user(client, "u1@example.com")
    other = register_user(client, "u2@example.com")
    created = _create_project(client, owner["access_token"], key="NOUP").json()

    response = client.put(
        f"/api/v1/projects/{created['id']}",
        json={"name": "Hacked"},
        headers=auth_headers(other["access_token"]),
    )
    assert response.status_code == 404  # not a member, so not found


def test_archive_project(client: TestClient):
    owner = register_user(client, "archiver@example.com")
    created = _create_project(client, owner["access_token"], key="ARCH").json()

    response = client.delete(f"/api/v1/projects/{created['id']}", headers=auth_headers(owner["access_token"]))
    assert response.status_code == 200
    assert response.json()["status"] == "ARCHIVED"

    # The project still exists (soft delete), just archived.
    response = client.get(f"/api/v1/projects/{created['id']}", headers=auth_headers(owner["access_token"]))
    assert response.status_code == 200
    assert response.json()["status"] == "ARCHIVED"


def test_admin_can_see_and_manage_any_project(client: TestClient):
    owner = register_user(client, "adminowner@example.com")
    admin = register_user(client, "superadmin@example.com")
    make_admin("superadmin@example.com")
    created = _create_project(client, owner["access_token"], key="ADMV").json()

    response = client.get(f"/api/v1/projects/{created['id']}", headers=auth_headers(admin["access_token"]))
    assert response.status_code == 200


def test_unauthorized_access_rejected(client: TestClient):
    response = client.get("/api/v1/projects")
    assert response.status_code == 401
