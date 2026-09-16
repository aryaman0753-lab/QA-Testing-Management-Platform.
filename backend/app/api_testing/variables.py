import re

from app.api_testing.secrets import MASK, is_sensitive_name
from app.common.exceptions import ValidationAppError

VARIABLE_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class VariableResolver:
    """Resolve with precedence runtime > extracted > environment."""

    def __init__(self, environment: dict[str, str] | None = None, extracted: dict[str, str] | None = None, runtime: dict[str, str] | None = None):
        self.values = {**(environment or {}), **(extracted or {}), **(runtime or {})}

    def resolve(self, value: str) -> str:
        missing: set[str] = set()

        def replace(match: re.Match) -> str:
            name = match.group(1)
            if name not in self.values:
                missing.add(name)
                return match.group(0)
            return str(self.values[name])

        result = VARIABLE_PATTERN.sub(replace, value)
        if missing:
            raise ValidationAppError(f"Undefined variable(s): {', '.join(sorted(missing))}.")
        return result

    def resolve_items(self, items: list[dict]) -> list[tuple[str, str]]:
        return [
            (self.resolve(str(item.get("key", ""))), self.resolve(str(item.get("value", ""))))
            for item in items if item.get("enabled", True) and str(item.get("key", "")).strip()
        ]

    def redact_sensitive_values(self, value: str) -> str:
        """Remove credential-like variable values before a resolved URL is persisted."""
        redacted = value
        for name, item in self.values.items():
            if item and is_sensitive_name(name):
                redacted = redacted.replace(str(item), MASK)
        return redacted
