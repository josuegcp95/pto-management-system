"""Tests for the database connection and session module."""

import pytest
from pydantic import SecretStr

from app.config import Settings, get_settings
from app.database import Base, get_engine, normalize_database_url


def test_normalize_database_url():
    assert (
        normalize_database_url("postgres://user:pass@localhost:5432/pto_db")
        == "postgresql+psycopg://user:pass@localhost:5432/pto_db"
    )
    assert (
        normalize_database_url("postgresql://user:pass@localhost:5432/pto_db")
        == "postgresql+psycopg://user:pass@localhost:5432/pto_db"
    )
    assert (
        normalize_database_url("postgresql+psycopg://user:pass@localhost:5432/pto_db")
        == "postgresql+psycopg://user:pass@localhost:5432/pto_db"
    )


def test_declarative_base_metadata_initialized():
    assert Base.metadata is not None


def test_get_engine_raises_when_database_url_missing(monkeypatch):
    get_settings.cache_clear()
    get_engine.cache_clear()
    monkeypatch.setattr(
        "app.database.get_settings", lambda: Settings(database_url=SecretStr(""))
    )
    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        get_engine()
    get_engine.cache_clear()
    get_settings.cache_clear()


def test_settings_repr_hides_secret_values(monkeypatch):
    """Secrets must never appear in repr(settings), e.g. in logs or tracebacks."""
    secrets = {
        "database_url": "postgresql+psycopg://user:super-secret-pw@localhost:5432/pto_db",
        "jwt_secret": "super-secret-jwt-value",
        "openai_api_key": "sk-super-secret-openai-key",
    }
    get_settings.cache_clear()
    try:
        settings = get_settings()
        for name, value in secrets.items():
            monkeypatch.setattr(settings, name, SecretStr(value))

        text = repr(settings)
        for name, value in secrets.items():
            assert value not in text
            assert getattr(settings, name).get_secret_value() == value
        assert "**********" in text
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
