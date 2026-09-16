import logging

from app.load_testing.queue import LoadTestQueue
from workers.load_testing.runner import LoadTestRunner

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("qahub.load_worker")


def main() -> None:
    queue = LoadTestQueue(); runner = LoadTestRunner(queue)
    logger.info("Load worker ready")
    while True:
        run_id = queue.dequeue(timeout=5)
        if run_id:
            logger.info("Starting queued load run %s", run_id)
            runner.execute(run_id)


if __name__ == "__main__":
    main()
