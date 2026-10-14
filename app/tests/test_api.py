import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from uptimeforge import api, monitoring
from uptimeforge.db import get_session
from uptimeforge.main import app
from uptimeforge.models import CheckResult


async def create(client, **values):
    return await client.post(
        "/api/monitors",
        json={
            "name": "Main API",
            "url": "https://example.com/health",
            "interval_seconds": 60,
            **values,
        },
    )


async def test_monitor_lifecycle_and_history(client, database):
    response = await create(client)
    assert response.status_code == 201
    monitor = response.json()
    assert monitor["status"] == "PENDING"
    assert monitor["created_at"].endswith("Z")
    monitor_id = monitor["id"]
    assert (await client.get("/api/monitors")).json() == [monitor]
    assert (await client.get(f"/api/monitors/{monitor_id}")).json() == monitor
    check = await client.post(f"/api/monitors/{monitor_id}/check")
    assert check.status_code == 200
    assert check.json()["status"] == "UP"
    assert check.json()["response_time_ms"] == 42.5
    assert check.json()["checked_at"].endswith("Z")
    history = (await client.get(f"/api/monitors/{monitor_id}/history")).json()
    assert history == [check.json()]
    updated = (await client.patch(f"/api/monitors/{monitor_id}", json={"name": "Renamed"})).json()
    assert updated["name"] == "Renamed" and updated["status"] == "UP"
    assert (await client.delete(f"/api/monitors/{monitor_id}")).status_code == 204
    assert (await client.get(f"/api/monitors/{monitor_id}")).status_code == 404
    async with database() as session:
        assert await session.scalar(select(func.count(CheckResult.id))) == 0


async def test_changed_target_resets_status_and_preserves_history(client):
    monitor_id = (await create(client)).json()["id"]
    await client.post(f"/api/monitors/{monitor_id}/check")
    response = await client.patch(
        f"/api/monitors/{monitor_id}", json={"url": "https://example.org"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "PENDING"
    assert response.json()["last_checked_at"] is None
    history = (await client.get(f"/api/monitors/{monitor_id}/history")).json()
    assert len(history) == 1
    assert history[0]["target_url"] == "https://example.com/health"


@pytest.mark.parametrize(
    "payload",
    [
        {"name": " "},
        {"url": "file:///etc/passwd"},
        {"url": "http://127.0.0.1"},
        {"url": "http://169.254.169.254/latest/meta-data"},
        {"interval_seconds": 1},
        {"interval_seconds": 86401},
        {"unknown": True},
    ],
)
async def test_invalid_create(client, payload):
    response = await create(client, **payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == 422


@pytest.mark.parametrize("field", ["url", "name", "interval_seconds"])
async def test_patch_null_is_rejected(client, field):
    monitor_id = (await create(client)).json()["id"]
    assert (
        await client.patch(f"/api/monitors/{monitor_id}", json={field: None})
    ).status_code == 422


async def test_missing_monitor_and_pagination(client):
    assert (await client.post("/api/monitors/999/check")).status_code == 404
    assert (await client.get("/api/monitors/999/history")).status_code == 404
    assert (await client.get("/api/monitors?limit=501")).status_code == 422
    for name in ("One", "Two"):
        await create(client, name=name)
    assert (await client.get("/api/monitors?offset=1&limit=1")).json()[0]["name"] == "Two"


async def test_failed_check_is_persisted(client, monkeypatch):
    async def failure(url, settings):
        return monitoring.Outcome("DOWN", None, 1000, "Request timed out")

    monkeypatch.setattr(monitoring, "probe", failure)
    monitor_id = (await create(client)).json()["id"]
    response = await client.post(f"/api/monitors/{monitor_id}/check")
    assert response.status_code == 200
    assert response.json()["error"] == "Request timed out"
    assert (await client.get(f"/api/monitors/{monitor_id}")).json()["status"] == "DOWN"


async def test_authentication_health_and_csrf(client):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as anonymous:
        for path in ("/", "/docs", "/redoc", "/openapi.json", "/api/monitors"):
            response = await anonymous.get(path)
            assert response.status_code == 401
            assert "Basic" in response.headers["www-authenticate"]
        assert (await anonymous.get("/health")).json() == {"status": "ok"}
    assert (await client.get("/api/monitors", auth=("test-admin", "wrong"))).status_code == 401
    response = await client.post(
        "/api/monitors", headers={"Origin": "https://evil.example"}, json={}
    )
    assert response.status_code == 403
    response = await client.post("/api/monitors", headers={"X-UptimeForge-Request": ""}, json={})
    assert response.status_code == 403


@pytest.mark.parametrize("peer,expected", [("10.20.1.236", 201), ("10.20.2.99", 403)])
async def test_https_browser_write_trusts_only_nginx_peer(client, peer, expected):
    proxy_app = ProxyHeadersMiddleware(app, trusted_hosts=["10.20.1.236"])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=proxy_app, client=(peer, 1234)),
        base_url="http://demo.example:8443",
        auth=client.auth,
        headers={
            "X-UptimeForge-Request": "1",
            "X-Forwarded-Proto": "https",
            "Origin": "https://demo.example:8443",
        },
    ) as proxied:
        assert (await create(proxied)).status_code == expected


async def test_openapi_includes_auth_and_write_header(client):
    schema = (await client.get("/openapi.json")).json()
    operation = schema["paths"]["/api/monitors"]["post"]
    assert operation["security"] == [{"HTTPBasic": []}]
    assert any(p["name"] == "x-uptimeforge-request" for p in operation["parameters"])


async def test_real_dashboard_empty_populated_details_and_escaping(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "Your uptime story starts here" in response.text
    assert "script-src 'self'" in response.headers["content-security-policy"]
    monitor_id = (await create(client, name="<script>alert(1)</script>")).json()["id"]
    await client.post(f"/api/monitors/{monitor_id}/check")
    response = await client.get("/")
    assert "42" in response.text and "Awaiting first check" not in response.text
    assert "&lt;script&gt;" in response.text
    response = await client.get(f"/monitors/{monitor_id}")
    assert response.status_code == 200
    assert "Successful response" in response.text
    assert "42.50" in response.text
    assert (await client.get("/monitors/999")).status_code == 404
    assert (await client.get("/static/app.js")).status_code == 200


async def test_dns_validation_rejects_before_insert(client, monkeypatch):
    async def reject(url):
        from uptimeforge.security import UnsafeTarget

        raise UnsafeTarget("private address")

    monkeypatch.setattr(api, "validate_destination", ORIGINAL_VALIDATOR)
    monkeypatch.setattr(api, "resolve_target", reject)
    assert (await create(client)).status_code == 422
    assert (await client.get("/api/monitors")).json() == []


ORIGINAL_VALIDATOR = api.validate_destination


async def test_database_outage_is_sanitized(client, monkeypatch):
    class UnavailableSession:
        async def execute(self, *args):
            raise SQLAlchemyError("sensitive connection details")

        async def scalars(self, *args):
            raise SQLAlchemyError("sensitive connection details")

    async def unavailable():
        yield UnavailableSession()

    monkeypatch.setitem(app.dependency_overrides, get_session, unavailable)
    for path in ("/health", "/api/monitors"):
        response = await client.get(path)
        assert response.status_code == 503
        assert response.json()["error"]["message"] == "Database temporarily unavailable"
        assert "sensitive" not in response.text
