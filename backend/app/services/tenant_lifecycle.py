"""Safe tenant lifecycle transitions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from app.db.control import get_control_engine, get_control_session_factory
from app.db.control_models import TenantAdminEvent, TenantCompany
from app.services.secret_provider import get_secret_provider
from app.services.tenant_backup import TenantBackupError, backup_database
from app.services.tenant_migration_lock import company_migration_lock
from app.services.tenant_credentials import resolve_tenant_database_url


def _start_admin_event(
    company: TenantCompany,
    action: str,
    reason: str,
) -> str:
    event_id = str(uuid.uuid4())
    db = get_control_session_factory()()
    try:
        db.add(
            TenantAdminEvent(
                id=event_id,
                company_id=company.id,
                company_code=company.code,
                action=action,
                status="started",
                reason=reason,
            )
        )
        db.commit()
    finally:
        db.close()
    return event_id


def _finish_admin_event(
    event_id: str,
    *,
    status: str,
    error: str = "",
) -> None:
    db = get_control_session_factory()()
    try:
        event = db.get(TenantAdminEvent, event_id)
        if event is None:
            return
        event.status = status
        event.error = error[:8000]
        event.finished_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def decommission_company(
    company_id: str,
    backup_path: str | Path,
    *,
    reason: str,
) -> str:
    """Disable a tenant, prove a backup, then mark it permanently retired.

    The tenant database itself is deliberately not dropped. Physical destruction
    remains a separate operator-controlled action after restore validation and
    retention requirements have been satisfied.
    """
    reason = reason.strip()
    if not reason:
        raise ValueError("Decommission reason is required")

    with company_migration_lock(company_id):
        db = get_control_session_factory()()
        try:
            company = db.get(TenantCompany, company_id)
            if company is None:
                raise ValueError(f"Company not found: {company_id}")
            if company.provisioning_status == "decommissioned":
                raise ValueError(f"Company {company.code} is already decommissioned")
            if company.provisioning_status != "ready" or not company.active:
                raise ValueError(
                    f"Company {company.code} is not active/ready and cannot be decommissioned"
                )
            company.active = False
            company.provisioning_status = "decommissioning"
            company.decommission_reason = reason
            db.commit()
            company_id_local = company.id
            company_code = company.code
            secret_ref = company.database_secret_ref
        finally:
            db.close()

        event_id = _start_admin_event(
            TenantCompany(
                id=company_id_local,
                code=company_code,
                name=company_code,
                database_secret_ref=secret_ref,
            ),
            "decommission",
            reason,
        )

        try:
            database_url = resolve_tenant_database_url(secret_ref)
            backup_database(
                database_url,
                backup_path,
                company_code=company_code,
            )
        except Exception as exc:
            _finish_admin_event(
                event_id,
                status="failed",
                error=str(exc),
            )
            # The tenant stays inactive and in decommissioning state. This is
            # intentional: failed backup must never silently reactivate a tenant.
            raise

        db = get_control_session_factory()()
        try:
            company = db.get(TenantCompany, company_id_local)
            if company is None:
                raise RuntimeError(
                    f"Company disappeared during decommissioning: {company_id_local}"
                )
            company.active = False
            company.provisioning_status = "decommissioned"
            company.decommissioned_at = datetime.now(timezone.utc)
            company.decommission_reason = reason
            db.commit()
        finally:
            db.close()

        _finish_admin_event(event_id, status="succeeded")

    return company_id
