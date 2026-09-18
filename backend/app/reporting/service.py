import csv
import io
import json
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.exceptions import NotFoundError, ValidationAppError
from app.database.models.api_testing import ApiTestResult, ApiTestRun
from app.database.models.automation import AutomationRun, AutomationSchedule, AutomationStepResult, AutomationTestSuite
from app.database.models.bug import Bug, BugSeverity, BugStatus
from app.database.models.load_testing import LoadTestRun, LoadTestStatus
from app.database.models.operations import CiTestExecution
from app.projects.service import get_project_for_read

TERMINAL_AUTOMATION = {"PASSED", "FAILED", "CANCELLED"}
SECRET_KEYS = {"password", "secret", "token", "authorization", "cookie", "api_key", "api-key"}


def _window(date_from: date | None, date_to: date | None):
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc) if date_from else datetime.now(timezone.utc) - timedelta(days=30)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc) if date_to else datetime.now(timezone.utc) + timedelta(seconds=1)
    if start >= end: raise ValidationAppError("The report start date must be before the end date.")
    return start, end


def _rate(value: int, total: int) -> float:
    return round((value / total * 100) if total else 0, 2)


def build_report(db: Session, project_id: uuid.UUID, user, environment_id=None, date_from=None, date_to=None):
    project = get_project_for_read(db, project_id, user); start, end = _window(date_from, date_to)
    env = [AutomationRun.environment_id == environment_id] if environment_id else []
    automation_runs = list(db.scalars(select(AutomationRun).where(AutomationRun.project_id == project_id, AutomationRun.created_at >= start, AutomationRun.created_at < end, *env).order_by(AutomationRun.created_at)))
    api_conditions = [ApiTestRun.project_id == project_id, ApiTestRun.created_at >= start, ApiTestRun.created_at < end]
    if environment_id: api_conditions.append(ApiTestRun.environment_id == environment_id)
    api_runs = list(db.scalars(select(ApiTestRun).where(*api_conditions)))
    api_ids = [row.id for row in api_runs]
    api_results = list(db.scalars(select(ApiTestResult).where(ApiTestResult.test_run_id.in_(api_ids)))) if api_ids else []
    load_conditions = [LoadTestRun.project_id == project_id, LoadTestRun.created_at >= start, LoadTestRun.created_at < end]
    if environment_id: load_conditions.append(LoadTestRun.environment_id == environment_id)
    load_runs = list(db.scalars(select(LoadTestRun).where(*load_conditions).order_by(LoadTestRun.created_at)))
    bugs = list(db.scalars(select(Bug).where(Bug.project_id == project_id, Bug.is_archived.is_(False))))
    final_steps = []
    automation_ids = [row.id for row in automation_runs]
    if automation_ids:
        final_steps = list(db.scalars(select(AutomationStepResult).where(AutomationStepResult.run_id.in_(automation_ids), AutomationStepResult.is_final.is_(True))))
    failed_steps = [row for row in final_steps if row.status == "FAILED"]
    flaky = flaky_tests(db, project_id, user, limit=10, authorize=False)
    endpoint_failures = Counter(result.request_name for result in api_results if getattr(result.status, "value", result.status) in {"FAIL", "ERROR", "TIMEOUT"})
    status_counts = Counter(row.status for row in automation_runs)
    completed_load = [row for row in load_runs if row.status == LoadTestStatus.COMPLETED]
    thresholds = [{"run_id": str(row.id), "run_key": row.run_key, "violations": [item for item in row.threshold_results if not item.get("passed", True)]} for row in completed_load if any(not item.get("passed", True) for item in row.threshold_results)]
    open_statuses = {BugStatus.NEW, BugStatus.ASSIGNED, BugStatus.IN_PROGRESS, BugStatus.REOPENED, BugStatus.QA_VERIFICATION}
    resolved_statuses = {BugStatus.FIXED, BugStatus.VERIFIED, BugStatus.CLOSED}
    automation_total = len(automation_runs); automation_passed = status_counts["PASSED"]; automation_failed = status_counts["FAILED"]
    return {
        "project": {"id": str(project.id), "key": project.key, "name": project.name},
        "environment_id": str(environment_id) if environment_id else None,
        "date_range": {"from": start.isoformat(), "to": end.isoformat()},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "test_execution": {"total_runs": automation_total, "passed": automation_passed, "failed": automation_failed, "skipped": sum(row.skipped_cases for row in automation_runs), "pass_rate": _rate(automation_passed, automation_total), "failure_rate": _rate(automation_failed, automation_total)},
        "api_testing": {"runs": len(api_runs), "requests_executed": len(api_results), "failures": sum(endpoint_failures.values()), "average_response_time_ms": round(sum(row.response_time_ms for row in api_results) / len(api_results), 2) if api_results else 0, "endpoint_failures": [{"endpoint": key, "failures": value} for key, value in endpoint_failures.most_common(10)]},
        "automation": {"suite_execution_trends": [{"date": row.created_at.date().isoformat(), "status": row.status, "duration_ms": row.duration_ms} for row in automation_runs[-100:]], "flaky_tests": flaky, "frequent_failures": [{"test": f"{key[0]} / {key[1]}", "count": value} for key, value in Counter((row.case_name, row.step_name) for row in failed_steps).most_common(10)], "longest_tests": [{"test": f"{row.case_name} / {row.step_name}", "response_time_ms": row.response_time_ms} for row in sorted((x for x in final_steps if x.response_time_ms is not None), key=lambda x: x.response_time_ms, reverse=True)[:10]]},
        "load_testing": {"runs": len(load_runs), "rps": round(sum(row.requests_per_second for row in completed_load) / len(completed_load), 2) if completed_load else 0, "p95_ms": max((row.p95_response_time for row in completed_load), default=0), "p99_ms": max((row.p99_response_time for row in completed_load), default=0), "failure_rate": round(sum(row.failure_rate for row in completed_load) / len(completed_load), 2) if completed_load else 0, "peak_users": max((row.virtual_users for row in load_runs), default=0), "threshold_violations": thresholds},
        "bugs": {"open": sum(row.status in open_statuses for row in bugs), "critical": sum(row.severity == BugSeverity.CRITICAL and row.status in open_statuses for row in bugs), "resolved": sum(row.status in resolved_statuses for row in bugs), "automated": sum(bool(row.discovered_from_test_result_id or row.discovered_from_load_test_run_id or row.discovered_from_automation_run_id) for row in bugs), "links": [{"id": str(row.id), "key": row.bug_key, "title": row.title, "status": row.status.value} for row in bugs[:100]]},
    }


