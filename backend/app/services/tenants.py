"""Tenant bootstrap and fleet migration helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.control import get_control_engine, get_control_session_factory
from app.db.control_models import TenantCompany, TenantMigrationEvent
from app.services.tenant_credentials import resolve_tenant_database_url
from app.services.tenant_migration_lock import (
    company_migration_lock,
    fleet_migration_lock,
)


def _tenant_alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _current_tenant_revision(database_url: str) -> str | None:
    """Return all current Alembic revisions, or None for a new/uninitialized DB."""
    engine = create_engine(database_url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            revisions = connection.execute(
                text("SELECT version_num FROM alembic_version ORDER BY version_num")
            ).scalars().all()
        return ",".join(str(revision) for revision in revisions) or None
    except SQLAlchemyError:
        return None
    finally:
        engine.dispose()


def _start_migration_event(
    company: TenantCompany,
    operation: str,
    from_revision: str | None,
) -> str:
    event_id = str(uuid.uuid4())
    db = get_control_session_factory()()
    try:
        db.add(
            TenantMigrationEvent(
                id=event_id,
                company_id=company.id,
                company_code=company.code,
                operation=operation,
                from_revision=from_revision,
                status="started",
                triggered_by="system",
            )
        )
        db.commit()
    finally:
        db.close()
    return event_id


def _finish_migration_event(
    event_id: str,
    *,
    status: str,
    to_revision: str | None,
    error: str = "",
) -> None:
    db = get_control_session_factory()()
    try:
        event = db.get(TenantMigrationEvent, event_id)
        if event is None:
            return
        event.status = status
        event.to_revision = to_revision
        event.error = error[:8000]
        event.finished_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def _run_tenant_upgrade(company: TenantCompany, operation: str) -> None:
    """Run one tenant Alembic upgrade and persist its outcome."""
    database_url = resolve_tenant_database_url(company.database_secret_ref)
    from_revision = _current_tenant_revision(database_url)
    event_id = _start_migration_event(company, operation, from_revision)

    try:
        command.upgrade(_tenant_alembic_config(database_url), "head")
        to_revision = _current_tenant_revision(database_url)
        _finish_migration_event(
            event_id,
            status="succeeded",
            to_revision=to_revision,
        )
    except Exception as exc:
        _finish_migration_event(
            event_id,
            status="failed",
            to_revision=_current_tenant_revision(database_url),
            error=str(exc),
        )
        raise


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
    database_secret_ref = database_secret_ref.strip()
    if not database_secret_ref:
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
                "database_secret_ref": database_secret_ref,
            },
        )

    with company_migration_lock(company_id):
        try:
            if initialize_schema:
                db = get_control_session_factory()()
                try:
                    company = db.get(TenantCompany, company_id)
                finally:
                    db.close()
                if company is None:
                    raise RuntimeError(f"Company disappeared during provisioning: {company_id}")
                _run_tenant_upgrade(company, "provision")
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
    failed: list[str] = []

    with fleet_migration_lock():
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

        for company in companies:
            with company_migration_lock(company.id):
                try:
                    _run_tenant_upgrade(company, "fleet_migrate")
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
    with company_migration_lock(company_id):
        db = get_control_session_factory()()
        try:
            company = db.get(TenantCompany, company_id)
            if company is None:
                raise ValueError(f"Company not found: {company_id}")
            if company.provisioning_status != "failed":
                raise ValueError(
                    f"Company {company.code} is not failed; refusing recovery transition"
                )
            company.provisioning_status = "provisioning"
            company.active = False
            db.commit()
        finally:
            db.close()

        db = get_control_session_factory()()
        try:
            company = db.get(TenantCompany, company_id)
        finally:
            db.close()
        if company is None:
            raise ValueError(f"Company not found: {company_id}")

        try:
            _run_tenant_upgrade(company, "retry")
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
