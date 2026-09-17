"""Per-run variables and conservative persistence redaction."""
import json
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.api_testing.secrets import MASK, is_sensitive_name
from app.common.exceptions import ValidationAppError

VARIABLE = re.compile(r"\$\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}|\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class AutomationVariables:
    def __init__(self, environment=None, runtime=None, secret_names=None):
        self.environment = dict(environment or {})
        self.runtime = dict(runtime or {})
        self.extracted: dict[str, str] = {}
        self.secrets: set[str] = set()
        for name, value in {**self.environment, **self.runtime}.items():
            if is_sensitive_name(name) or name in (secret_names or []):
                self.remember_secret(value)

    @property
    def values(self):
        return {**self.environment, **self.extracted, **self.runtime}

    def resolve(self, value: Any):
        if isinstance(value, dict):
            return {key: self.resolve(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.resolve(item) for item in value]
        if not isinstance(value, str):
            return value

        def replace(match):
            name = match.group(1) or match.group(2)
            if name not in self.values:
                raise ValidationAppError(f"Undefined variable: {name}.")
            return str(self.values[name])

        return VARIABLE.sub(replace, value)

    def assign(self, name: str, value: Any, is_secret=False):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,99}", name):
            raise ValidationAppError("Invalid variable name.")
        text = value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))
        self.extracted[name] = text
        # All extracted values are confidential in persisted execution results.
        self.remember_secret(text)

    def remember_secret(self, value):
        if value is not None and str(value):
            self.secrets.add(str(value))

    def discover_response_secrets(self, body: str, headers: dict):
        for name, value in headers.items():
            if is_sensitive_name(name):
                self.remember_secret(value)
                if str(value).lower().startswith("bearer "):
                    self.remember_secret(str(value)[7:])
        try:
            value = json.loads(body)
        except (ValueError, TypeError):
            return

        def walk(item):
            if isinstance(item, dict):
                for key, child in item.items():
                    if is_sensitive_name(key) and not isinstance(child, (dict, list)):
                        self.remember_secret(child)
                    walk(child)
            elif isinstance(item, list):
                for child in item:
                    walk(child)
        walk(value)

    def sanitize(self, value: Any):
        if isinstance(value, dict):
            return {key: MASK if is_sensitive_name(key) and item is not None else self.sanitize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.sanitize(item) for item in value]
        if not isinstance(value, str):
            return value
        for secret in sorted(self.secrets, key=len, reverse=True):
            if value == secret:
                return MASK
            if len(secret) >= 4:
                value = value.replace(secret, MASK)
        return value

    def sanitize_url(self, value: str) -> str:
        """Keep useful request routing metadata without retaining variable values."""
        try:
            parts = urlsplit(value)
            path = parts.path
            for secret in sorted(self.secrets, key=len, reverse=True):
                # URL paths commonly contain short numeric IDs; unlike free-form
                # messages, every discovered value must be removed here.
                if secret:
                    path = path.replace(secret, MASK)
            return urlunsplit((parts.scheme, parts.netloc, path, "", ""))
        except (TypeError, ValueError):
            return MASK
