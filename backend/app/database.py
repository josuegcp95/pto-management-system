"""Database connection pool and session management.

Establishes the PostgreSQL persistence boundary defined in the System Design
Specification. Reads DATABASE_URL from app/config.py.
"""

from collections.abc import Generator
from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy ORM models."""
    pass


def normalize_database_url(url: str) -> str:
    """Ensure PostgreSQL connection strings use the psycopg v3 dialect."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@lru_cache
def get_engine() -> Engine:
    """Create and cache the SQLAlchemy engine using DATABASE_URL from app.config."""
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Configure it in backend/.env or environment variables."
        )
    db_url = normalize_database_url(settings.database_url)
    return create_engine(db_url, pool_pre_ping=True)


@lru_cache
def get_session_local() -> sessionmaker[Session]:
    """Create and cache the database session factory."""
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session per request."""
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()