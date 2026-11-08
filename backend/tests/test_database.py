"""Tests for the database connection and session module."""

import pytest
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
    monkeypatch.setattr("app.database.get_settings", lambda: Settings(database_url=""))
    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        get_engine()
    get_engine.cache_clear()
    get_settings.cache_clear()