import ipaddress
from urllib.parse import urlsplit

from app.api_testing.outbound_security import validate_and_pin_url
from app.common.exceptions import ValidationAppError
from app.core.config import get_settings


def host_matches(host: str, pattern: str) -> bool:
    pattern = pattern.strip().lower().rstrip(".")
    return host == pattern or (pattern.startswith("*.") and host.endswith(pattern[1:]) and host != pattern[2:])


async def validate_automation_target(url: str, allowed_hosts=None):
    settings = get_settings()
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    global_hosts = [item.strip() for item in settings.AUTOMATION_ALLOWED_HOSTS.split(",") if item.strip()]
    for configured in (global_hosts, allowed_hosts or []):
        if configured and not any(host_matches(hostname, item) for item in configured):
            raise ValidationAppError("Destination is not permitted by the automation allowed-host policy.")
    pinned = await validate_and_pin_url(url, allow_private=settings.AUTOMATION_ALLOW_PRIVATE_NETWORKS)
    address = ipaddress.ip_address(pinned.ip)
    # Private opt-in permits private test infrastructure, never metadata or loopback.
    if address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast or address.is_reserved:
        raise ValidationAppError("Localhost, metadata, and reserved destinations are not allowed.")
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped and (mapped.is_loopback or mapped.is_link_local):
        raise ValidationAppError("Localhost and metadata destinations are not allowed.")
    return pinned


def request_url_validator(allowed_hosts):
    origin = None

    async def validate(url):
        nonlocal origin
        parsed = urlsplit(url)
        current = (parsed.scheme.lower(), parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        if origin is not None and current != origin:
            raise ValidationAppError("Cross-origin automation redirects are not permitted.")
        pinned = await validate_automation_target(url, allowed_hosts)
        origin = current
        return pinned

    return validate
