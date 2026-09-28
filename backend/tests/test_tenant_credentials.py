"""Tests for tenant database secret-reference resolution."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.tenant_credentials import resolve_tenant_database_url


def test_secret_reference_resolves_from_runtime_secret(monkeypatch):
    monkeypatch.setenv("TENANT_DB_URL_ACME", "postgresql+psycopg://user:pass@db/acme")
    assert resolve_tenant_database_url("ACME") == "postgresql+psycopg://user:pass@db/acme"


def test_missing_secret_reference_fails_closed(monkeypatch):
    monkeypatch.delenv("TENANT_DB_URL_MISSING", raising=False)
    with pytest.raises(RuntimeError, match="unavailable"):
        resolve_tenant_database_url("MISSING")


def test_local_default_is_development_only(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv(
        "CONTROL_DATABASE_URL",
        "postgresql+psycopg://user:pass@control/control",
    )
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="unavailable"):
            resolve_tenant_database_url("LOCAL_DEFAULT")
    finally:
        get_settings.cache_clear()
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("JWT_SECRET", raising=False)
        monkeypatch.delenv("CONTROL_DATABASE_URL", raising=False)
