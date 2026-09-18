"""Run with python -m workers.automation.worker."""
import logging
import time

from app.automation.queue import dequeue_run
from workers.automation.runner import process_run
from workers.heartbeat import Heartbeat
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


def main():
    configure_logging()
    logger.info("Automation worker started")
    heartbeat = Heartbeat("AUTOMATION").start()
    while True:
        try:
            run_id = dequeue_run(timeout=5)
            if run_id:
                heartbeat.working(run_id)
                process_run(run_id)
                heartbeat.finished()
        except KeyboardInterrupt:
            heartbeat.stop()
            return
        except Exception:
            heartbeat.finished(failed=True)
            logger.warning("Automation worker queue or database is temporarily unavailable")
            time.sleep(3)


if __name__ == "__main__":
    main()
