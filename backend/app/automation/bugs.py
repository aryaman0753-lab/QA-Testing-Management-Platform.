"""Create one unresolved bug for a stable final automation failure."""
import hashlib
import json

from sqlalchemy import select

from app.bugs.service import _history, _require_bug_creator
from app.database.models.automation import AutomationAuditLog, AutomationFailureLink, AutomationStepResult
from app.database.models.bug import Bug, BugPriority, BugSeverity, BugStatus
from app.database.models.project import Project


def create_failure_bugs(db, run, user) -> list:
    """Caller commits this transaction; the project lock protects counters and dedup."""
    if run.status != "FAILED":
        return []
    _require_bug_creator(db, run.project_id, user)
    project = db.scalar(select(Project).where(Project.id == run.project_id).with_for_update())
    failures = db.scalars(select(AutomationStepResult).where(
        AutomationStepResult.run_id == run.id, AutomationStepResult.is_final.is_(True),
        AutomationStepResult.status == "FAILED", AutomationStepResult.error_kind.in_(["ASSERTION", "HTTP", "NETWORK", "TIMEOUT"]),
    )).all()
    created = []
    for result in failures:
        failed_assertions = [entry for entry in result.assertions if not entry.get("passed", False)]
        identity = {
            "project": str(run.project_id), "suite": str(run.suite_id), "case": str(result.case_id),
            "step": str(result.step_id), "kind": result.error_kind, "status_code": result.status_code,
            "assertions": [{key: entry.get(key) for key in ("source", "assertion_type", "operator", "target", "expected")} for entry in failed_assertions],
        }
        fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        link = db.scalar(select(AutomationFailureLink).where(AutomationFailureLink.fingerprint == fingerprint))
        previous = db.get(Bug, link.bug_id) if link else None
        if previous and not previous.is_archived and previous.status not in {BugStatus.CLOSED, BugStatus.VERIFIED, BugStatus.DUPLICATE, BugStatus.WONT_FIX}:
            continue
        project.next_bug_number += 1
        bug = Bug(
            project_id=project.id, bug_number=project.next_bug_number,
            title=f"Automation failure: {result.case_name} / {result.step_name}"[:500],
            description=f"Automation run {run.id} failed.\nTest case: {result.case_name}\nStep: {result.step_name}\n{result.error_message or 'Final assertion failure.'}",
            steps_to_reproduce=[f"Open automation suite {run.suite_id}.", f"Run the suite and inspect case '{result.case_name}', step '{result.step_name}'."],
            expected_result="The automation step and its assertions pass.",
            actual_result=json.dumps({"error": result.error_message, "assertions": failed_assertions}, ensure_ascii=False),
            severity=BugSeverity.MEDIUM, priority=BugPriority.MEDIUM, status=BugStatus.NEW,
            reported_by=user.id, discovered_from_automation_run_id=run.id, discovered_from_automation_step_result_id=result.id,
        )
        db.add(bug)
        db.flush()
        _history(db, bug, user, "CREATED")
        if link:
            link.bug_id, link.run_id, link.case_id, link.step_id = bug.id, run.id, result.case_id, result.step_id
        else:
            db.add(AutomationFailureLink(fingerprint=fingerprint, bug_id=bug.id, run_id=run.id, case_id=result.case_id, step_id=result.step_id))
        db.add(AutomationAuditLog(project_id=run.project_id, user_id=user.id, action="BUG_AUTOMATICALLY_CREATED", resource_type="bug", resource_id=bug.id))
        created.append(bug)
    return created