def compare_automation_runs(db: Session, project_id, run_a_id, run_b_id, user):
    get_project_for_read(db, project_id, user)
    rows = [db.get(AutomationRun, item) for item in (run_a_id, run_b_id)]
    if any(row is None or row.project_id != project_id for row in rows): raise NotFoundError("Automation run not found in this project.")
    def summary(run):
        final = [item for item in run.results if item.is_final]
        failures = {f"{item.case_name} / {item.step_name}" for item in final if item.status == "FAILED"}
        times = [item.response_time_ms for item in final if item.response_time_ms is not None]
        return {"run_id": str(run.id), "status": run.status, "total_tests": run.total_cases, "passed_tests": run.passed_cases, "failed_tests": run.failed_cases, "duration_ms": run.duration_ms, "average_response_time_ms": round(sum(times) / len(times), 2) if times else 0, "failures": sorted(failures)}
    a, b = summary(rows[0]), summary(rows[1])
    return {"run_a": a, "run_b": b, "differences": {"total_tests": b["total_tests"] - a["total_tests"], "passed_tests": b["passed_tests"] - a["passed_tests"], "failed_tests": b["failed_tests"] - a["failed_tests"], "duration_ms": round(b["duration_ms"] - a["duration_ms"], 2), "average_response_time_ms": round(b["average_response_time_ms"] - a["average_response_time_ms"], 2), "new_failures": sorted(set(b["failures"]) - set(a["failures"])), "resolved_failures": sorted(set(a["failures"]) - set(b["failures"]))}}


def flaky_tests(db: Session, project_id, user, limit=100, authorize=True):
    if authorize: get_project_for_read(db, project_id, user)
    rows = list(db.scalars(select(AutomationStepResult).join(AutomationRun, AutomationRun.id == AutomationStepResult.run_id).where(AutomationRun.project_id == project_id, AutomationStepResult.is_final.is_(True), AutomationStepResult.step_id.is_not(None)).order_by(AutomationStepResult.started_at.desc()).limit(5000)))
    grouped = defaultdict(list)
    for row in rows: grouped[row.step_id].append(row)
    candidates = []
    for step_id, history in grouped.items():
        history = list(reversed(history[:20])); statuses = [row.status for row in history]
        passed, failed = statuses.count("PASSED"), statuses.count("FAILED")
        alternations = sum(left != right for left, right in zip(statuses, statuses[1:]) if left in {"PASSED", "FAILED"} and right in {"PASSED", "FAILED"})
        if len(history) >= 5 and passed and failed and alternations >= 2:
            last = history[-1]
            candidates.append({"classification": "FLAKY_CANDIDATE", "step_id": str(step_id), "case_name": last.case_name, "step_name": last.step_name, "executions": len(history), "pass_count": passed, "fail_count": failed, "failure_percentage": _rate(failed, passed + failed), "recent_history": [{"run_id": str(row.run_id), "status": row.status, "executed_at": row.started_at.isoformat()} for row in history]})
    return sorted(candidates, key=lambda row: (row["failure_percentage"], row["executions"]), reverse=True)[:limit]


