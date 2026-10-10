import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

import httpx


class UnsafeTarget(ValueError):
    pass


def public_ip(value: str) -> bool:
    address = ipaddress.ip_address(value)
    # IPv6 translation/tunneling ranges can conceal a private IPv4 destination.
    if isinstance(address, ipaddress.IPv6Address):
        if address.is_site_local or address.ipv4_mapped or address.sixtofour or address.teredo:
            return False
        if address in ipaddress.ip_network("64:ff9b::/96"):
            return False
        if address in ipaddress.ip_network("64:ff9b:1::/48"):
            return False
    return address.is_global and not address.is_multicast and not address.is_reserved


def validate_url(value: str) -> str:
    try:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise UnsafeTarget("Use a complete http:// or https:// URL")
        if parts.username is not None or parts.password is not None or parts.fragment:
            raise UnsafeTarget("URL credentials and fragments are not allowed")
        if any(ord(char) <= 32 or ord(char) == 127 for char in value) or "\\" in value:
            raise UnsafeTarget("URL contains unsafe characters")
        host = parts.hostname.rstrip(".").lower()
        if "%" in host:
            raise UnsafeTarget("Scoped or encoded hostnames are not allowed")
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise UnsafeTarget("Local destinations are not allowed")
        if parts.port not in {None, 80, 443}:
            raise UnsafeTarget("Only ports 80 and 443 are allowed")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if ":" in host or "%" in host:
                raise UnsafeTarget("Invalid hostname") from None
        else:
            if not public_ip(host):
                raise UnsafeTarget("Only public IP addresses are allowed")
        normalized = str(httpx.URL(value))
        if len(normalized) > 2048:
            raise UnsafeTarget("URL is too long")
        return normalized
    except (ValueError, httpx.InvalidURL) as exc:
        if isinstance(exc, UnsafeTarget):
            raise
        raise UnsafeTarget("Invalid URL") from None


async def resolve_target(url: str) -> tuple[str, str]:
    """Resolve once, reject every unsafe answer, and pin the connection to an IP."""
    parts = urlsplit(validate_url(url))
    host = parts.hostname
    assert host is not None
    port = parts.port or (443 if parts.scheme == "https" else 80)
    answers = await asyncio.get_running_loop().getaddrinfo(
        host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
    )
    addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
    if not addresses or not all(public_ip(address) for address in addresses):
        raise UnsafeTarget("DNS resolved to a non-public destination")
    address = addresses[0]
    authority = f"[{address}]" if ":" in address else address
    if parts.port:
        authority += f":{parts.port}"
    return urlunsplit((parts.scheme, authority, parts.path, parts.query, "")), host
