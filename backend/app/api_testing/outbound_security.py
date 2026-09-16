import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from time import perf_counter
from urllib.parse import urlsplit, urlunsplit

from app.common.exceptions import ValidationAppError
from app.core.config import get_settings


@dataclass
class PinnedUrl:
    logical_url: str
    network_url: str
    host_header: str
    sni_hostname: str
    ip: str
    dns_lookup_ms: float


def _allowed_ip(address: str, allow_private: bool) -> bool:
    ip = ipaddress.ip_address(address)
    if ip.is_unspecified or ip.is_multicast:
        return False
    return allow_private or ip.is_global


async def validate_and_pin_url(url: str, allow_private: bool | None = None) -> PinnedUrl:
    settings = get_settings()
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValidationAppError("Only HTTP and HTTPS URLs are allowed.")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValidationAppError("URL must contain a hostname and cannot contain embedded credentials.")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local"):
        raise ValidationAppError("Local and internal hostnames are not allowed.")
    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise ValidationAppError("URL contains an invalid port.") from exc

    started = perf_counter()
    try:
        records = await asyncio.to_thread(socket.getaddrinfo, hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValidationAppError("The hostname could not be resolved.") from exc
    dns_ms = (perf_counter() - started) * 1000
    addresses = list(dict.fromkeys(record[4][0] for record in records))
    private_allowed = settings.API_ALLOW_PRIVATE_NETWORKS if allow_private is None else allow_private
    if not addresses or any(not _allowed_ip(address, private_allowed) for address in addresses):
        raise ValidationAppError("The destination resolves to a private, reserved, or internal address.")
    selected = addresses[0]
    ip_host = f"[{selected}]" if ":" in selected else selected
    default_port = (parsed.scheme.lower() == "https" and port == 443) or (parsed.scheme.lower() == "http" and port == 80)
    network_netloc = ip_host if default_port else f"{ip_host}:{port}"
    host_header = hostname if default_port else f"{hostname}:{port}"
    return PinnedUrl(
        logical_url=urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, "")),
        network_url=urlunsplit((parsed.scheme, network_netloc, parsed.path or "/", parsed.query, "")),
        host_header=host_header,
        sni_hostname=hostname,
        ip=selected,
        dns_lookup_ms=round(dns_ms, 2),
    )


def verify_connected_peer(response, expected_ip: str) -> None:
    stream = response.extensions.get("network_stream")
    if stream is None:
        return
    try:
        peer = stream.get_extra_info("server_addr") or stream.get_extra_info("peername")
        peer_ip = peer[0] if isinstance(peer, tuple) else None
    except Exception:
        return
    if peer_ip and ipaddress.ip_address(peer_ip) != ipaddress.ip_address(expected_ip):
        raise ValidationAppError("Connected peer did not match the validated destination.")