def project_dashboard(db: Session, project_id, user):
    get_project_for_read(db, project_id, user)
    bugs = {getattr(status, "value", status): count for status, count in db.execute(select(Bug.status, func.count(Bug.id)).where(Bug.project_id == project_id, Bug.is_archived.is_(False)).group_by(Bug.status))}
    api_total = db.scalar(select(func.count(ApiTestRun.id)).where(ApiTestRun.project_id == project_id)) or 0
    api_passed = db.scalar(select(func.count(ApiTestRun.id)).where(ApiTestRun.project_id == project_id, ApiTestRun.status == "PASS")) or 0
    auto_recent = list(db.scalars(select(AutomationRun).where(AutomationRun.project_id == project_id).order_by(AutomationRun.created_at.desc()).limit(5)))
    load_recent = list(db.scalars(select(LoadTestRun).where(LoadTestRun.project_id == project_id).order_by(LoadTestRun.created_at.desc()).limit(5)))
    ci_recent = list(db.execute(select(CiTestExecution, AutomationRun).join(AutomationRun, AutomationRun.id == CiTestExecution.automation_run_id).where(CiTestExecution.project_id == project_id).order_by(CiTestExecution.created_at.desc()).limit(5)))
    return {
        "bugs": {"open": bugs.get("NEW", 0) + bugs.get("ASSIGNED", 0), "in_progress": bugs.get("IN_PROGRESS", 0), "resolved": bugs.get("CLOSED", 0) + bugs.get("VERIFIED", 0) + bugs.get("FIXED", 0), "reopened": bugs.get("REOPENED", 0)},
        "api_tests": {"total_runs": api_total, "pass_rate": _rate(api_passed, api_total), "failures": api_total - api_passed},
        "automation": {"scheduled_suites": db.scalar(select(func.count(AutomationSchedule.id)).where(AutomationSchedule.project_id == project_id, AutomationSchedule.enabled.is_(True))) or 0, "failed_suites": sum(row.status == "FAILED" for row in auto_recent), "recent_runs": [{"id": str(row.id), "status": row.status, "suite_id": str(row.suite_id), "created_at": row.created_at.isoformat()} for row in auto_recent]},
        "load_testing": {"threshold_violations": sum(any(not item.get("passed", True) for item in row.threshold_results) for row in load_recent), "recent_runs": [{"id": str(row.id), "status": row.status.value, "result_status": row.result_status.value if row.result_status else None, "rps": row.requests_per_second, "p95_ms": row.p95_response_time} for row in load_recent]},
        "ci_cd": {"failed_pipelines": sum(run.status == "FAILED" for _, run in ci_recent), "recent_executions": [{"run_id": str(run.id), "status": run.status, "provider": ci.provider, "commit_sha": ci.commit_sha, "branch": ci.branch, "build_number": ci.build_number, "created_at": ci.created_at.isoformat()} for ci, run in ci_recent]},
    }


def _clean(value):
    if isinstance(value, dict): return {key: _clean(item) for key, item in value.items() if key.lower() not in SECRET_KEYS and not any(word in key.lower() for word in ("password", "secret", "token"))}
    if isinstance(value, list): return [_clean(item) for item in value]
    return value


def report_csv(report: dict) -> bytes:
    stream = io.StringIO(); writer = csv.writer(stream); writer.writerow(["section", "metric", "value"])
    for section, values in report.items():
        if isinstance(values, dict):
            for key, value in values.items(): writer.writerow([section, key, json.dumps(value, default=str) if isinstance(value, (dict, list)) else value])
        else: writer.writerow(["report", section, values])
    return stream.getvalue().encode("utf-8")


def report_pdf(report: dict) -> bytes:
    """Small dependency-free text PDF; intentionally excludes raw requests and secrets."""
    lines = ["QAHub QA Report", f"Project: {report['project']['name']} ({report['project']['key']})", f"Range: {report['date_range']['from']} to {report['date_range']['to']}"]
    for section in ("test_execution", "api_testing", "load_testing", "bugs"):
        lines.append(section.replace("_", " ").title())
        for key, value in report[section].items():
            if not isinstance(value, (dict, list)): lines.append(f"  {key.replace('_', ' ')}: {value}")
    def esc(text): return str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")[:110]
    content = "BT /F1 10 Tf 50 780 Td 14 TL " + " ".join(f"({esc(line)}) Tj T*" for line in lines[:48]) + " ET"
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>", "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", f"<< /Length {len(content.encode('latin-1', 'replace'))} >>\nstream\n{content}\nendstream"]
    output = b"%PDF-1.4\n"; offsets = [0]
    for index, obj in enumerate(objects, 1): offsets.append(len(output)); output += f"{index} 0 obj\n{obj}\nendobj\n".encode("latin-1", "replace")
    xref = len(output); output += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode()
    output += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return output + f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


def export_report(report: dict, format: str):
    clean = _clean(report)
    if format == "json": return json.dumps(clean, indent=2, default=str).encode(), "application/json", "json"
    if format == "csv": return report_csv(clean), "text/csv; charset=utf-8", "csv"
    if format == "pdf": return report_pdf(clean), "application/pdf", "pdf"
    raise ValidationAppError("Report format must be json, csv, or pdf.")
