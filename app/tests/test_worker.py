from datetime import timedelta

from sqlalchemy import select

from uptimeforge import monitoring, worker
from uptimeforge.models import CheckResult, Monitor, utcnow


async def test_worker_checks_only_due_monitors(database, monkeypatch):
    async def probe(url, settings):
        return monitoring.Outcome("UP", 200, 12)

    monkeypatch.setattr(worker, "SessionFactory", database)
    monkeypatch.setattr(monitoring, "probe", probe)
    async with database() as session:
        session.add_all(
            [
                Monitor(name="Due", url="https://example.com", interval_seconds=60),
                Monitor(
                    name="Later",
                    url="https://example.org",
                    interval_seconds=60,
                    next_check_at=utcnow() + timedelta(hours=1),
                ),
            ]
        )
        await session.commit()
    assert await worker.check_due_once() is True
    assert await worker.check_due_once() is False
    async with database() as session:
        results = (await session.scalars(select(CheckResult))).all()
        assert len(results) == 1 and results[0].status == "UP"
        monitor = await session.get(Monitor, results[0].monitor_id)
        assert monitor.next_check_at > monitor.last_checked_at


async def test_worker_rolls_back_unexpected_failure(database, monkeypatch):
    import pytest

    async def fail(url, settings):
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(worker, "SessionFactory", database)
    monkeypatch.setattr(monitoring, "probe", fail)
    async with database() as session:
        monitor = Monitor(name="Due", url="https://example.com", interval_seconds=60)
        session.add(monitor)
        await session.commit()
        monitor_id = monitor.id
    with pytest.raises(RuntimeError):
        await worker.check_due_once()
    async with database() as session:
        assert (await session.get(Monitor, monitor_id)).status == "PENDING"
        assert (await session.scalars(select(CheckResult))).all() == []
