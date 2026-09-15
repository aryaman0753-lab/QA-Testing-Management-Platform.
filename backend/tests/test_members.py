from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_user


def _create_project(client: TestClient, token: str, key="MEMB"):
    return client.post(
        "/api/v1/projects",
        json={"name": "Membership Test Project", "key": key},
        headers=auth_headers(token),
    ).json()


def test_add_member(client: TestClient):
    owner = register_user(client, "memowner@example.com")
    member = register_user(client, "member1@example.com")
    project = _create_project(client, owner["access_token"], key="ADDM")

    response = client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": member["user"]["id"], "project_role": "MEMBER"},
        headers=auth_headers(owner["access_token"]),
    )
    assert response.status_code == 201, response.text
    assert response.json()["project_role"] == "MEMBER"
    assert response.json()["user"]["email"] == "member1@example.com"


def test_cannot_add_same_member_twice(client: TestClient):
    owner = register_user(client, "memowner2@example.com")
    member = register_user(client, "member2@example.com")
    project = _create_project(client, owner["access_token"], key="DUPM")

    payload = {"user_id": member["user"]["id"], "project_role": "MEMBER"}
    client.post(f"/api/v1/projects/{project['id']}/members", json=payload, headers=auth_headers(owner["access_token"]))
    response = client.post(
        f"/api/v1/projects/{project['id']}/members", json=payload, headers=auth_headers(owner["access_token"])
    )
    assert response.status_code == 409


def test_list_members(client: TestClient):
    owner = register_user(client, "memowner3@example.com")
    member = register_user(client, "member3@example.com")
    project = _create_project(client, owner["access_token"], key="LISTM")

    client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": member["user"]["id"], "project_role": "VIEWER"},
        headers=auth_headers(owner["access_token"]),
    )

    response = client.get(f"/api/v1/projects/{project['id']}/members", headers=auth_headers(owner["access_token"]))
    assert response.status_code == 200
    emails = {m["user"]["email"] for m in response.json()}
    assert emails == {"memowner3@example.com", "member3@example.com"}


def test_remove_member(client: TestClient):
    owner = register_user(client, "memowner4@example.com")
    member = register_user(client, "member4@example.com")
    project = _create_project(client, owner["access_token"], key="REMM")

    client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": member["user"]["id"], "project_role": "MEMBER"},
        headers=auth_headers(owner["access_token"]),
    )

    response = client.delete(
        f"/api/v1/projects/{project['id']}/members/{member['user']['id']}",
        headers=auth_headers(owner["access_token"]),
    )
    assert response.status_code == 204

    response = client.get(f"/api/v1/projects/{project['id']}/members", headers=auth_headers(owner["access_token"]))
    emails = {m["user"]["email"] for m in response.json()}
    assert "member4@example.com" not in emails


def test_cannot_remove_last_owner(client: TestClient):
    owner = register_user(client, "loneowner@example.com")
    project = _create_project(client, owner["access_token"], key="LONE")

    response = client.delete(
        f"/api/v1/projects/{project['id']}/members/{owner['user']['id']}",
        headers=auth_headers(owner["access_token"]),
    )
    assert response.status_code == 409


def test_non_owner_member_cannot_manage_membership(client: TestClient):
    owner = register_user(client, "memowner5@example.com")
    member = register_user(client, "member5@example.com")
    outsider = register_user(client, "outsider5@example.com")
    project = _create_project(client, owner["access_token"], key="PERM5")

    client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": member["user"]["id"], "project_role": "MEMBER"},
        headers=auth_headers(owner["access_token"]),
    )

    # A plain MEMBER cannot add other members.
    response = client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": outsider["user"]["id"], "project_role": "MEMBER"},
        headers=auth_headers(member["access_token"]),
    )
    assert response.status_code == 403


def test_non_member_cannot_list_members(client: TestClient):
    owner = register_user(client, "memowner6@example.com")
    outsider = register_user(client, "outsider6@example.com")
    project = _create_project(client, owner["access_token"], key="PERM6")

    response = client.get(
        f"/api/v1/projects/{project['id']}/members", headers=auth_headers(outsider["access_token"])
    )
    assert response.status_code == 404
