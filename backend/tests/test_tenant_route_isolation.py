"""Regression tests for runtime tenant isolation across ERP API modules.

The important distinction from the original tenant tests is that these requests
exercise app.db.session.get_db, which is the dependency imported by the ERP
route modules. That proves the HTTP route layer, not only authentication, is
resolved against the JWT-selected tenant database.
"""

from pathlib import Path
import sys

# Allow the suite to run both from the repository root and from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.api.deps as deps
import app.api.routes.auth as auth_routes
import app.db.session as session_module
from app import models
from app.db.control import get_control_db
from app.db.control_models import ControlBase, TenantCompany
from app.main import app
from app.core.security import hash_password


@pytest.fixture()
def isolated_tenants(tmp_path: Path, monkeypatch):
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
    company_a = TenantCompany(
        id="company-a",
        code="AA",
        name="Company A",
        database_url=f"sqlite:///{tmp_path / 'company_a.db'}",
        active=True,
        provisioning_status="ready",
    )
    company_b = TenantCompany(
        id="company-b",
        code="BB",
        name="Company B",
        database_url=f"sqlite:///{tmp_path / 'company_b.db'}",
        active=True,
        provisioning_status="ready",
    )
    control.add_all([company_a, company_b])
    control.commit()

    def seed(Session, company_label: str, suffix: str):
        db = Session()
        user = models.User(
            username="admin",
            full_name=f"{company_label} Admin",
            password_hash=hash_password("Password@123"),
            role=models.Role.admin,
            active=True,
            must_change_password=False,
        )
        customer = models.Party(
            id=f"customer-{suffix}",
            kind="customer",
            name=f"{company_label} Customer",
        )
        supplier = models.Party(
            id=f"supplier-{suffix}",
            kind="supplier",
            name=f"{company_label} Supplier",
        )
        product = models.Product(
            id=f"product-{suffix}",
            code=f"FG-{suffix}",
            name=f"${company_label} Product",
            cost_price=10 if suffix == "a" else 20,
            stock=10 if suffix == "a" else 20,
        )
        material = models.RawMaterial(
            id=f"material-{suffix}",
            code=f"RM-{suffix}",
            name=f"${company_label} Material",
            cost=5 if suffix == "a" else 15,
            stock=5 if suffix == "a" else 15,
        )
        invoice = models.Invoice(
            id=f"invoice-{suffix}",
            invoice_no=f"INV-{suffix.upper()}",
            invoice_date=__import__("datetime").date(2026, 9, 28),
            customer_id=customer.id,
            customer_name=customer.name,
            grand_total=100 if suffix == "a" else 200,
            balance_amount=100 if suffix == "a" else 200,
            status=models.InvoiceStatus.unpaid,
            created_by="admin",
        )
        requisition = models.PurchaseRequisition(
            id=f"pr-{suffix}",
            pr_no=f"PR-{suffix.upper()}",
            pr_date=__import__("datetime").date(2026, 9, 28),
            requested_by="admin",
            created_by="admin",
            status=models.PurchaseRequisitionStatus.draft,
        )
        payment = models.CustomerPayment(
            id=f"payment-{suffix}",
            payment_no=f"CPAY-{suffix.upper()}",
            payment_date=__import__("datetime").date(2026, 9, 28),
            customer_id=customer.id,
            customer_name=customer.name,
            amount=10 if suffix == "a" else 20,
            created_by="admin",
        )
        db.add_all([user, customer, supplier, product, material, invoice, requisition, payment])
        db.commit()
        db.close()

    seed(TenantASession, "Company A", "a")
    seed(TenantBSession, "Company B", "b")

    def tenant_db_for(company: TenantCompany):
        factory = TenantASession if company.id == "company-a" else TenantBSession
        return factory()

    def override_control_db():
        db = ControlSession()
        try:
            yield db
        finally:
            db.close()

    # Authentication dependency and route DB dependency use different module
    # globals, so both are patched deliberately.
    monkeypatch.setattr(deps, "get_tenant_db", tenant_db_for)
    monkeypatch.setattr(auth_routes, "get_tenant_db", tenant_db_for)
    monkeypatch.setattr(session_module, "get_tenant_db", tenant_db_for)
    app.dependency_overrides[get_control_db] = override_control_db

    yield {
        "client": TestClient(app),
        "sessions": (TenantASession, TenantBSession),
    }

    app.dependency_overrides.clear()
    control.close()


