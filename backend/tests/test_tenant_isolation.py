"""Integration tests for database-per-company tenant isolation.

These tests use two independent SQLite tenant databases and one control DB.
The production code uses PostgreSQL URLs; SQLite keeps the suite deterministic
and self-contained for CI.
"""

from pathlib import Path

import pytest
import app.api.deps as deps
import app.api.routes.auth as auth_routes
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.db import session as tenant_session
from app.db.control_models import ControlBase, TenantCompany
from app.db.control import get_control_db
from app.db.tenant import get_tenant_db
from app.core.security import hash_password
from app.main import app


@pytest.fixture()
def tenant_environment(tmp_path: Path):
    control_engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    tenant_a_engine = create_engine(f"sqlite:///{tmp_path / 'company_a.db'}")
    tenant_b_engine = create_engine(f"sqlite:///{tmp_path / 'company_b.db'}")

    ControlBase.metadata.create_all(control_engine)
    models.Base.metadata.create_all(tenant_a_engine)
    models.Base.metadata.create_all(tenant_b_engine)

    ControlSession = sessionmaker(bind=control_engine)
    TenantASession = sessionmaker(bind=tenant_a_engine)
    TenantBSession = sessionmaker(bind=tenant_b_engine)

    control = ControlSession()
    company_a = TenantCompany(id="company-a", code="A", name="Company A", database_url=f"sqlite:///{tmp_path / 'company_a.db'}")
    company_b = TenantCompany(id="company-b", code="B", name="Company B", database_url=f"sqlite:///{tmp_path / 'company_b.db'}")
    control.add_all([company_a, company_b])
    control.commit()

    for Session, company in ((TenantASession, company_a), (TenantBSession, company_b)):
        db = Session()
        db.add(models.User(
            username="admin",
            full_name=f"{company.name} Admin",
            password_hash=hash_password("Password@123"),
            role=models.Role.admin,
            active=True,
            must_change_password=False,
        ))
        db.commit()
        db.close()

    def override_control_db():
        db = ControlSession()
        try:
            yield db
        finally:
            db.close()

    def tenant_db_for(company):
        return TenantASession() if company.id == "company-a" else TenantBSession()

    deps.get_tenant_db = tenant_db_for
    auth_routes.get_tenant_db = tenant_db_for
    app.dependency_overrides[get_control_db] = override_control_db
    yield {
        "control": control,
        "companies": (company_a, company_b),
        "tenant_sessions": (TenantASession, TenantBSession),
    }

    app.dependency_overrides.clear()
    control.close()


def test_same_username_isolated_by_company(tenant_environment):
    client = TestClient(app)

    a = client.post("/api/v1/auth/login", json={
        "company_code": "A", "username": "admin", "password": "Password@123"
    })
    b = client.post("/api/v1/auth/login", json={
        "company_code": "B", "username": "admin", "password": "Password@123"
    })

    assert a.status_code == 200
    assert b.status_code == 200
    assert a.json()["company_id"] == "company-a"
    assert b.json()["company_id"] == "company-b"
    assert a.json()["company_id"] != b.json()["company_id"]


def test_invalid_company_cannot_authenticate(tenant_environment):
    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={
        "company_code": "NOT-REAL", "username": "admin", "password": "Password@123"
    })
    assert response.status_code == 401


def test_deactivated_company_cannot_authenticate(tenant_environment):
    client = TestClient(app)
    control = tenant_environment["control"]
    company = tenant_environment["companies"][0]
    company.active = False
    control.commit()

    response = client.post("/api/v1/auth/login", json={
        "company_code": "A", "username": "admin", "password": "Password@123"
    })
    assert response.status_code == 401
