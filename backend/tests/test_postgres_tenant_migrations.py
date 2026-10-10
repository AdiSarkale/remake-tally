"""PostgreSQL integration coverage for database-per-company provisioning.

This test is skipped unless POSTGRES_TEST_ADMIN_URL and
CONTROL_DATABASE_URL are provided. CI creates the control database first,
runs control migrations, then executes this lifecycle test.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import psycopg
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import NullPool

from app.db.control_models import TenantAdminEvent, TenantCompany, TenantMigrationEvent
from app.db.control import get_control_session_factory
from app.services.tenant_migration_lock import build_lock_key, company_migration_lock
from app.services.tenant_backup import backup_database, restore_database
from app.services.tenant_lifecycle import decommission_company
from app.services.tenants import migrate_all_ready_tenants, register_company, retry_failed_company


def _psycopg_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def _admin_url() -> str:
    value = os.getenv("POSTGRES_TEST_ADMIN_URL")
    if not value:
        pytest.skip("POSTGRES_TEST_ADMIN_URL is not configured")
    return value


def _control_url() -> str:
    value = os.getenv("CONTROL_DATABASE_URL")
    if not value:
        pytest.skip("CONTROL_DATABASE_URL is not configured")
    return value


def _create_database(admin_url: str, name: str) -> None:
    with psycopg.connect(_psycopg_url(admin_url), autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')


def _drop_database(admin_url: str, name: str) -> None:
    with psycopg.connect(_psycopg_url(admin_url), autocommit=True) as conn:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (name,),
        )
        conn.execute(f'DROP DATABASE IF EXISTS "{name}"')


def test_postgres_tenant_backup_and_restore_round_trip():
    admin_url = _admin_url()
    marker = uuid.uuid4().hex[:10]
    source_name = f"minitally_backup_source_{marker}"
    restore_name = f"minitally_backup_restore_{marker}"
    source_url = admin_url.rsplit("/", 1)[0] + "/" + source_name
    restore_url = admin_url.rsplit("/", 1)[0] + "/" + restore_name

    _create_database(admin_url, source_name)
    _create_database(admin_url, restore_name)
    backup_path = Path(__file__).resolve().parent / f".tenant-backup-{marker}.dump"

    try:
        cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", source_url)
        command.upgrade(cfg, "head")

        engine = create_engine(source_url)
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE TABLE dr_round_trip_marker "
                        "(id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
                    )
                )
                connection.execute(
                    text(
                        "INSERT INTO dr_round_trip_marker (id, value) "
                        "VALUES (1, 'tenant-backup-ok')"
                    )
                )
        finally:
            engine.dispose()

        backup_database(source_url, backup_path, company_code="DRTEST")
        assert backup_path.is_file()
        assert backup_path.with_suffix(".dump.json").is_file()

        restore_database(
            restore_url,
            backup_path,
            expected_company_code="DRTEST",
        )

        engine = create_engine(restore_url)
        try:
            with engine.connect() as connection:
                value = connection.execute(
                    text(
                        "SELECT value FROM dr_round_trip_marker "
                        "WHERE id = 1"
                    )
                ).scalar_one()
            assert value == "tenant-backup-ok"
        finally:
            engine.dispose()
    finally:
        for path in (
            backup_path,
            backup_path.with_suffix(".dump.json"),
        ):
            path.unlink(missing_ok=True)
        for name in (source_name, restore_name):
            _drop_database(admin_url, name)


def test_postgres_company_migration_advisory_lock_serializes_processes():
    _control_url()
    marker = uuid.uuid4().hex[:10]
    company_id = f"lock-test-{marker}"
    lock_key = build_lock_key("tenant-migration", "company", company_id)

    with company_migration_lock(company_id):
        engine = create_engine(_control_url(), poolclass=NullPool)
        try:
            with engine.connect() as connection:
                acquired = connection.execute(
                    text(
                        "SELECT pg_try_advisory_lock("
                        "hashtextextended(:lock_key, 0)"
                        ")"
                    ),
                    {"lock_key": lock_key},
                ).scalar_one()
                assert acquired is False
        finally:
            engine.dispose()


def test_existing_tenant_upgrades_from_previous_head_to_current_head():
    """Prove an existing tenant at the previous migration head can reach head."""
    admin_url = _admin_url()
    marker = uuid.uuid4().hex[:10]
    database_name = f"minitally_upgrade_{marker}"
    database_url = admin_url.rsplit("/", 1)[0] + "/" + database_name

    _create_database(admin_url, database_name)
    try:
        cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(cfg, "8d4f6a1b2c3e")

        engine = create_engine(database_url)
        try:
            inspector = inspect(engine)
            assert "employees" in inspector.get_table_names()
            assert "employee_type" not in {
                column["name"] for column in inspector.get_columns("employees")
            }
        finally:
            engine.dispose()

        command.upgrade(cfg, "head")

        engine = create_engine(database_url)
        try:
            inspector = inspect(engine)
            employee_columns = {
                column["name"] for column in inspector.get_columns("employees")
            }
            assert "employee_type" in employee_columns

            with engine.connect() as connection:
                revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()

            assert revision == "hr_role_001"
        finally:
            engine.dispose()
    finally:
        _drop_database(admin_url, database_name)


def test_postgres_company_provisioning_and_fleet_migration():
    admin_url = _admin_url()
    control_url = _control_url()

    marker = uuid.uuid4().hex[:10]
    database_names = [f"minitally_tenant_{marker}_a", f"minitally_tenant_{marker}_b"]
    tenant_urls = []

    try:
        for name in database_names:
            _create_database(admin_url, name)
            tenant_urls.append(admin_url.rsplit("/", 1)[0] + "/" + name)

        company_ids = []
        for suffix, database_url in zip(("A", "B"), tenant_urls):
            secret_ref = f"PG{marker}{suffix}"
            os.environ[f"TENANT_DB_URL_{secret_ref}"] = database_url
            company_ids.append(
                register_company(
                    secret_ref,
                    f"PostgreSQL Company {suffix}",
                    secret_ref,
                    initialize_schema=True,
                )
            )

        control_factory = get_control_session_factory()
        control = control_factory()
        try:
            companies = (
                control.query(TenantCompany)
                .filter(TenantCompany.id.in_(company_ids))
                .order_by(TenantCompany.code)
                .all()
            )
            assert len(companies) == 2
            assert all(company.active for company in companies)
            assert all(company.provisioning_status == "ready" for company in companies)
            expected_secret_refs = {f"PG{marker}A", f"PG{marker}B"}
            assert {company.database_secret_ref for company in companies} == expected_secret_refs

            events = (
                control.query(TenantMigrationEvent)
                .filter(TenantMigrationEvent.company_id.in_(company_ids))
                .all()
            )
            assert len(events) == 2
            assert {event.operation for event in events} == {"provision"}
            assert all(event.status == "succeeded" for event in events)
            assert all(event.to_revision == "hr_role_001" for event in events)

            with psycopg.connect(_psycopg_url(control_url)) as control_connection:
                columns = {
                    row[0]
                    for row in control_connection.execute(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'tenant_companies'"
                    )
                }
                event_columns = {
                    row[0]
                    for row in control_connection.execute(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'tenant_migration_events'"
                    )
                }
            assert "database_secret_ref" in columns
            assert "database_url" not in columns
            assert {"company_id", "status", "from_revision", "to_revision"}.issubset(event_columns)
        finally:
            control.close()

        for database_url in tenant_urls:
            engine = create_engine(database_url)
            try:
                inspector = inspect(engine)
                tables = set(inspector.get_table_names())
                assert "users" in tables
                assert "products" in tables
                assert "parties" in tables
                assert "alembic_version" in tables

                with engine.connect() as connection:
                    revision = connection.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalar_one()
                assert revision
            finally:
                engine.dispose()

        migrated = migrate_all_ready_tenants()
        expected_codes = {f"PG{marker}A".upper(), f"PG{marker}B".upper()}
        assert expected_codes.issubset(set(migrated))

        control = control_factory()
        try:
            fleet_events = (
                control.query(TenantMigrationEvent)
                .filter(TenantMigrationEvent.company_id.in_(company_ids))
                .all()
            )
            assert sum(event.operation == "fleet_migrate" for event in fleet_events) == 2
        finally:
            control.close()

        control = control_factory()
        try:
            first = control.query(TenantCompany).filter_by(code=f"PG{marker}A".upper()).one()
            first.active = False
            first.provisioning_status = "failed"
            failed_id = first.id
            control.commit()
        finally:
            control.close()

        retry_failed_company(failed_id)

        control = control_factory()
        try:
            recovered = control.get(TenantCompany, failed_id)
            assert recovered.active is True
            assert recovered.provisioning_status == "ready"

            retry_events = (
                control.query(TenantMigrationEvent)
                .filter(
                    TenantMigrationEvent.company_id == failed_id,
                    TenantMigrationEvent.operation == "retry",
                )
                .all()
            )
            assert len(retry_events) == 1
            assert retry_events[0].status == "succeeded"
            assert retry_events[0].to_revision == "employee_type_001"
        finally:
            control.close()

        decommission_backup = Path(__file__).resolve().parent / f".tenant-decommission-{marker}.dump"
        decommission_company(
            company_ids[1],
            decommission_backup,
            reason="CI disaster-recovery lifecycle validation",
        )
        assert decommission_backup.is_file()

        control = control_factory()
        try:
            retired = control.get(TenantCompany, company_ids[1])
            assert retired is not None
            assert retired.active is False
            assert retired.provisioning_status == "decommissioned"
            assert retired.decommissioned_at is not None
            assert retired.decommission_reason == "CI disaster-recovery lifecycle validation"

            lifecycle_events = (
                control.query(TenantAdminEvent)
                .filter(
                    TenantAdminEvent.company_id == company_ids[1],
                    TenantAdminEvent.action == "decommission",
                )
                .all()
            )
            assert len(lifecycle_events) == 1
            assert lifecycle_events[0].status == "succeeded"
        finally:
            control.close()

        decommission_backup.unlink(missing_ok=True)
        decommission_backup.with_suffix(".dump.json").unlink(missing_ok=True)

    finally:
        for suffix in ("A", "B"):
            os.environ.pop(f"TENANT_DB_URL_PG{marker}{suffix}", None)
        for name in database_names:
            _drop_database(admin_url, name)


def test_postgres_control_secret_ref_migration_preserves_existing_tenants():
    admin_url = _admin_url()
    marker = uuid.uuid4().hex[:10]
    database_name = f"minitally_control_migration_{marker}"
    control_url = admin_url.rsplit("/", 1)[0] + "/" + database_name
    secret_ref = f"LEGACY{marker.upper()}"

    _create_database(admin_url, database_name)
    try:
        os.environ[f"TENANT_DB_URL_{secret_ref}"] = "postgresql+psycopg://example/tenant"

        cfg = Config(str(Path(__file__).resolve().parents[1] / "control_alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", control_url)
        command.upgrade(cfg, "control_002")

        with psycopg.connect(_psycopg_url(control_url), autocommit=True) as connection:
            connection.execute(
                """
                INSERT INTO tenant_companies
                    (id, code, name, database_url, active, provisioning_status)
                VALUES
                    (%s, %s, %s, %s, TRUE, 'ready')
                """,
                (
                    str(uuid.uuid4()),
                    f"legacy{marker}",
                    "Legacy Company",
                    "postgresql+psycopg://legacy-user:legacy-password@db.example/legacy",
                ),
            )

        command.upgrade(cfg, "head")

        with psycopg.connect(_psycopg_url(control_url)) as connection:
            row = connection.execute(
                "SELECT code, database_secret_ref FROM tenant_companies"
            ).fetchone()
            columns = {
                item[0]
                for item in connection.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'tenant_companies'"
                )
            }

        assert row == (f"legacy{marker}", f"LEGACY{marker.upper()}")
        assert "database_secret_ref" in columns
        assert "database_url" not in columns
    finally:
        os.environ.pop(f"TENANT_DB_URL_{secret_ref}", None)
        _drop_database(admin_url, database_name)