def _login(client: TestClient, company_code: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "company_code": company_code,
            "username": "admin",
            "password": "Password@123",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_route_db_dependency_is_tenant_scoped(isolated_tenants):
    client = isolated_tenants["client"]
    a = _login(client, "AA")
    b = _login(client, "BB")

    a_headers = {"Authorization": f"Bearer {a['access_token']}"}
    b_headers = {"Authorization": f"Bearer {b['access_token']}"}

    checks = [
        ("/api/v1/masters/customers", lambda rows: [r["name"] for r in rows], "Company A Customer", "Company B Customer"),
        ("/api/v1/masters/suppliers", lambda rows: [r["name"] for r in rows], "Company A Supplier", "Company B Supplier"),
        ("/api/v1/masters/products", lambda rows: [r["code"] for r in rows], "FG-a", "FG-b"),
        ("/api/v1/masters/materials", lambda rows: [r["code"] for r in rows], "RM-a", "RM-b"),
        ("/api/v1/sales/invoices", lambda rows: [r["invoice_no"] for r in rows], "INV-A", "INV-B"),
        ("/api/v1/purchasing/requisitions", lambda rows: [r["pr_no"] for r in rows], "PR-A", "PR-B"),
        ("/api/v1/finance/customer-payments", lambda rows: [r["payment_no"] for r in rows], "CPAY-A", "CPAY-B"),
    ]

    for path, extract, expected_a, expected_b in checks:
        a_response = client.get(path, headers=a_headers)
        b_response = client.get(path, headers=b_headers)
        assert a_response.status_code == 200, f"{path}: {a_response.text}"
        assert b_response.status_code == 200, f"{path}: {b_response.text}"

        a_values = extract(a_response.json())
        b_values = extract(b_response.json())

        assert a_values
        assert b_values
        assert expected_a in a_values
        assert expected_b in b_values
        assert expected_b not in a_values
        assert expected_a not in b_values
        assert set(a_values).isdisjoint(b_values)


def test_aggregate_routes_are_tenant_scoped(isolated_tenants):
    client = isolated_tenants["client"]
    a = _login(client, "AA")
    b = _login(client, "BB")

    a_headers = {"Authorization": f"Bearer {a['access_token']}"}
    b_headers = {"Authorization": f"Bearer {b['access_token']}"}

    valuation_a = client.get("/api/v1/inventory/valuation", headers=a_headers)
    valuation_b = client.get("/api/v1/inventory/valuation", headers=b_headers)
    assert valuation_a.status_code == 200
    assert valuation_b.status_code == 200
    assert valuation_a.json()["total"] != valuation_b.json()["total"]

    dashboard_a = client.get("/api/v1/dashboard", headers=a_headers)
    dashboard_b = client.get("/api/v1/dashboard", headers=b_headers)
    assert dashboard_a.status_code == 200
    assert dashboard_b.status_code == 200
    assert dashboard_a.json()["finished_goods_value"] != dashboard_b.json()["finished_goods_value"]
    assert dashboard_a.json()["raw_material_value"] != dashboard_b.json()["raw_material_value"]


def _dependency_calls(dependant):
    yield from dependant.dependencies
    for child in dependant.dependencies:
        yield from _dependency_calls(child)


def test_db_backed_api_routes_use_canonical_tenant_dependency():
    expected = session_module.get_db
    excluded_prefixes = (
        "/api/v1/auth/login",
        "/api/v1/auth/me",
        "/api/v1/users/me/change-password",
    )

    missing = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/v1/"):
            continue
        if route.path in excluded_prefixes:
            continue

        calls = {dep.call for dep in _dependency_calls(route.dependant)}
        if expected not in calls:
            missing.append(route.path)

    assert missing == [], f"Routes bypass canonical tenant DB dependency: {missing}"
