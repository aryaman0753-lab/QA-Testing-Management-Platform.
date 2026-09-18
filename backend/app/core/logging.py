import logging
import json
import re
import sys
from datetime import datetime, timezone

from app.core.config import get_settings

settings = get_settings()


class JsonFormatter(logging.Formatter):
    _secret = re.compile(r"(?i)(password|authorization|cookie|api[_-]?key|token|secret)=([^\s,]+)")
    _json_secret = re.compile(r'(?i)(["\']?(?:password|authorization|cookie|api[_-]?key|token|secret)["\']?\s*:\s*)["\']?[^,"\'}\s]+')
    _bearer = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+")

    def format(self, record: logging.LogRecord) -> str:
        from app.core.observability import request_id
        message = self._secret.sub(r"\1=[REDACTED]", record.getMessage())
        message = self._json_secret.sub(r"\1[REDACTED]", message)
        message = self._bearer.sub(r"\1[REDACTED]", message)
        value = {"timestamp": datetime.now(timezone.utc).isoformat(), "level": record.levelname, "logger": record.name, "request_id": request_id(), "message": message}
        for field in ("user_id", "project_id", "job_id", "run_id", "duration_ms", "status", "method", "path"):
            if hasattr(record, field):
                value[field] = getattr(record, field)
        if record.exc_info:
            value["exception"] = self.formatException(record.exc_info)
        return json.dumps(value, ensure_ascii=False)


def configure_logging() -> None:
    level = logging.DEBUG if settings.DEBUG else logging.INFO
    handler = logging.StreamHandler(sys.stdout); handler.setFormatter(JsonFormatter())
    root = logging.getLogger(); root.handlers.clear(); root.addHandler(handler); root.setLevel(level)
    # Quiet noisy third-party loggers unless we're debugging.
    if not settings.DEBUG:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
