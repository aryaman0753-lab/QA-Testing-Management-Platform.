from app.database.models.load_testing import LoadTestRun, LoadTestStatus


ALLOWED_TRANSITIONS: dict[LoadTestStatus, set[LoadTestStatus]] = {
    LoadTestStatus.QUEUED: {LoadTestStatus.STARTING, LoadTestStatus.STOPPING, LoadTestStatus.FAILED, LoadTestStatus.CANCELLED},
    LoadTestStatus.STARTING: {LoadTestStatus.RUNNING, LoadTestStatus.STOPPING, LoadTestStatus.FAILED, LoadTestStatus.CANCELLED},
    LoadTestStatus.RUNNING: {LoadTestStatus.STOPPING, LoadTestStatus.COMPLETED, LoadTestStatus.FAILED, LoadTestStatus.CANCELLED},
    LoadTestStatus.STOPPING: {LoadTestStatus.CANCELLED, LoadTestStatus.FAILED},
    LoadTestStatus.DRAFT: {LoadTestStatus.QUEUED},
    LoadTestStatus.COMPLETED: set(), LoadTestStatus.FAILED: set(), LoadTestStatus.CANCELLED: set(),
}


def transition_run(run: LoadTestRun, target: LoadTestStatus) -> None:
    if target not in ALLOWED_TRANSITIONS.get(run.status, set()):
        raise ValueError(f"Invalid load-test transition: {run.status.value} -> {target.value}")
    run.status = target
