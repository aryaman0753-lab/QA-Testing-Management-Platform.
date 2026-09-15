"""Test fixtures.

Tests run against an isolated in-memory SQLite database (via StaticPool so
all connections share the same in-memory DB for the life of the process).
This never touches a developer's local Postgres database - a deliberate
strategy so `pytest` is safe to run anytime without Docker or a running
Postgres instance, per the "don't destroy development data" requirement.
"""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import get_db
from app.database.models import Base
from app.main import app

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def _fresh_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def register_user(client: TestClient, email: str, password: str = "Password123", full_name: str = "Test User") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"full_name": full_name, "email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_admin(email: str) -> None:
    """Promote a registered user to ADMIN directly via the DB (no admin-creation
    endpoint exists by design in Phase 1 - the first admin is provisioned out of
    band, e.g. via the seed script or a manual DB update)."""
    from app.database.models.user import User, UserRole

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        user.role = UserRole.ADMIN
        db.commit()
    finally:
        db.close()
