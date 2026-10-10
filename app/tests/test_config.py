import pytest
from pydantic import ValidationError

from uptimeforge.config import Settings


def test_credentials_are_required(monkeypatch):
    monkeypatch.delenv("AUTH_PASSWORD")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_reject_weak_password_and_non_postgres():
    with pytest.raises(ValidationError):
        Settings(auth_password="weak", _env_file=None)
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite:///app.db", _env_file=None)


def test_settings_do_not_reveal_secrets():
    representation = repr(Settings(_env_file=None))
    assert "only-for-tests" not in representation
    assert "test:test@" not in representation
