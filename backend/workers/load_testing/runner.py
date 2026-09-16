import asyncio
import logging
import socket
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import delete

from app.api_testing.engine import ApiExecutionService
from app.api_testing.secrets import reveal_key_values
from app.api_testing.variables import VariableResolver
from app.database.database import SessionLocal
from app.database.models.load_testing import (
    LoadTestEndpointMetric, LoadTestError, LoadTestMetric, LoadTestResultStatus,
    LoadTestRun, LoadTestStatus,
)
from app.load_testing.queue import LoadTestQueue
from app.load_testing.security import validate_load_target
from app.load_testing.service import _effective_request, _environment_values
from app.load_testing.state import transition_run
from app.load_testing.thresholds import Summary, evaluate_thresholds
from workers.load_testing.locust_engine import EngineConfig, EngineResult, LocustLoadTestEngine, MetricSnapshot

logger = logging.getLogger("qahub.load_worker.runner")


def _now(): return datetime.now(timezone.utc)


class LoadTestRunner:
    def __init__(self, queue: LoadTestQueue | None = None, engine_factory=LocustLoadTestEngine):
        self.queue = queue or LoadTestQueue(); self.engine_factory = engine_factory

    def _config(self, run: LoadTestRun) -> EngineConfig:
        item = run.load_test; source = _effective_request(item); resolver = VariableResolver(_environment_values(item.environment))
        if not item.api_request:
            source = SimpleNamespace(method=item.request_method, url=item.target_url, headers=item.headers, query_parameters=item.query_parameters,
                body=item.body, body_type=item.body_type, authentication_type=item.authentication_type, authentication_config=item.authentication_config)
        url = resolver.resolve(source.url if item.api_request else item.target_url)
        pinned = asyncio.run(validate_load_target(url, run.load_test.project.load_allowed_hosts, run.load_test.project.load_allowlist_enabled))
        headers = ApiExecutionService._build_headers(source, resolver); params = resolver.resolve_items(reveal_key_values(source.query_parameters))
        request_kwargs = ApiExecutionService._build_body(source, resolver); params.extend(ApiExecutionService._apply_auth(source, resolver, headers))
        headers = {key: value for key, value in headers.items() if key.lower() != "host"}
        headers["Host"] = pinned.host_header
        return EngineConfig(url=pinned.network_url, method=(source.method if item.api_request else item.request_method).value, headers=headers, params=params,
            request_kwargs=request_kwargs, users=run.virtual_users, spawn_rate=run.spawn_rate, duration_seconds=run.duration_seconds,
            timeout_seconds=item.timeout_seconds, target_rps=item.target_rps, tls_hostname=pinned.sni_hostname)

    def execute(self, run_id: uuid.UUID) -> None:
        db = SessionLocal()
        try:
            run = db.get(LoadTestRun, run_id)
            if run is None or run.status not in {LoadTestStatus.QUEUED, LoadTestStatus.STOPPING}: return
            if run.status == LoadTestStatus.STOPPING or self.queue.should_stop(run.id):
                self._cancel(db, run); logger.info("load_run_cancelled run_id=%s before_start=true", run.id); return
            transition_run(run, LoadTestStatus.STARTING); run.worker_id = socket.gethostname(); run.heartbeat_at = _now(); db.commit()
            logger.info("load_run_starting run_id=%s worker_id=%s", run.id, run.worker_id)
            config = self._config(run); transition_run(run, LoadTestStatus.RUNNING); run.started_at = _now(); run.heartbeat_at = _now(); db.commit()
            logger.info("locust_started run_id=%s users=%s duration_seconds=%s", run.id, run.virtual_users, run.duration_seconds)
            engine = self.engine_factory()
            def metric(snapshot: MetricSnapshot):
                run.heartbeat_at = _now(); db.add(LoadTestMetric(run_id=run.id, **asdict(snapshot))); db.commit()
            result = engine.start(config, lambda: self.queue.should_stop(run.id), metric)
            self._finish(db, run, result)
            logger.info("load_run_%s run_id=%s total_requests=%s", "cancelled" if result.cancelled else "completed", run.id, result.summary.total_requests)
        except Exception:
            db.rollback(); run = db.get(LoadTestRun, run_id)
            if run:
                if run.status in {LoadTestStatus.QUEUED, LoadTestStatus.STARTING, LoadTestStatus.RUNNING, LoadTestStatus.STOPPING}:
                    transition_run(run, LoadTestStatus.FAILED)
                run.result_status = LoadTestResultStatus.ERROR; run.completed_at = _now(); run.error_message = "The isolated load worker failed while executing this run."; db.commit()
            logger.error("load_run_failed run_id=%s", run_id)
        finally: db.close()

    @staticmethod
    def _cancel(db, run):
        transition_run(run, LoadTestStatus.CANCELLED); run.result_status = LoadTestResultStatus.CANCELLED; run.completed_at = _now(); db.commit()

    def _finish(self, db, run: LoadTestRun, result: EngineResult):
        summary = result.summary; run.total_requests = summary.total_requests; run.failed_requests = summary.failed_requests
        run.successful_requests = summary.total_requests - summary.failed_requests; run.requests_per_second = summary.requests_per_second
        run.failure_rate = summary.failure_rate; run.avg_response_time = summary.avg_response_time; run.min_response_time = result.min_response_time
        run.max_response_time = result.max_response_time; run.median_response_time = summary.p50; run.p50_response_time = summary.p50
        run.p75_response_time = result.p75; run.p90_response_time = summary.p90; run.p95_response_time = summary.p95; run.p99_response_time = summary.p99
        run.status_distribution = result.status_distribution; run.error_summary = {row.error_type: row.count for row in result.errors}
        db.execute(delete(LoadTestEndpointMetric).where(LoadTestEndpointMetric.run_id == run.id)); db.execute(delete(LoadTestError).where(LoadTestError.run_id == run.id))
        db.add_all(LoadTestEndpointMetric(run_id=run.id, **asdict(row)) for row in result.endpoints)
        db.add_all(LoadTestError(run_id=run.id, **asdict(row)) for row in result.errors)
        if result.cancelled: self._cancel(db, run); return
        threshold_results = evaluate_thresholds(Summary(total_requests=summary.total_requests, failed_requests=summary.failed_requests,
            requests_per_second=summary.requests_per_second, failure_rate=summary.failure_rate, avg_response_time=summary.avg_response_time,
            p95_response_time=summary.p95, p99_response_time=summary.p99), run.load_test.thresholds)
        run.threshold_results = threshold_results; transition_run(run, LoadTestStatus.COMPLETED); run.completed_at = _now()
        run.result_status = LoadTestResultStatus.THRESHOLD_EXCEEDED if any(not row["passed"] for row in threshold_results) else (LoadTestResultStatus.FAIL if summary.failed_requests and summary.total_requests == summary.failed_requests else LoadTestResultStatus.PASS)
        db.commit()
