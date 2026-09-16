import threading
import time
import uuid
from collections import defaultdict, deque

from app.common.exceptions import AppError
from app.core.config import get_settings


class RateLimitError(AppError):
    status_code = 429
    detail = "API execution rate limit exceeded. Try again shortly."


class ExecutionRateLimiter:
    def __init__(self):
        self._events: dict[uuid.UUID, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, user_id: uuid.UUID) -> None:
        now = time.monotonic()
        limit = get_settings().API_EXECUTIONS_PER_MINUTE
        with self._lock:
            events = self._events[user_id]
            while events and events[0] <= now - 60:
                events.popleft()
            if len(events) >= limit:
                raise RateLimitError()
            events.append(now)


execution_rate_limiter = ExecutionRateLimiter()
