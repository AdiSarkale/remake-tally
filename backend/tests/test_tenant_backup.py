"""Unit coverage for tenant backup safety and manifest validation."""

from __future__ import annotations

import json

import pytest

from app.services.tenant_backup import TenantBackupError, restore_database


def test_restore_rejects_missing_backup():
    with pytest.raises(TenantBackupError, match="does not exist"):
        restore_database(
            "postgresql+psycopg://user:pass@localhost/target",
            "/tmp/does-not-exist.dump",
        )


def test_restore_rejects_tampered_manifest(tmp_path):
    backup = tmp_path / "tenant.dump"
    backup.write_bytes(b"backup-bytes")
    manifest = backup.with_suffix(".dump.json")
    manifest.write_text(
        json.dumps(
            {
                "format": "postgresql-custom",
                "company_code": "ACME",
                "sha256": "deadbeef",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(TenantBackupError, match="checksum"):
        restore_database(
            "postgresql+psycopg://user:pass@localhost/target",
            backup,
        )


def test_restore_rejects_cross_company_manifest(tmp_path):
    backup = tmp_path / "tenant.dump"
    backup.write_bytes(b"backup-bytes")

    from hashlib import sha256

    checksum = sha256(backup.read_bytes()).hexdigest()
    backup.with_suffix(".dump.json").write_text(
        json.dumps(
            {
                "format": "postgresql-custom",
                "company_code": "OTHER",
                "sha256": checksum,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(TenantBackupError, match="does not match"):
        restore_database(
            "postgresql+psycopg://user:pass@localhost/target",
            backup,
            expected_company_code="ACME",
        )
