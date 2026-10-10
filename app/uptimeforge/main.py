import base64
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from .api import Session, get_monitor, router
from .config import get_settings
from .db import engine
from .logging import configure_logging
from .models import CheckResult, Monitor
from .schemas import CheckRead

ROOT = Path(__file__).parent
templates = Jinja2Templates(directory=ROOT / "templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    yield
    await engine.dispose()


app = FastAPI(title="UptimeForge", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.include_router(router)


def error_response(status: int, message: str, headers=None) -> JSONResponse:
    return JSONResponse({"error": {"code": status, "message": message}}, status, headers=headers)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    settings = get_settings()
    if request.url.path != "/health":
        valid = False
        try:
            scheme, encoded = request.headers.get("authorization", "").split(" ", 1)
            username, password = base64.b64decode(encoded, validate=True).decode().split(":", 1)
            valid = (
                scheme.lower() == "basic"
                and secrets.compare_digest(username.encode(), settings.auth_username.encode())
                and secrets.compare_digest(
                    password.encode(), settings.auth_password.get_secret_value().encode()
                )
            )
        except (ValueError, UnicodeError):
            pass
        if not valid:
            return error_response(
                401, "Authentication required", {"WWW-Authenticate": 'Basic realm="UptimeForge"'}
            )
    if request.method in {"POST", "PATCH", "DELETE", "PUT"}:
        origin = request.headers.get("origin")
        if origin:
            try:
                parsed = urlsplit(origin)
                same_origin = (parsed.scheme, parsed.netloc) == (
                    request.url.scheme,
                    request.url.netloc,
                )
            except ValueError:
                same_origin = False
            if not same_origin:
                return error_response(403, "Cross-origin requests are not allowed")
        if request.headers.get("x-uptimeforge-request") != "1":
            return error_response(403, "X-UptimeForge-Request: 1 header required")
    response = await call_next(request)
    response.headers.update(
        {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "no-store",
        }
    )
    # Swagger/ReDoc use CDN scripts; protected docs retain their own rendering policy.
    if request.url.path not in {"/docs", "/redoc", "/docs/oauth2-redirect"}:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'"
        )
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return error_response(exc.status_code, str(exc.detail), exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Omit raw input: target URLs may contain confidential query parameters.
    issues = [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(
        {"error": {"code": 422, "message": "Validation failed", "details": issues}}, 422
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    logging.getLogger(__name__).error("database_request_failed")
    return error_response(503, "Database temporarily unavailable")


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logging.getLogger(__name__).error("unexpected_request_failure")
    return error_response(500, "Unexpected application error")


@app.get("/health", tags=["health"])
async def health(session: Session):
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return error_response(503, "Database temporarily unavailable")
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def dashboard(request: Request, session: Session, page: int = 1):
    page = max(1, page)
    rows = (
        await session.scalars(
            select(Monitor).order_by(Monitor.id.desc()).limit(50).offset((page - 1) * 50)
        )
    ).all()
    total = await session.scalar(select(func.count(Monitor.id))) or 0
    counts = dict(
        (
            await session.execute(
                select(Monitor.status, func.count(Monitor.id)).group_by(Monitor.status)
            )
        ).all()
    )
    average = await session.scalar(select(func.avg(Monitor.response_time_ms)))
    recent = (
        await session.scalars(select(CheckResult).order_by(CheckResult.checked_at.desc()).limit(50))
    ).all()
    chart = [
        CheckRead.model_validate(result).model_dump(mode="json") for result in reversed(recent)
    ]
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "monitors": rows,
            "total": total,
            "counts": counts,
            "average": average,
            "chart": chart,
            "page": page,
            "has_next": page * 50 < total,
        },
    )


@app.get("/monitors/{monitor_id}", include_in_schema=False)
async def details(monitor_id: int, request: Request, session: Session):
    monitor = await get_monitor(session, monitor_id)
    history = (
        await session.scalars(
            select(CheckResult)
            .where(CheckResult.monitor_id == monitor_id)
            .order_by(CheckResult.checked_at.desc(), CheckResult.id.desc())
            .limit(100)
        )
    ).all()
    chart = [
        CheckRead.model_validate(result).model_dump(mode="json") for result in reversed(history)
    ]
    return templates.TemplateResponse(
        request=request,
        name="details.html",
        context={
            "monitor": monitor,
            "history": history,
            "chart": chart,
        },
    )
