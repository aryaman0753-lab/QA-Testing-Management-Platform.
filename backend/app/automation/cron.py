"""Five-field cron expressions evaluated in an explicit IANA timezone."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

from app.common.exceptions import ValidationAppError


def next_execution(expression: str, timezone_name: str, after: datetime | None = None) -> datetime:
    try:
        if len(expression.split()) != 5 or not croniter.is_valid(expression):
            raise ValueError("Invalid cron expression")
        zone = ZoneInfo(timezone_name)
        start = after or datetime.now(timezone.utc)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        return croniter(expression, start.astimezone(zone)).get_next(datetime).astimezone(timezone.utc)
    except (ValueError, KeyError, ZoneInfoNotFoundError) as exc:
        raise ValidationAppError("Use a valid five-field cron expression and IANA timezone.") from exc
