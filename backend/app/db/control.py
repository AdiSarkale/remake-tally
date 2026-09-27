"""Control-plane database access for company routing metadata."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()


def control_database_url() -> str:
    if not settings.control_database_url:
        raise RuntimeError("CONTROL_DATABASE_URL must be configured for production")
    return settings.control_database_url


@lru_cache(maxsize=1)
def get_control_engine():
    return create_engine(control_database_url(), pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_control_session_factory():
    return sessionmaker(bind=get_control_engine(), autoflush=False, autocommit=False)


def get_control_db():
    db = get_control_session_factory()()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
