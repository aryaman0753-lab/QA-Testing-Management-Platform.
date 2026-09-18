import logging

from app.load_testing.queue import LoadTestQueue
from workers.load_testing.runner import LoadTestRunner
from workers.heartbeat import Heartbeat
from app.core.logging import configure_logging

logger = logging.getLogger("qahub.load_worker")


def main() -> None:
    configure_logging()
    queue = LoadTestQueue(); runner = LoadTestRunner(queue)
    heartbeat = Heartbeat("LOAD").start()
    logger.info("Load worker ready")
    while True:
        run_id = queue.dequeue(timeout=5)
        if run_id:
            logger.info("Starting queued load run %s", run_id)
            heartbeat.working(run_id)
            try:
                runner.execute(run_id)
                heartbeat.finished()
            except Exception:
                heartbeat.finished(failed=True)
                raise


if __name__ == "__main__":
    main()
