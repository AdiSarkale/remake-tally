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
import app.db.control_models as models_control
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
        database_secret_ref="LOCAL_A",
        active=True,
        provisioning_status="ready",
    )
    company_b = TenantCompany(
        id="company-b",
        code="BB",
        name="Company B",
        database_secret_ref="LOCAL_B",
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
        "control_session": ControlSession,
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


def test_company_write_operations_stay_in_selected_tenant(isolated_tenants):
    client = isolated_tenants["client"]
    sessions = isolated_tenants["sessions"]
    a = _login(client, "AA")
    b = _login(client, "BB")
    a_headers = {"Authorization": f"Bearer {a["access_token"]}"}
    b_headers = {"Authorization": f"Bearer {b["access_token"]}"}

    created = client.post(
        "/api/v1/masters/customers",
        headers=a_headers,
        json={"name": "A-only Customer"},
    )
    assert created.status_code == 201, created.text
    customer_id = created.json()["id"]

    a_db, b_db = sessions
    assert a_db().get(models.Party, customer_id).name == "A-only Customer"
    assert b_db().get(models.Party, customer_id) is None

    cross_tenant_update = client.put(
        f"/api/v1/masters/customers/{customer_id}",
        headers=b_headers,
        json={"name": "B attempted takeover"},
    )
    assert cross_tenant_update.status_code == 404

    cross_tenant_delete = client.delete(
        f"/api/v1/masters/customers/{customer_id}",
        headers=b_headers,
    )
    assert cross_tenant_delete.status_code == 404

    assert a_db().get(models.Party, customer_id).name == "A-only Customer"
    assert b_db().get(models.Party, customer_id) is None


def test_inactive_or_non_ready_company_cannot_login(isolated_tenants):
    client = isolated_tenants["client"]
    ControlSession = isolated_tenants["control_session"]

    db = ControlSession()
    company_b = db.get(models_control.TenantCompany, "company-b")
    company_b.active = False
    db.commit()
    db.close()

    inactive = client.post(
        "/api/v1/auth/login",
        json={"company_code": "BB", "username": "admin", "password": "Password@123"},
    )
    assert inactive.status_code == 401

    db = ControlSession()
    company_b = db.get(models_control.TenantCompany, "company-b")
    company_b.active = True
    company_b.provisioning_status = "provisioning"
    db.commit()
    db.close()

    not_ready = client.post(
        "/api/v1/auth/login",
        json={"company_code": "BB", "username": "admin", "password": "Password@123"},
    )
    assert not_ready.status_code == 401


def test_first_login_requires_password_change_and_then_unlocks_access(isolated_tenants):
    client = isolated_tenants["client"]
    TenantASession = isolated_tenants["sessions"][0]

    db = TenantASession()
    db.add(
        models.User(
            username="firstlogin",
            full_name="First Login",
            password_hash=hash_password("Initial@123"),
            role=models.Role.operator,
            active=True,
            must_change_password=True,
        )
    )
    db.commit()
    db.close()

    login = client.post(
        "/api/v1/auth/login",
        json={"company_code": "AA", "username": "firstlogin", "password": "Initial@123"},
    )
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True
    headers = {"Authorization": f"Bearer {login.json()["access_token"]}"}

    blocked = client.get("/api/v1/masters/products", headers=headers)
    assert blocked.status_code == 403

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200

    changed = client.post(
        "/api/v1/users/me/change-password",
        headers=headers,
        json={"current_password": "Initial@123", "new_password": "Changed@123"},
    )
    assert changed.status_code == 204

    unlocked = client.get("/api/v1/inventory/valuation", headers=headers)
    assert unlocked.status_code == 200


def test_only_admin_can_reset_passwords(isolated_tenants):
    client = isolated_tenants["client"]
    TenantASession = isolated_tenants["sessions"][0]

    db = TenantASession()
    operator = models.User(
        username="operator",
        full_name="Operator",
        password_hash=hash_password("Operator@123"),
        role=models.Role.operator,
        active=True,
        must_change_password=False,
    )
    target = models.User(
        username="target",
        full_name="Target",
        password_hash=hash_password("Target@123"),
        role=models.Role.operator,
        active=True,
        must_change_password=False,
    )
    db.add_all([operator, target])
    db.commit()
    target_id = target.id
    db.close()

    operator_login = _login(client, "AA")  # admin token is used below for the positive path
    operator_response = client.post(
        "/api/v1/users/me/change-password",
        headers={"Authorization": f"Bearer {operator_login["access_token"]}"},
        json={"current_password": "Password@123", "new_password": "Changed@123"},
    )
    assert operator_response.status_code == 204

    # A real operator token must not be able to invoke admin password reset.
    login = client.post(
        "/api/v1/auth/login",
        json={"company_code": "AA", "username": "operator", "password": "Operator@123"},
    )
    assert login.status_code == 200
    operator_headers = {"Authorization": f"Bearer {login.json()["access_token"]}"}

    forbidden = client.post(
        f"/api/v1/users/{target_id}/reset-password",
        headers=operator_headers,
        json={"new_password": "Reset@123"},
    )
    assert forbidden.status_code == 403

    admin_headers = {"Authorization": f"Bearer {operator_login["access_token"]}"}
    allowed = client.post(
        f"/api/v1/users/{target_id}/reset-password",
        headers=admin_headers,
        json={"new_password": "Reset@123"},
    )
    assert allowed.status_code == 204

    target_login = client.post(
        "/api/v1/auth/login",
        json={"company_code": "AA", "username": "target", "password": "Reset@123"},
    )
    assert target_login.status_code == 200
    assert target_login.json()["must_change_password"] is True


def test_operator_and_accountant_have_inventory_and_purchase_request_access(isolated_tenants):
    client = isolated_tenants["client"]
    TenantASession = isolated_tenants["sessions"][0]

    db = TenantASession()
    db.add(
        models.User(
            username="accountant",
            full_name="Accountant",
            password_hash=hash_password("Accountant@123"),
            role=models.Role.accountant,
            active=True,
            must_change_password=False,
        )
    )
    db.add(
        models.User(
            username="operator2",
            full_name="Operator 2",
            password_hash=hash_password("Operator2@123"),
            role=models.Role.operator,
            active=True,
            must_change_password=False,
        )
    )
    db.commit()
    db.close()

    for username, password in (
        ("accountant", "Accountant@123"),
        ("operator2", "Operator2@123"),
    ):
        login = client.post(
            "/api/v1/auth/login",
            json={"company_code": "AA", "username": username, "password": password},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()["access_token"]}"}

        inventory = client.get("/api/v1/inventory/valuation", headers=headers)
        requisitions = client.get("/api/v1/purchasing/requisitions", headers=headers)
        assert inventory.status_code == 200
        assert requisitions.status_code == 200


def test_company_write_operations_stay_in_selected_tenant(isolated_tenants):
    client = isolated_tenants["client"]
    sessions = isolated_tenants["sessions"]
    a = _login(client, "AA")
    b = _login(client, "BB")
    a_headers = {"Authorization": f"Bearer {a['access_token']}"}
    b_headers = {"Authorization": f"Bearer {b['access_token']}"}

    created = client.post("/api/v1/masters/customers", headers=a_headers, json={"name": "A-only Customer"})
    assert created.status_code == 201, created.text
    customer_id = created.json()["id"]

    a_db, b_db = sessions
    a_check = a_db()
    b_check = b_db()
    try:
        assert a_check.get(models.Party, customer_id).name == "A-only Customer"
        assert b_check.get(models.Party, customer_id) is None
    finally:
        a_check.close()
        b_check.close()

    cross_tenant_update = client.put(
        f"/api/v1/masters/customers/{customer_id}",
        headers=b_headers,
        json={"name": "B attempted takeover"},
    )
    assert cross_tenant_update.status_code == 404

    cross_tenant_delete = client.delete(f"/api/v1/masters/customers/{customer_id}", headers=b_headers)
    assert cross_tenant_delete.status_code == 404


def test_inactive_or_non_ready_company_cannot_login(isolated_tenants):
    client = isolated_tenants["client"]
    ControlSession = isolated_tenants["control_session"]

    db = ControlSession()
    company_b = db.get(models_control.TenantCompany, "company-b")
    company_b.active = False
    db.commit()
    db.close()

    inactive = client.post("/api/v1/auth/login", json={
        "company_code": "BB", "username": "admin", "password": "Password@123"
    })
    assert inactive.status_code == 401

    db = ControlSession()
    company_b = db.get(models_control.TenantCompany, "company-b")
    company_b.active = True
    company_b.provisioning_status = "provisioning"
    db.commit()
    db.close()

    not_ready = client.post("/api/v1/auth/login", json={
        "company_code": "BB", "username": "admin", "password": "Password@123"
    })
    assert not_ready.status_code == 401


def test_first_login_requires_password_change_and_then_unlocks_access(isolated_tenants):
    client = isolated_tenants["client"]
    TenantASession = isolated_tenants["sessions"][0]

    db = TenantASession()
    db.add(models.User(
        username="firstlogin",
        full_name="First Login",
        password_hash=hash_password("Initial@123"),
        role=models.Role.operator,
        active=True,
        must_change_password=True,
    ))
    db.commit()
    db.close()

    login = client.post("/api/v1/auth/login", json={
        "company_code": "AA", "username": "firstlogin", "password": "Initial@123"
    })
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    blocked = client.get("/api/v1/masters/products", headers=headers)
    assert blocked.status_code == 403
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    changed = client.post(
        "/api/v1/users/me/change-password",
        headers=headers,
        json={"current_password": "Initial@123", "new_password": "Changed@123"},
    )
    assert changed.status_code == 204

    verify_db = TenantASession()
    try:
        assert verify_db.query(models.User).filter_by(username="firstlogin").one().must_change_password is False
    finally:
        verify_db.close()

    assert client.get("/api/v1/inventory/valuation", headers=headers).status_code == 200


def test_only_admin_can_reset_passwords(isolated_tenants):
    client = isolated_tenants["client"]
    TenantASession = isolated_tenants["sessions"][0]

    db = TenantASession()
    operator = models.User(
        username="operator",
        full_name="Operator",
        password_hash=hash_password("Operator@123"),
        role=models.Role.operator,
        active=True,
        must_change_password=False,
    )
    target = models.User(
        username="target",
        full_name="Target",
        password_hash=hash_password("Target@123"),
        role=models.Role.operator,
        active=True,
        must_change_password=False,
    )
    db.add_all([operator, target])
    db.commit()
    target_id = target.id
    db.close()

    admin_login = _login(client, "AA")
    login = client.post("/api/v1/auth/login", json={
        "company_code": "AA", "username": "operator", "password": "Operator@123"
    })
    assert login.status_code == 200
    operator_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    forbidden = client.post(
        f"/api/v1/users/{target_id}/reset-password",
        headers=operator_headers,
        json={"new_password": "Reset@123"},
    )
    assert forbidden.status_code == 403

    allowed = client.post(
        f"/api/v1/users/{target_id}/reset-password",
        headers={"Authorization": f"Bearer {admin_login['access_token']}"},
        json={"new_password": "Reset@123"},
    )
    assert allowed.status_code == 204

    target_login = client.post("/api/v1/auth/login", json={
        "company_code": "AA", "username": "target", "password": "Reset@123"
    })
    assert target_login.status_code == 200
    assert target_login.json()["must_change_password"] is True


def test_operator_and_accountant_have_inventory_and_purchase_request_access(isolated_tenants):
    client = isolated_tenants["client"]
    TenantASession = isolated_tenants["sessions"][0]

    db = TenantASession()
    db.add_all([
        models.User(
            username="accountant",
            full_name="Accountant",
            password_hash=hash_password("Accountant@123"),
            role=models.Role.accountant,
            active=True,
            must_change_password=False,
        ),
        models.User(
            username="operator2",
            full_name="Operator 2",
            password_hash=hash_password("Operator2@123"),
            role=models.Role.operator,
            active=True,
            must_change_password=False,
        ),
    ])
    db.commit()
    db.close()

    for username, password in (
        ("accountant", "Accountant@123"),
        ("operator2", "Operator2@123"),
    ):
        login = client.post("/api/v1/auth/login", json={
            "company_code": "AA", "username": username, "password": password
        })
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert client.get("/api/v1/inventory/valuation", headers=headers).status_code == 200
        assert client.get("/api/v1/purchasing/requisitions", headers=headers).status_code == 200


def test_control_schema_is_not_created_by_application_startup():
    import app.main as main_module
    assert not hasattr(main_module, "ControlBase")
