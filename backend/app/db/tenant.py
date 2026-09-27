"""Resolve and cache isolated SQLAlchemy connections per company."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app import models


@lru_cache(maxsize=128)
def get_tenant_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


@lru_cache(maxsize=128)
def get_tenant_session_factory(database_url: str) -> sessionmaker:
    return sessionmaker(bind=get_tenant_engine(database_url), autoflush=False, autocommit=False)


def get_tenant_db(company: models.TenantCompany) -> Session:
    return get_tenant_session_factory(company.database_url)()
