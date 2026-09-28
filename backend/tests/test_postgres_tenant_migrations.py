"""PostgreSQL integration coverage for database-per-company provisioning.

This test is skipped unless POSTGRES_TEST_ADMIN_URL and
CONTROL_DATABASE_URL are provided. CI creates the control database first,
runs control migrations, then executes this lifecycle test.
"""

from __future__ import annotations

import os
import uuid

import pytest
import psycopg
from sqlalchemy import create_engine, inspect, text

from app.db.control_models import TenantCompany
from app.db.control import get_control_session_factory
from app.services.tenants import migrate_all_ready_tenants, register_company


pytestmark = pytest.mark.integration


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
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')


def _drop_database(admin_url: str, name: str) -> None:
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (name,),
        )
        conn.execute(f'DROP DATABASE IF EXISTS "{name}"')


def test_postgres_company_provisioning_and_fleet_migration():
    admin_url = _admin_url()
    control_url = _control_url()
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
            assert all(company.database_secret_ref == company.code for company in companies)

            with psycopg.connect(control_url) as control_connection:
                columns = {
                    row[0]
                    for row in control_connection.execute(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'tenant_companies'"
                    )
                }
            assert "database_secret_ref" in columns
            assert "database_url" not in columns
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
        assert all(code in migrated for code in (f"PG{marker}A", f"PG{marker}B"))

    finally:
        for suffix in ("A", "B"):
            os.environ.pop(f"TENANT_DB_URL_PG{marker}{suffix}", None)
        for name in database_names:
            _drop_database(admin_url, name)
