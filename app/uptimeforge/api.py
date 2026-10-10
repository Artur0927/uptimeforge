import asyncio
import socket
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.security import HTTPBasic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings, get_settings
from .db import get_session
from .models import CheckResult, Monitor, utcnow
from .monitoring import record_check
from .schemas import CheckRead, MonitorCreate, MonitorRead, MonitorUpdate
from .security import UnsafeTarget, resolve_target


def request_header(
    x_uptimeforge_request: Annotated[str, Header(description="Required for write requests")] = "1",
) -> None:
    """Expose the CSRF header in OpenAPI. Middleware enforces it before routing."""


router = APIRouter(
    prefix="/api/monitors",
    tags=["monitors"],
    dependencies=[Depends(HTTPBasic(auto_error=False)), Depends(request_header)],
)
Session = Annotated[AsyncSession, Depends(get_session)]
Config = Annotated[Settings, Depends(get_settings)]


async def get_monitor(session: AsyncSession, monitor_id: int, *, lock: bool = False) -> Monitor:
    query = select(Monitor).where(Monitor.id == monitor_id)
    if lock:
        query = query.with_for_update(skip_locked=True)
    monitor = await session.scalar(query)
    if monitor is None:
        if lock and await session.get(Monitor, monitor_id) is not None:
            raise HTTPException(409, "Monitor is being checked or updated; try again shortly")
        raise HTTPException(404, "Monitor not found")
    return monitor


async def validate_destination(url: str, settings: Settings) -> None:
    try:
        async with asyncio.timeout(settings.check_timeout_seconds):
            await resolve_target(url)
    except (UnsafeTarget, socket.gaierror, TimeoutError):
        raise HTTPException(422, "Target must resolve to public IP addresses") from None


@router.get("", response_model=list[MonitorRead])
async def list_monitors(
    session: Session,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return (
        await session.scalars(select(Monitor).order_by(Monitor.id).limit(limit).offset(offset))
    ).all()


@router.post("", response_model=MonitorRead, status_code=201)
async def create_monitor(payload: MonitorCreate, session: Session, settings: Config):
    await validate_destination(payload.url, settings)
    monitor = Monitor(**payload.model_dump())
    session.add(monitor)
    await session.commit()
    return monitor


@router.get("/{monitor_id}", response_model=MonitorRead)
async def read_monitor(monitor_id: int, session: Session):
    return await get_monitor(session, monitor_id)


@router.patch("/{monitor_id}", response_model=MonitorRead)
async def update_monitor(
    monitor_id: int,
    payload: MonitorUpdate,
    session: Session,
    settings: Config,
):
    values = payload.model_dump(exclude_unset=True)
    if "url" in values:
        await validate_destination(values["url"], settings)
    monitor = await get_monitor(session, monitor_id, lock=True)
    if "url" in values and values["url"] != monitor.url:
        monitor.status = "PENDING"
        monitor.status_code = None
        monitor.response_time_ms = None
        monitor.last_checked_at = None
    for name, value in values.items():
        setattr(monitor, name, value)
    if values:
        monitor.next_check_at = utcnow()
    await session.commit()
    return monitor


@router.delete("/{monitor_id}", status_code=204)
async def delete_monitor(monitor_id: int, session: Session):
    monitor = await get_monitor(session, monitor_id, lock=True)
    await session.delete(monitor)
    await session.commit()
    return Response(status_code=204)


@router.post("/{monitor_id}/check", response_model=CheckRead)
async def check_monitor(monitor_id: int, session: Session, settings: Config):
    monitor = await get_monitor(session, monitor_id, lock=True)
    result = await record_check(session, monitor, settings)
    await session.commit()
    return result


@router.get("/{monitor_id}/history", response_model=list[CheckRead])
async def monitor_history(
    monitor_id: int,
    session: Session,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    await get_monitor(session, monitor_id)
    query = (
        select(CheckResult)
        .where(CheckResult.monitor_id == monitor_id)
        .order_by(CheckResult.checked_at.desc(), CheckResult.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return (await session.scalars(query)).all()
