"""Regression tests for targeting demo seeds at the routed tenant database."""

from types import SimpleNamespace

import app.seed as seed


class _FakeQuery:
    def __init__(self, row):
        self.row = row

    def filter_by(self, **filters):
        assert filters == {"code": "SPW"}
        return self

    def first(self):
        return self.row


class _FakeControlSession:
    def __init__(self, row):
        self.row = row
        self.closed = False

    def query(self, _model):
        return _FakeQuery(self.row)

    def close(self):
        self.closed = True


def test_seed_uses_database_resolved_from_spw_tenant_secret(monkeypatch):
    company = SimpleNamespace(
        code="SPW",
        active=True,
        provisioning_status="ready",
        database_secret_ref="SPW_LOCAL_DB",
    )
    control_session = _FakeControlSession(company)
    monkeypatch.setattr(seed, "_ensure_demo_tenant", lambda: None)
    monkeypatch.setattr(
        "app.db.control.get_control_session_factory",
        lambda: lambda: control_session,
    )
    resolved_urls = []

    def resolve_secret(secret_ref):
        resolved_urls.append(secret_ref)
        return "sqlite+pysqlite:///:memory:"

    monkeypatch.setattr(
        "app.services.tenant_credentials.resolve_tenant_database_url",
        resolve_secret,
    )

    tenant_code, tenant_engine, session_factory = seed._demo_tenant_database()
    try:
        assert tenant_code == "SPW"
        assert resolved_urls == ["SPW_LOCAL_DB"]
        assert tenant_engine.url.drivername == "sqlite+pysqlite"
        assert session_factory.kw["bind"] is tenant_engine
        assert control_session.closed is True
    finally:
        tenant_engine.dispose()
