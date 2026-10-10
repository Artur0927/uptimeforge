import asyncio
import socket

import httpx
import pytest

from uptimeforge import monitoring
from uptimeforge.config import get_settings
from uptimeforge.security import UnsafeTarget


class Body(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk


@pytest.fixture
def network(monkeypatch):
    real_client = httpx.AsyncClient
    requests = []

    async def resolver(url):
        return "https://8.8.8.8/health", "example.com"

    def install(handler):
        def capture(request):
            requests.append(request)
            return handler(request)

        def client(**kwargs):
            assert kwargs["trust_env"] is False
            assert kwargs["follow_redirects"] is False
            return real_client(transport=httpx.MockTransport(capture), **kwargs)

        monkeypatch.setattr(monitoring.httpx, "AsyncClient", client)

    monkeypatch.setattr(monitoring, "resolve_target", resolver)
    return install, requests


@pytest.mark.parametrize(
    "code,status", [(200, "UP"), (204, "UP"), (302, "UP"), (404, "DOWN"), (503, "DOWN")]
)
async def test_http_status_and_pinned_request(network, code, status):
    install, requests = network
    install(
        lambda _: httpx.Response(
            code, stream=Body([b"ok"]), headers={"Location": "http://127.0.0.1"}
        )
    )
    result = await monitoring.probe("https://example.com/health", get_settings())
    assert result.status == status and result.status_code == code
    assert result.response_time_ms >= 0
    assert len(requests) == 1
    assert requests[0].url.host == "8.8.8.8"
    assert requests[0].headers["host"] == "example.com"
    assert requests[0].extensions["sni_hostname"] == "example.com"


@pytest.mark.parametrize(
    "exception,error",
    [
        (httpx.ConnectError("secret details"), "Connection or protocol failure"),
        (httpx.ReadTimeout("secret details"), "Request timed out"),
    ],
)
async def test_network_failures(network, exception, error):
    install, _ = network

    def fail(request):
        raise exception

    install(fail)
    result = await monitoring.probe("https://example.com", get_settings())
    assert result.status == "DOWN" and result.error == error
    assert result.status_code is None


@pytest.mark.parametrize(
    "headers,chunks", [({"content-length": "2048"}, []), ({}, [b"a" * 600, b"b" * 600])]
)
async def test_response_size_limit(network, headers, chunks):
    install, _ = network
    install(lambda _: httpx.Response(200, headers=headers, stream=Body(chunks)))
    settings = get_settings().model_copy(update={"max_response_bytes": 1024})
    result = await monitoring.probe("https://example.com", settings)
    assert result.status == "DOWN" and result.error == "Response exceeds size limit"


@pytest.mark.parametrize(
    "exception,error",
    [
        (UnsafeTarget("private"), "Target blocked by URL safety policy"),
        (socket.gaierror("failed"), "DNS resolution failed"),
    ],
)
async def test_dns_failure(monkeypatch, exception, error):
    async def resolver(url):
        raise exception

    monkeypatch.setattr(monitoring, "resolve_target", resolver)
    result = await monitoring.probe("https://example.com", get_settings())
    assert result.status == "DOWN" and result.error == error


async def test_total_deadline_includes_dns(monkeypatch):
    async def slow_dns(url):
        await asyncio.sleep(0.1)

    monkeypatch.setattr(monitoring, "resolve_target", slow_dns)
    settings = get_settings().model_copy(update={"check_timeout_seconds": 0.01})
    result = await monitoring.probe("https://example.com", settings)
    assert result.error == "Request timed out"


async def test_real_transport_connects_to_pinned_ip_and_uses_original_tls_hostname(monkeypatch):
    from httpcore._backends.anyio import AnyIOBackend

    captured = {}

    class Stream:
        async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
            captured["sni"] = server_hostname
            assert ssl_context.check_hostname is True
            return self

        async def write(self, buffer, timeout=None):
            captured["request"] = captured.get("request", b"") + buffer

        async def read(self, max_bytes, timeout=None):
            return b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"

        async def aclose(self):
            pass

        def get_extra_info(self, info):
            return None

    async def connect(self, host, port, **kwargs):
        captured["host"] = host
        return Stream()

    async def resolver(url):
        return "https://8.8.8.8/health", "example.com"

    monkeypatch.setattr(AnyIOBackend, "connect_tcp", connect)
    monkeypatch.setattr(monitoring, "resolve_target", resolver)
    result = await monitoring.probe("https://example.com/health", get_settings())
    assert result.status == "UP"
    assert captured["host"] == "8.8.8.8"
    assert captured["sni"] == "example.com"
    assert b"Host: example.com\r\n" in captured["request"]
