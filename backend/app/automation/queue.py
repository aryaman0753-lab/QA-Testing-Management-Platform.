"""Queue messages contain run identifiers only, never request credentials."""
import uuid

import redis

from app.core.config import get_settings


def _redis():
    return redis.Redis.from_url(get_settings().REDIS_URL, decode_responses=True, socket_connect_timeout=3, socket_timeout=10)


def enqueue_run(run_id: uuid.UUID | str) -> None:
    _redis().rpush(get_settings().AUTOMATION_QUEUE_NAME, str(run_id))


def dequeue_run(timeout: int = 5) -> uuid.UUID | None:
    message = _redis().blpop(get_settings().AUTOMATION_QUEUE_NAME, timeout=timeout)
    if message is None:
        return None
    try:
        return uuid.UUID(message[1])
    except (ValueError, TypeError):
        return None


def request_stop(run_id: uuid.UUID | str) -> None:
    _redis().setex(f"{get_settings().AUTOMATION_QUEUE_NAME}:stop:{run_id}", 86400, "1")


def stop_requested(run_id: uuid.UUID | str) -> bool:
    return bool(_redis().get(f"{get_settings().AUTOMATION_QUEUE_NAME}:stop:{run_id}"))
