from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_user


def test_registration_works(client: TestClient):
    data = register_user(client, "john@example.com")
    assert data["user"]["email"] == "john@example.com"
    assert data["user"]["role"] == "QA_ENGINEER"
    assert "access_token" in data
    assert "password" not in data["user"]


def test_duplicate_email_rejected(client: TestClient):
    register_user(client, "dup@example.com")
    response = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Dup User", "email": "dup@example.com", "password": "Password123"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert response.json()["error"]["request_id"]


def test_email_is_normalized(client: TestClient):
    register_user(client, "Mixed.Case@Example.com")
    response = client.post(
        "/api/v1/auth/login", json={"email": "mixed.case@example.com", "password": "Password123"}
    )
    assert response.status_code == 200


def test_weak_password_rejected(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Weak", "email": "weak@example.com", "password": "short"},
    )
    assert response.status_code == 422


def test_login_works(client: TestClient):
    register_user(client, "login@example.com", password="Password123")
    response = client.post(
        "/api/v1/auth/login", json={"email": "login@example.com", "password": "Password123"}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_incorrect_password_rejected(client: TestClient):
    register_user(client, "wrongpw@example.com", password="Password123")
    response = client.post(
        "/api/v1/auth/login", json={"email": "wrongpw@example.com", "password": "WrongPassword1"}
    )
    assert response.status_code == 401


def test_protected_endpoint_requires_authentication(client: TestClient):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_protected_endpoint_rejects_garbage_token(client: TestClient):
    response = client.get("/api/v1/auth/me", headers=auth_headers("not-a-real-token"))
    assert response.status_code == 401


def test_current_user_works(client: TestClient):
    data = register_user(client, "me@example.com")
    response = client.get("/api/v1/auth/me", headers=auth_headers(data["access_token"]))
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"
