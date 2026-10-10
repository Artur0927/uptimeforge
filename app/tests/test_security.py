import asyncio
import socket

import pytest

from uptimeforge.security import UnsafeTarget, public_ip, resolve_target, validate_url


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost",
        "http://x.localhost",
        "http://service.internal",
        "http://10.0.0.1",
        "http://172.16.1.1",
        "http://192.168.1.1",
        "http://169.254.169.254",
        "http://0.0.0.0",
        "http://[::1]",
        "http://[fc00::1]",
        "http://[fe80::1]",
        "http://[::ffff:127.0.0.1]",
        "http://[64:ff9b::7f00:1]",
        "ftp://example.com",
        "file:///etc/passwd",
        "http://user:password@example.com",
        "https://example.com:8080",
        "http://example.com/#x",
        "http://example.com\n",
        "http://example.com\\@localhost",
        "http://example.com:wrong",
    ],
)
def test_unsafe_urls(url):
    with pytest.raises(UnsafeTarget):
        validate_url(url)


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "100.64.0.1", "224.0.0.1", "255.255.255.255", "2001:db8::1"]
)
def test_nonpublic_addresses(address):
    assert not public_ip(address)


def test_public_url_and_unicode_domain():
    assert validate_url("https://example.com") == "https://example.com"
    assert "xn--" in validate_url("https://пример.рф")
    assert public_ip("8.8.8.8")


@pytest.mark.parametrize("url", ["http://[fec0::1]", "http://[2606:4700::1111%25lo0]"])
def test_ipv6_site_local_and_scoped_hosts_rejected(url):
    with pytest.raises(UnsafeTarget):
        validate_url(url)


def answers(*addresses):
    return [
        (
            socket.AF_INET6 if ":" in ip else socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            (ip, 443),
        )
        for ip in addresses
    ]


async def test_mixed_dns_answers_blocked(monkeypatch):
    async def lookup(*args, **kwargs):
        return answers("8.8.8.8", "10.0.0.1")

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", lookup)
    with pytest.raises(UnsafeTarget):
        await resolve_target("https://example.com")


async def test_dns_pins_public_ip_and_preserves_path(monkeypatch):
    calls = []

    async def lookup(*args, **kwargs):
        calls.append(args)
        return answers("8.8.8.8")

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", lookup)
    target, host = await resolve_target("https://example.com:443/health?q=1")
    assert target == "https://8.8.8.8/health?q=1"
    assert host == "example.com" and len(calls) == 1


async def test_ipv6_pinning(monkeypatch):
    async def lookup(*args, **kwargs):
        return answers("2606:4700:4700::1111")

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", lookup)
    assert (await resolve_target("https://example.com"))[0] == "https://[2606:4700:4700::1111]"
