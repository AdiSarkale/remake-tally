"""Tenant bootstrap and fleet migration helpers."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import text
from alembic import command
from alembic.config import Config

from app.core.config import get_settings
from app.db.control import get_control_engine, get_control_session_factory
from app.db.control_models import TenantCompany
from app.services.tenant_credentials import resolve_tenant_database_url


def register_company(
    code: str,
    name: str,
    database_secret_ref: str,
    initialize_schema: bool = True,
) -> str:
    """Register a company and optionally initialize its isolated ERP schema."""
    code = code.strip().upper()
    if not code:
        raise ValueError("Company code is required")
    if not database_secret_ref.strip():
        raise ValueError("Tenant database secret reference is required")

    company_id = str(uuid.uuid4())

    with get_control_engine().begin() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM tenant_companies WHERE code = :code"),
            {"code": code},
        ).scalar_one_or_none()
        if exists:
            raise ValueError(f"Company code already exists: {code}")

        connection.execute(
            text(
                "INSERT INTO tenant_companies "
                "(id, code, name, database_secret_ref, active, provisioning_status) "
                "VALUES (:id, :code, :name, :database_secret_ref, FALSE, 'provisioning')"
            ),
            {
                "id": company_id,
                "code": code,
                "name": name,
                "database_secret_ref": database_secret_ref.strip(),
            },
        )

    try:
        database_url = resolve_tenant_database_url(database_secret_ref.strip())
        if initialize_schema:
            alembic_cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
            alembic_cfg.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(alembic_cfg, "head")
    except Exception:
        with get_control_engine().begin() as connection:
            connection.execute(
                text(
                    "UPDATE tenant_companies "
                    "SET provisioning_status = 'failed', active = FALSE "
                    "WHERE id = :id"
                ),
                {"id": company_id},
            )
        raise

    with get_control_engine().begin() as connection:
        connection.execute(
            text(
                "UPDATE tenant_companies "
                "SET provisioning_status = 'ready', active = TRUE "
                "WHERE id = :id"
            ),
            {"id": company_id},
        )

    return company_id


def migrate_all_ready_tenants() -> list[str]:
    """Apply the current tenant Alembic head to every ready tenant."""
    migrated: list[str] = []
    db = get_control_session_factory()()
    try:
        companies = (
            db.query(TenantCompany)
            .filter(
                TenantCompany.active.is_(True),
                TenantCompany.provisioning_status == "ready",
            )
            .all()
        )
    finally:
        db.close()

    alembic_ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    failed: list[str] = []

    for company in companies:
        try:
            database_url = resolve_tenant_database_url(company.database_secret_ref)
            alembic_cfg = Config(str(alembic_ini))
            alembic_cfg.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(alembic_cfg, "head")
            migrated.append(company.code)
        except Exception:
            failed.append(company.code)
            with get_control_engine().begin() as connection:
                connection.execute(
                    text(
                        "UPDATE tenant_companies "
                        "SET provisioning_status = 'failed', active = FALSE "
                        "WHERE id = :id"
                    ),
                    {"id": company.id},
                )

    if failed:
        raise RuntimeError(
            "Tenant migrations failed for: " + ", ".join(sorted(failed))
        )

    return migrated


def bootstrap_demo_company() -> str:
    settings = get_settings()
    return register_company(
        "DEMO",
        "Demo Company",
        "LOCAL_DEFAULT",
        initialize_schema=False,
    )


def retry_failed_company(company_id: str) -> str:
    """Retry provisioning/migration for one failed tenant.

    A failed tenant remains inactive until its current schema reaches the
    tenant Alembic head successfully. A failed retry leaves it failed/inactive.
    """
    db = get_control_session_factory()()
    try:
        company = db.get(TenantCompany, company_id)
        if company is None:
            raise ValueError(f"Company not found: {company_id}")
        if company.provisioning_status != "failed":
            raise ValueError(
                f"Company {company.code} is not failed; refusing recovery transition"
            )
        secret_ref = company.database_secret_ref
        company.provisioning_status = "provisioning"
        company.active = False
        db.commit()
    finally:
        db.close()

    try:
        database_url = resolve_tenant_database_url(secret_ref)
        alembic_cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(alembic_cfg, "head")
    except Exception:
        with get_control_engine().begin() as connection:
            connection.execute(
                text(
                    "UPDATE tenant_companies "
                    "SET provisioning_status = 'failed', active = FALSE "
                    "WHERE id = :id"
                ),
                {"id": company_id},
            )
        raise

    with get_control_engine().begin() as connection:
        connection.execute(
            text(
                "UPDATE tenant_companies "
                "SET provisioning_status = 'ready', active = TRUE "
                "WHERE id = :id"
            ),
            {"id": company_id},
        )

    return company_id
