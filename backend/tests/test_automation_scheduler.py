from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.automation.cron import next_execution
from app.common.exceptions import ValidationAppError
from app.database.models.automation import AutomationRun, AutomationSchedule, AutomationTestSuite
from tests.conftest import TestingSessionLocal
from tests.test_automation_engine import provision_workflow


def test_cron_timezone_validation_and_next_execution():
    now = datetime(2026, 1, 1, 14, 1, tzinfo=timezone.utc)
    assert next_execution("*/5 * * * *", "UTC", now) == now.replace(minute=5)
    assert next_execution("0 9 * * 1-5", "America/New_York", now) == datetime(2026, 1, 2, 14, tzinfo=timezone.utc)
    for expr, zone in (("not cron", "UTC"), ("* * * * * *", "UTC"), ("0 0 * * *", "Not/AZone")):
        with pytest.raises(ValidationAppError):
            next_execution(expr, zone, now)


def make_due(client, monkeypatch):
    run_id, suite_id, user_id = provision_workflow(client, monkeypatch)
    now = datetime.now(timezone.utc)
    with TestingSessionLocal() as db:
        run = db.get(AutomationRun, run_id)
        run.status = "PASSED"
        suite = db.get(AutomationTestSuite, suite_id)
        schedule = AutomationSchedule(suite_id=suite.id, project_id=suite.project_id, created_by=user_id, cron_expression="*/5 * * * *", timezone="UTC", enabled=True, next_run_at=now-timedelta(seconds=1))
        db.add(schedule)
        db.commit()
        return schedule.id, suite_id, now


def test_scheduler_queues_once_and_skips_suite_overlap(client, monkeypatch):
    from workers.automation.scheduler import scheduler_tick
    schedule_id, suite_id, now = make_due(client, monkeypatch)
    queued = []
    assert len(scheduler_tick(TestingSessionLocal, queued.append, now)) == 1
    assert not scheduler_tick(TestingSessionLocal, queued.append, now)
    with TestingSessionLocal() as db:
        schedule = db.get(AutomationSchedule, schedule_id)
        assert schedule.last_run_at is not None and schedule.last_error is None
        schedule.next_run_at = now - timedelta(seconds=1)
        db.commit()
    assert not scheduler_tick(TestingSessionLocal, queued.append, now)
    assert len(queued) == 1
    with TestingSessionLocal() as db:
        assert "still active" in db.get(AutomationSchedule, schedule_id).last_error


def test_scheduler_records_queue_errors_disables_archived_suites_and_recovers_stale_runs(client, monkeypatch):
    from workers.automation.scheduler import recover_stale_runs, scheduler_tick
    schedule_id, suite_id, now = make_due(client, monkeypatch)
    def unavailable(run_id):
        raise ConnectionError("do not persist credentials from errors")
    assert not scheduler_tick(TestingSessionLocal, unavailable, now)
    with TestingSessionLocal() as db:
        schedule = db.get(AutomationSchedule, schedule_id)
        assert schedule.last_error == "The automation queue is unavailable."
        failed = db.scalar(select(AutomationRun).where(AutomationRun.schedule_id == schedule_id))
        assert failed.status == "FAILED"
        failed.status, failed.heartbeat_at = "RUNNING", now - timedelta(hours=1)
        db.commit()
        assert recover_stale_runs(db, now) == 1
        db.get(AutomationTestSuite, suite_id).status = "ARCHIVED"
        schedule.next_run_at = now - timedelta(seconds=1)
        db.commit()
    assert not scheduler_tick(TestingSessionLocal, unavailable, now)
    with TestingSessionLocal() as db:
        assert not db.get(AutomationSchedule, schedule_id).enabled
