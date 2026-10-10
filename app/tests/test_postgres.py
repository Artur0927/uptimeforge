"""Opt-in tests against an existing migrated, empty PostgreSQL *_test database.

No database is provisioned here. Only application records created by these tests
are removed by their fixture, using ORM DELETE with the normal FK cascade.
"""

import asyncio
import os

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from uptimeforge import monitoring, worker
from uptimeforge.api import get_monitor
from uptimeforge.models import CheckResult, Monitor

TEST_URL = os.environ.get("UPTIMEFORGE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_URL, reason="No dedicated PostgreSQL test database configured"
)


@pytest.fixture
async def postgres():
    url = make_url(TEST_URL)
    if url.drivername != "postgresql+psycopg" or not (url.database or "").endswith("_test"):
        pytest.fail("PostgreSQL tests require a postgresql+psycopg database ending in _test")
    engine = create_async_engine(
        url, connect_args={"connect_timeout": 5, "options": "-c timezone=UTC"}
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        if await session.scalar(select(func.count(Monitor.id))) != 0:
            pytest.fail("PostgreSQL test database must be empty; use an isolated database")
        monitor = Monitor(name="Test concurrency", url="https://example.com", interval_seconds=60)
        session.add(monitor)
        await session.commit()
        monitor_id = monitor.id
    try:
        yield factory, monitor_id
    finally:
        async with factory() as session:
            await session.execute(delete(Monitor).where(Monitor.id == monitor_id))
            await session.commit()
        await engine.dispose()


async def test_postgres_busy_monitor_returns_conflict(postgres):
    factory, monitor_id = postgres
    async with factory() as first, factory() as second:
        await get_monitor(first, monitor_id, lock=True)
        with pytest.raises(HTTPException) as exc:
            await get_monitor(second, monitor_id, lock=True)
        assert exc.value.status_code == 409
        await first.rollback()
        await second.rollback()


async def test_postgres_workers_skip_locked_and_schedule_once(postgres, monkeypatch):
    factory, monitor_id = postgres
    entered, release = asyncio.Event(), asyncio.Event()

    async def probe(url, settings):
        entered.set()
        await release.wait()
        return monitoring.Outcome("UP", 200, 5)

    monkeypatch.setattr(worker, "SessionFactory", factory)
    monkeypatch.setattr(monitoring, "probe", probe)
    task = asyncio.create_task(worker.check_due_once())
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        assert await worker.check_due_once() is False
    finally:
        release.set()
        await task
    assert await worker.check_due_once() is False
    async with factory() as session:
        assert await session.scalar(select(func.count(CheckResult.id))) == 1
        monitor = await session.get(Monitor, monitor_id)
        assert monitor.last_checked_at.tzinfo is not None
        assert monitor.next_check_at > monitor.last_checked_at
