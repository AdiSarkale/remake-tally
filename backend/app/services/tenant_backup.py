"""Tenant database backup and restore primitives.

Backups are created in PostgreSQL custom format so they can be restored with
pg_restore. Database credentials are resolved at runtime and are never written
to the control plane or backup manifest.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from app.services.tenant_credentials import resolve_tenant_database_url


class TenantBackupError(RuntimeError):
    """Raised when tenant backup or restore cannot be completed."""


def _command_url(database_url: str) -> tuple[str, str | None]:
    """Return a libpq PostgreSQL URL and an optional password environment value."""
    try:
        url = make_url(database_url)
    except Exception as exc:
        raise TenantBackupError("Invalid tenant PostgreSQL URL") from exc

    if url.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise TenantBackupError("Tenant backup requires PostgreSQL")

    password = url.password
    safe_url = url.set(drivername="postgresql", password=None).render_as_string(
        hide_password=False
    )
    return safe_url, password


def _run_pg_command(
    args: list[str],
    *,
    database_url: str,
    failure_prefix: str,
) -> None:
    safe_url, password = _command_url(database_url)
    command = [arg.replace("__DATABASE_URL__", safe_url) for arg in args]

    env = os.environ.copy()
    if password is not None:
        env["PGPASSWORD"] = password

    try:
        completed = subprocess.run(
            command,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise TenantBackupError(
            f"{failure_prefix}: PostgreSQL client utility is not installed"
        ) from exc
    except OSError as exc:
        raise TenantBackupError(f"{failure_prefix}: {exc}") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise TenantBackupError(
            f"{failure_prefix} (exit {completed.returncode})"
            + (f": {detail[-2000:]}" if detail else "")
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def current_revision(database_url: str) -> str | None:
    """Read the tenant Alembic revision before creating a backup."""
    engine = create_engine(database_url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            revisions = connection.execute(
                text("SELECT version_num FROM alembic_version ORDER BY version_num")
            ).scalars().all()
        return ",".join(str(revision) for revision in revisions) or None
    except Exception:
        return None
    finally:
        engine.dispose()


def write_manifest(
    backup_path: Path,
    *,
    company_code: str,
    revision: str | None,
) -> Path:
    manifest = backup_path.with_suffix(backup_path.suffix + ".json")
    payload: dict[str, Any] = {
        "format": "postgresql-custom",
        "company_code": company_code.upper(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": revision,
        "sha256": _sha256(backup_path),
    }
    manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return manifest


def backup_database(
    database_url: str,
    output_path: str | Path,
    *,
    company_code: str,
) -> Path:
    """Create a PostgreSQL custom-format backup and an integrity manifest."""
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    revision = current_revision(database_url)
    _run_pg_command(
        [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--file",
            str(path),
            "--dbname",
            "__DATABASE_URL__",
        ],
        database_url=database_url,
        failure_prefix=f"Tenant backup failed for {company_code.upper()}",
    )

    if not path.is_file() or path.stat().st_size == 0:
        raise TenantBackupError("Tenant backup completed without producing a non-empty file")

    write_manifest(path, company_code=company_code, revision=revision)
    return path


def backup_registered_tenant(
    company_code: str,
    output_path: str | Path,
) -> Path:
    """Resolve an active ready tenant and back it up."""
    from app.db.control import get_control_session_factory
    from app.db.control_models import TenantCompany

    code = company_code.strip().upper()
    db = get_control_session_factory()()
    try:
        company = (
            db.query(TenantCompany)
            .filter_by(code=code)
            .one_or_none()
        )
        if company is None:
            raise TenantBackupError(f"Company not found: {code}")
        if not company.active or company.provisioning_status != "ready":
            raise TenantBackupError(f"Company is not active/ready: {code}")
        database_secret_ref = company.database_secret_ref
    finally:
        db.close()

    database_url = resolve_tenant_database_url(database_secret_ref)
    return backup_database(database_url, output_path, company_code=code)


def restore_database(
    database_url: str,
    backup_path: str | Path,
    *,
    expected_company_code: str | None = None,
) -> None:
    """Restore a custom-format PostgreSQL backup into a target database."""
    path = Path(backup_path).expanduser().resolve()
    if not path.is_file():
        raise TenantBackupError(f"Backup file does not exist: {path}")

    manifest = path.with_suffix(path.suffix + ".json")
    if manifest.is_file():
        try:
            metadata = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise TenantBackupError(f"Invalid backup manifest: {manifest}") from exc

        actual_checksum = _sha256(path)
        if metadata.get("sha256") != actual_checksum:
            raise TenantBackupError("Backup checksum does not match its manifest")

        if expected_company_code:
            manifest_code = str(metadata.get("company_code", "")).upper()
            if manifest_code != expected_company_code.strip().upper():
                raise TenantBackupError(
                    "Backup company does not match the requested restore company"
                )

    _run_pg_command(
        [
            "pg_restore",
            "--exit-on-error",
            "--no-owner",
            "--no-privileges",
            "--dbname",
            "__DATABASE_URL__",
            str(path),
        ],
        database_url=database_url,
        failure_prefix="Tenant restore failed",
    )


def restore_registered_tenant(
    company_code: str,
    backup_path: str | Path,
    target_database_url: str,
) -> None:
    """Restore a tenant backup into an explicitly supplied target database."""
    if company_code.strip() == "":
        raise TenantBackupError("Company code is required for restore validation")
    restore_database(
        target_database_url,
        backup_path,
        expected_company_code=company_code,
    )
