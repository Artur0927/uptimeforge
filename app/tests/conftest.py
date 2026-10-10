import os

# Test-only credentials, never used by a running application.
os.environ["DATABASE_URL"] = "postgresql+psycopg://test:test@127.0.0.1/uptimeforge_test"
os.environ["AUTH_USERNAME"] = "test-admin"
os.environ["AUTH_PASSWORD"] = "only-for-tests-12345"

import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from uptimeforge import api, monitoring
from uptimeforge.db import get_session
from uptimeforge.main import app
from uptimeforge.models import Base


@pytest.fixture
async def database():
    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
async def client(database, monkeypatch):
    async def session_override():
        async with database() as session:
            yield session

    async def public_destination(url, settings):
        return None

    async def successful_probe(url, settings):
        return monitoring.Outcome("UP", 200, 42.5)

    app.dependency_overrides[get_session] = session_override
    monkeypatch.setattr(api, "validate_destination", public_destination)
    monkeypatch.setattr(monitoring, "probe", successful_probe)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        auth=("test-admin", "only-for-tests-12345"),
        headers={"X-UptimeForge-Request": "1"},
    ) as client:
        yield client
    app.dependency_overrides.clear()
