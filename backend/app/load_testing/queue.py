import json
import uuid

import redis

from app.core.config import get_settings


class LoadTestQueue:
    def __init__(self, client=None):
        settings = get_settings()
        self.client = client or redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.name = settings.LOAD_TEST_QUEUE_NAME

    def enqueue(self, run_id: uuid.UUID) -> None:
        self.client.rpush(self.name, json.dumps({"run_id": str(run_id)}))

    def dequeue(self, timeout: int = 5) -> uuid.UUID | None:
        item = self.client.blpop(self.name, timeout=timeout)
        if not item:
            return None
        return uuid.UUID(json.loads(item[1])["run_id"])

    def request_stop(self, run_id: uuid.UUID) -> None:
        self.client.setex(f"qahub:load-stop:{run_id}", 3600, "1")

    def should_stop(self, run_id: uuid.UUID) -> bool:
        return bool(self.client.get(f"qahub:load-stop:{run_id}"))


def get_load_queue() -> LoadTestQueue:
    return LoadTestQueue()
