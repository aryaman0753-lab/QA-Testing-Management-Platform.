"""Durable worker heartbeat updated from a small daemon thread."""
import os
import socket
import threading
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.database.database import SessionLocal
from app.database.models.operations import WorkerHeartbeat


class Heartbeat:
    def __init__(self, worker_type: str):
        self.worker_type = worker_type
        self.worker_id = f"{worker_type}:{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        self.status = "IDLE"
        self.current_job: str | None = None
        self.completed_jobs = 0
        self.failed_jobs = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _write(self) -> None:
        try:
            with SessionLocal() as db:
                row = db.scalar(select(WorkerHeartbeat).where(WorkerHeartbeat.worker_id == self.worker_id))
                if row is None:
                    row = WorkerHeartbeat(worker_id=self.worker_id, worker_type=self.worker_type)
                    db.add(row)
                row.status = self.status
                row.current_job = self.current_job
                row.last_heartbeat = datetime.now(timezone.utc)
                row.completed_jobs = self.completed_jobs
                row.failed_jobs = self.failed_jobs
                db.commit()
        except Exception:
            pass  # A monitoring write must never terminate an execution worker.

    def _loop(self) -> None:
        while not self._stop.wait(get_settings().WORKER_HEARTBEAT_INTERVAL_SECONDS):
            self._write()

    def start(self) -> "Heartbeat":
        self._write()
        self._thread = threading.Thread(target=self._loop, daemon=True, name=f"heartbeat-{self.worker_type}")
        self._thread.start()
        return self

    def working(self, job_id: object) -> None:
        self.status, self.current_job = "BUSY", str(job_id)
        self._write()

    def finished(self, failed: bool = False, completed: int = 1) -> None:
        if failed: self.failed_jobs += 1
        else: self.completed_jobs += completed
        self.status, self.current_job = "IDLE", None
        self._write()

    def stop(self) -> None:
        self.status, self.current_job = "STOPPING", None
        self._stop.set(); self._write()
