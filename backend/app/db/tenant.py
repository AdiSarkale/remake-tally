"""Resolve isolated SQLAlchemy connections per company.

The registry is bounded and disposes evicted engines so a growing tenant
population cannot leave abandoned connection pools behind.
"""

from __future__ import annotations

from collections import OrderedDict
from threading import RLock

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.control_models import TenantCompany
from app.services.tenant_credentials import resolve_tenant_database_url

_settings = get_settings()
_MAX_TENANT_ENGINES = _settings.tenant_engine_cache_size
_registry: OrderedDict[str, tuple[Engine, sessionmaker]] = OrderedDict()
_lock = RLock()


def _get_or_create(database_url: str) -> tuple[Engine, sessionmaker]:
    with _lock:
        existing = _registry.pop(database_url, None)
        if existing is not None:
            _registry[database_url] = existing
            return existing

        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=_settings.tenant_pool_size,
            max_overflow=_settings.tenant_pool_max_overflow,
            pool_timeout=_settings.tenant_pool_timeout_seconds,
            pool_recycle=_settings.tenant_pool_recycle_seconds,
        )
        factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        _registry[database_url] = (engine, factory)

        while len(_registry) > _MAX_TENANT_ENGINES:
            _, (evicted_engine, _) = _registry.popitem(last=False)
            evicted_engine.dispose()

        return engine, factory


def get_tenant_engine(database_url: str) -> Engine:
    return _get_or_create(database_url)[0]


def get_tenant_session_factory(database_url: str) -> sessionmaker:
    return _get_or_create(database_url)[1]


def get_tenant_db(company: TenantCompany) -> Session:
    database_url = resolve_tenant_database_url(company.database_secret_ref)
    return get_tenant_session_factory(database_url)()


def dispose_tenant_engines() -> None:
    """Dispose every cached tenant pool during application shutdown."""
    with _lock:
        engines = [engine for engine, _ in _registry.values()]
        _registry.clear()

    for engine in engines:
        engine.dispose()
