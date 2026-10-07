"""Audit registered tenant Alembic revisions before production fleet upgrades.

This is a read-only preflight. It verifies that every active/ready tenant's
recorded Alembic revision exists in the deployed migration graph and is on the
current head path. It does not mutate tenant databases.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.db.control import get_control_session_factory
from app.db.control_models import TenantCompany
from app.services.tenant_credentials import resolve_tenant_database_url


@dataclass(frozen=True)
class TenantRevisionAudit:
    company_code: str
    company_id: str
    revision: str | None
    status: str
    detail: str = ""


def _script_directory() -> ScriptDirectory:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    return ScriptDirectory.from_config(config)


def _current_revision(database_url: str) -> str | None:
    engine = create_engine(database_url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            revisions = connection.execute(
                text("SELECT version_num FROM alembic_version ORDER BY version_num")
            ).scalars().all()
        return ",".join(str(revision) for revision in revisions) or None
    finally:
        engine.dispose()


def _revision_on_head_path(script: ScriptDirectory, revision: str) -> bool:
    if "," in revision:
        return all(_revision_on_head_path(script, item.strip()) for item in revision.split(","))
    script.get_revision(revision)
    head = script.get_current_head()
    return any(candidate.revision == revision for candidate in script.walk_revisions(head, revision))


def audit_ready_tenants() -> list[TenantRevisionAudit]:
    """Return a read-only compatibility report for all ready tenants."""
    script = _script_directory()
    db = get_control_session_factory()()
    try:
        companies = (
            db.query(TenantCompany)
            .filter(
                TenantCompany.active.is_(True),
                TenantCompany.provisioning_status == "ready",
            )
            .order_by(TenantCompany.code)
            .all()
        )
        snapshots = [
            (company.id, company.code, company.database_secret_ref)
            for company in companies
        ]
    finally:
        db.close()

    results: list[TenantRevisionAudit] = []
    for company_id, company_code, secret_ref in snapshots:
        try:
            database_url = resolve_tenant_database_url(secret_ref)
            revision = _current_revision(database_url)
            if revision is None:
                results.append(
                    TenantRevisionAudit(
                        company_code, company_id, None, "invalid", "alembic_version is empty or missing"
                    )
                )
                continue
            if not _revision_on_head_path(script, revision):
                results.append(
                    TenantRevisionAudit(
                        company_code,
                        company_id,
                        revision,
                        "invalid",
                        "revision is not on the current migration head path",
                    )
                )
                continue
            results.append(TenantRevisionAudit(company_code, company_id, revision, "ready"))
        except Exception as exc:
            results.append(
                TenantRevisionAudit(
                    company_code,
                    company_id,
                    None,
                    "error",
                    str(exc)[:8000],
                )
            )

    return results
