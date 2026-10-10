from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    database_url: SecretStr
    auth_username: str = Field(min_length=1, max_length=100)
    auth_password: SecretStr
    check_timeout_seconds: float = Field(default=10, ge=1, le=60)
    max_response_bytes: int = Field(default=1_048_576, ge=1024, le=10_485_760)
    worker_poll_seconds: float = Field(default=2, ge=0.5, le=60)
    worker_concurrency: int = Field(default=5, ge=1, le=20)

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use postgresql+psycopg://")
        return value

    @field_validator("auth_password")
    @classmethod
    def strong_password(cls, value: SecretStr) -> SecretStr:
        if value.get_secret_value().startswith("REPLACE_"):
            raise ValueError("Replace the example password before starting the application")
        if len(value.get_secret_value()) < 12:
            raise ValueError("AUTH_PASSWORD must contain at least 12 characters")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
