from urllib.parse import urlsplit

from app.api_testing.outbound_security import PinnedUrl, validate_and_pin_url
from app.common.exceptions import ValidationAppError
from app.core.config import get_settings


def host_matches(hostname: str, allowed: str) -> bool:
    hostname, allowed = hostname.lower().rstrip("."), allowed.lower().rstrip(".")
    return hostname == allowed or hostname.endswith("." + allowed)


async def validate_load_target(url: str, project_hosts: list[str], allowlist_enabled: bool) -> PinnedUrl:
    hostname = (urlsplit(url).hostname or "").lower().rstrip(".")
    settings = get_settings()
    allowed = [*settings.load_test_allowed_hosts_list, *[item.lower() for item in project_hosts]]
    if settings.LOAD_TEST_REQUIRE_ALLOWLIST or allowlist_enabled:
        if not hostname or not any(host_matches(hostname, item) for item in allowed):
            raise ValidationAppError("Load-test target is not on the configured project/server allowlist.")
    return await validate_and_pin_url(url, allow_private=settings.LOAD_TEST_ALLOW_PRIVATE_NETWORKS)
