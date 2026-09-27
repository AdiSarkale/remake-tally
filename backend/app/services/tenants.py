"""Tenant bootstrap helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import create_engine, text

from app import models
from app.core.config import get_settings
from app.db.control import get_control_engine


def register_company(code: str, name: str, database_url: str, initialize_schema: bool = False) -> str:
    """Register a company and optionally initialize its isolated ERP schema."""
    company_id = str(uuid.uuid4())

    with get_control_engine().begin() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM tenant_companies WHERE code = :code"),
            {"code": code},
        ).scalar_one_or_none()
        if exists:
            raise ValueError(f"Company code already exists: {code}")

        connection.execute(
            text("INSERT INTO tenant_companies (id, code, name, database_url, active) VALUES (:id, :code, :name, :database_url, TRUE)"),
            {"id": company_id, "code": code, "name": name, "database_url": database_url},
        )

    if initialize_schema:
        engine = create_engine(database_url, pool_pre_ping=True)
        tables = [table for table in models.Base.metadata.tables.values() if table.name != "tenant_companies"]
        models.Base.metadata.create_all(bind=engine, tables=tables)

    return company_id


def bootstrap_demo_company() -> str:
    settings = get_settings()
    return register_company("DEMO", "Demo Company", settings.database_url, initialize_schema=False)
