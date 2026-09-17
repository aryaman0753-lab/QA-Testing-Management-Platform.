"""Deployment defaults and safe, idempotent development examples."""
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.database.models.automation import (
    AutomationRun, AutomationSchedule, AutomationTestSuite,
)
from app.database.models.load_testing import LoadTest
from tests.conftest import TestingSessionLocal


@pytest.mark.parametrize("name,value", [
    ("AUTOMATION_MAX_CONCURRENT_RUNS", 0),
    ("AUTOMATION_MAX_CONCURRENT_PER_PROJECT", -1),
    ("AUTOMATION_MAX_CONCURRENT_PER_USER", 0),
    ("AUTOMATION_MAX_CASES", 0),
    ("AUTOMATION_MAX_STEPS", 0),
    ("AUTOMATION_MAX_RUN_SECONDS", 0),
    ("AUTOMATION_MAX_DELAY_SECONDS", -1),
    ("AUTOMATION_MAX_RETRIES", -1),
    ("AUTOMATION_SCHEDULER_INTERVAL_SECONDS", 0),
])
def test_invalid_automation_limits_fail_at_startup(name, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{name: value})


def test_automation_host_settings_are_normalized():
    settings = Settings(_env_file=None, AUTOMATION_ALLOWED_HOSTS=" QA.Example.Test, , api.example.test ")
    assert settings.automation_allowed_hosts_list == ["qa.example.test", "api.example.test"]


def test_development_seed_adds_only_a_draft_suite_and_is_idempotent(monkeypatch):
    from app import seed

    monkeypatch.setattr(seed, "SessionLocal", TestingSessionLocal)
    seed.seed()
    seed.seed()
    with TestingSessionLocal() as db:
        suites = db.query(AutomationTestSuite).all()
        assert len(suites) == 1
        suite = suites[0]
        assert suite.status == "DRAFT"
        assert suite.allowed_hosts == ["api.example.test"]
        assert suite.auto_create_bugs is False
        assert len(suite.cases) == 1
        assert [step.step_type for step in suite.cases[0].steps] == ["HTTP_REQUEST", "ASSERTION"]
        assert db.query(AutomationSchedule).count() == 0
        assert db.query(AutomationRun).count() == 0
        assert db.query(LoadTest).count() == 1
