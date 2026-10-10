"""Independent worker: python -m uptimeforge.worker. Stop with Ctrl-C/SIGTERM."""

import asyncio
import logging
import signal

from sqlalchemy import select

from .config import get_settings
from .db import SessionFactory, engine
from .logging import configure_logging
from .models import Monitor, utcnow
from .monitoring import record_check

logger = logging.getLogger(__name__)


async def check_due_once() -> bool:
    async with SessionFactory() as session, session.begin():
        monitor = await session.scalar(
            select(Monitor)
            .where(Monitor.next_check_at <= utcnow())
            .order_by(Monitor.next_check_at, Monitor.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if monitor is None:
            return False
        await record_check(session, monitor, get_settings())
        return True


async def run() -> None:
    settings = get_settings()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    async def lane() -> None:
        while not stop.is_set():
            try:
                if await check_due_once():
                    continue
            except Exception:
                logger.exception("worker_check_failed")
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_seconds)
            except TimeoutError:
                pass

    logger.info("worker_started")
    try:
        await asyncio.gather(*(lane() for _ in range(settings.worker_concurrency)))
    finally:
        await engine.dispose()
        logger.info("worker_stopped")


if __name__ == "__main__":
    configure_logging()
    asyncio.run(run())
