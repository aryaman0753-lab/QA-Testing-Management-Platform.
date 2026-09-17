"""Run with python -m workers.automation.worker."""
import logging
import time

from app.automation.queue import dequeue_run
from workers.automation.runner import process_run

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO)
    logger.info("Automation worker started")
    while True:
        try:
            run_id = dequeue_run(timeout=5)
            if run_id:
                process_run(run_id)
        except KeyboardInterrupt:
            return
        except Exception:
            logger.warning("Automation worker queue or database is temporarily unavailable")
            time.sleep(3)


if __name__ == "__main__":
    main()
