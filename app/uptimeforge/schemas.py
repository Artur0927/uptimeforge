from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .security import validate_url


class MonitorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(max_length=2048)
    interval_seconds: int = Field(default=60, ge=30, le=86400)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name must not be blank")
        return value.strip()

    @field_validator("url")
    @classmethod
    def safe_url(cls, value: str) -> str:
        return validate_url(value)


class MonitorUpdate(MonitorCreate):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    url: str | None = Field(default=None, max_length=2048)
    interval_seconds: int | None = Field(default=None, ge=30, le=86400)

    @field_validator("name", "url", "interval_seconds", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Fields cannot be null")
        return value


class UTCModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("created_at", "last_checked_at", "checked_at", check_fields=False)
    @classmethod
    def ensure_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class MonitorRead(UTCModel):
    id: int
    name: str
    url: str
    interval_seconds: int
    status: str
    status_code: int | None
    response_time_ms: float | None
    last_checked_at: datetime | None
    created_at: datetime


class CheckRead(UTCModel):
    id: int
    monitor_id: int
    target_url: str
    status: str
    status_code: int | None
    response_time_ms: float
    error: str | None
    checked_at: datetime
