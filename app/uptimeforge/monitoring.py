import asyncio
import logging
import socket
from dataclasses import dataclass
from datetime import timedelta
from time import perf_counter
from urllib.parse import urlsplit

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings
from .models import CheckResult, Monitor, utcnow
from .security import UnsafeTarget, resolve_target

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Outcome:
    status: str
    status_code: int | None
    response_time_ms: float
    error: str | None = None


async def probe(url: str, settings: Settings) -> Outcome:
    started = perf_counter()
    status_code = None
    error = None
    try:
        # The deadline covers DNS, connection, headers and the entire streamed body.
        async with asyncio.timeout(settings.check_timeout_seconds):
            pinned_url, hostname = await resolve_target(url)
            original = urlsplit(url)
            host_header = f"[{hostname}]" if ":" in hostname else hostname
            if original.port:
                host_header += f":{original.port}"
            async with httpx.AsyncClient(
                trust_env=False,
                follow_redirects=False,
                timeout=settings.check_timeout_seconds,
                headers={"User-Agent": "UptimeForge/0.1", "Accept-Encoding": "identity"},
            ) as client:
                async with client.stream(
                    "GET",
                    pinned_url,
                    headers={"Host": host_header},
                    extensions={"sni_hostname": hostname},
                ) as response:
                    status_code = response.status_code
                    length = response.headers.get("content-length")
                    if length and length.isdecimal() and int(length) > settings.max_response_bytes:
                        raise ValueError("Response exceeds size limit")
                    # Raw streaming avoids decompression bombs; the body is never retained.
                    total = 0
                    async for chunk in response.aiter_raw():
                        total += len(chunk)
                        if total > settings.max_response_bytes:
                            raise ValueError("Response exceeds size limit")
                    if not 200 <= status_code < 400:
                        error = "HTTP error response"
    except UnsafeTarget:
        error = "Target blocked by URL safety policy"
    except (TimeoutError, httpx.TimeoutException):
        error = "Request timed out"
    except socket.gaierror:
        error = "DNS resolution failed"
    except httpx.HTTPError:
        error = "Connection or protocol failure"
    except ValueError:
        error = "Response exceeds size limit"
    elapsed = round((perf_counter() - started) * 1000, 2)
    return Outcome("DOWN" if error else "UP", status_code, elapsed, error)


async def record_check(session: AsyncSession, monitor: Monitor, settings: Settings) -> CheckResult:
    """Caller holds the monitor row lock until this transaction commits."""
    outcome = await probe(monitor.url, settings)
    checked_at = utcnow()
    result = CheckResult(
        monitor_id=monitor.id,
        target_url=monitor.url,
        status=outcome.status,
        status_code=outcome.status_code,
        response_time_ms=outcome.response_time_ms,
        error=outcome.error,
        checked_at=checked_at,
    )
    session.add(result)
    monitor.status = outcome.status
    monitor.status_code = outcome.status_code
    monitor.response_time_ms = outcome.response_time_ms
    monitor.last_checked_at = checked_at
    monitor.next_check_at = checked_at + timedelta(seconds=monitor.interval_seconds)
    await session.flush()
    logger.info(
        "monitor_checked",
        extra={
            "monitor_id": monitor.id,
            "status": outcome.status,
            "response_time_ms": outcome.response_time_ms,
        },
    )
    return result
