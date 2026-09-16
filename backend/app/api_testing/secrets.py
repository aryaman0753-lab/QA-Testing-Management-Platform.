"""Encryption and masking for API-testing credentials stored in JSON columns."""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

MASK = "********"
PREFIX = "enc:"
SENSITIVE_NAMES = {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key", "api-key"}


def _fernet() -> Fernet:
    settings = get_settings()
    raw = settings.SECRET_ENCRYPTION_KEY or settings.JWT_SECRET_KEY
    key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode("utf-8")).digest())
    return Fernet(key)


def encrypt(value: str) -> str:
    if value.startswith(PREFIX):
        return value
    return PREFIX + _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(value: str) -> str:
    if not value.startswith(PREFIX):
        return value
    try:
        return _fernet().decrypt(value[len(PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Stored credential cannot be decrypted with the configured key.") from exc


def is_sensitive_name(name: str) -> bool:
    normalized = name.strip().lower().replace("_", "-")
    return normalized in SENSITIVE_NAMES or any(part in normalized for part in ("token", "secret", "password", "api-key"))


def protect_key_values(items: list[dict]) -> list[dict]:
    return [{**item, "value": encrypt(str(item.get("value", ""))) if is_sensitive_name(str(item.get("key", ""))) else str(item.get("value", ""))} for item in items]


def reveal_key_values(items: list[dict]) -> list[dict]:
    return [{**item, "value": decrypt(str(item.get("value", "")))} for item in items]


def mask_key_values(items: list[dict]) -> list[dict]:
    return [{**item, "value": MASK if is_sensitive_name(str(item.get("key", ""))) and item.get("value") else item.get("value", "")} for item in items]


def protect_auth(auth_type: str, config: dict[str, str]) -> dict[str, str]:
    sensitive = {"token", "password", "value", "client_secret"}
    return {key: encrypt(value) if key.lower() in sensitive and value and value != MASK else value for key, value in config.items()}


def reveal_auth(config: dict[str, str]) -> dict[str, str]:
    return {key: decrypt(value) for key, value in config.items()}


def mask_auth(config: dict[str, str]) -> dict[str, str]:
    return {key: MASK if key.lower() in {"token", "password", "value", "client_secret"} and value else value for key, value in config.items()}


def mask_response_headers(headers: dict[str, str]) -> dict[str, str]:
    return {key: (MASK if is_sensitive_name(key) else value) for key, value in headers.items()}
