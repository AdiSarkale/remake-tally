"""Regression tests for runtime tenant isolation across ERP API modules.

The important distinction from the original tenant tests is that these requests
exercise app.db.session.get_db, which is the dependency imported by the ERP
route modules. That proves the HTTP route layer, not only authentication, is
resolved against the JWT-selected tenant database.
"""

from datetime import date
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
        # Mirror the exact route-level grant migration instead of relying on
        # wildcard compatibility grants in isolated tenant fixtures.
        import importlib.util
        migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "p0_authz_exact_015.py"
        spec = importlib.util.spec_from_file_location("p0_authz_exact_015_test", migration_path)
        authz_migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(authz_migration)
        module_grants = [
            models.RolePermissionGrant(
                role=role, module=module, feature=feature, action=action,
                data_scope="tenant", allowed=True, updated_by="test-migration",
            )
            for role, modules in authz_migration.ROLE_MODULES.items()
            for module in modules
            for feature, actions in authz_migration.MODULE_FEATURE_ACTIONS.get(module, {}).items()
            for action in actions
        ]
        payroll_grants = [
            models.RolePermissionGrant(
                role=role, module="hr", feature="payroll", action=action,
                data_scope="tenant", allowed=True, updated_by="test",
            )
            for role in ("Admin", "HR")
            for action in ("read", "write", "prepare", "approve", "finalize", "lock", "reverse")
        ]
        finance_accounts = [
            models.FinanceAccount(id=f"salary-expense-{suffix}", code="5100", name="Salary Expense", account_type="expense", active=True, system_account=True, created_by="test"),
            models.FinanceAccount(id=f"salary-payable-{suffix}", code="2100", name="Salary Payable", account_type="liability", active=True, system_account=True, created_by="test"),
            models.FinanceAccount(id=f"pf-payable-{suffix}", code="2110", name="PF Payable", account_type="liability", active=True, system_account=True, created_by="test"),
            models.FinanceAccount(id=f"pt-payable-{suffix}", code="2120", name="PT Payable", account_type="liability", active=True, system_account=True, created_by="test"),
            models.FinanceAccount(id=f"tds-payable-{suffix}", code="2130", name="TDS Payable", account_type="liability", active=True, system_account=True, created_by="test"),
        ]
        payroll_mapping = models.FinancePayrollAccountMapping(
            id=1, salary_expense_account_id=f"salary-expense-{suffix}",
            salary_payable_account_id=f"salary-payable-{suffix}",
            employee_pf_payable_account_id=f"pf-payable-{suffix}",
            professional_tax_payable_account_id=f"pt-payable-{suffix}",
            tds_payable_account_id=f"tds-payable-{suffix}", updated_by="test",
        )
        shift_employee = models.Employee(
            id=f"shift-employee-{suffix}", emp_code=f"SHIFT-{suffix.upper()}",
            name=f"{company_label} Shift Employee", joining_date=date(2026, 1, 1), active=True,
        )
        shift_type = models.HRShiftType(
            id=f"shift-type-{suffix}", code="DAY", name="Day Shift",
            start_time=__import__("datetime").time(9), end_time=__import__("datetime").time(17),
            end_day_offset=0, active=True, created_by="admin",
        )
        shift_assignment = models.HRShiftAssignment(
            id=f"shift-assignment-{suffix}", scope_type="employee",
            employee_id=shift_employee.id, branch_id=None, department=None,
            shift_type_id=shift_type.id, weekdays=[0, 1, 2, 3, 4],
            valid_from=date(2026, 1, 1), valid_to=None, created_by="admin",
        )
        shift_assignment_grants = [
            models.RolePermissionGrant(
                role="Admin", module="hr", feature="shift_assignments",
                action=action, data_scope="tenant", allowed=True, updated_by="test",
            )
            for action in ("read", "write")
        ]
        leave_grants = []
        for role in ("Admin", "HR"):
            for feature, action, scope in (
                ("leave_types", "read", "tenant"), ("leave_types", "write", "tenant"),
                ("leave_balances", "read", "tenant"), ("leave_balances", "write", "tenant"),
                ("leave_requests", "read", "tenant"), ("leave_requests", "approve", "tenant"),
                ("leave_types", "read", "self"), ("leave_balances", "read", "self"),
                ("leave_requests", "read", "self"), ("leave_requests", "create", "self"),
            ):
                leave_grants.append(models.RolePermissionGrant(
                    role=role, module="hr", feature=feature, action=action,
                    data_scope=scope, allowed=True, updated_by="test",
                ))
        for feature, action, scope in (
            ("leave_types", "read", "self"), ("leave_balances", "read", "self"),
            ("leave_requests", "read", "self"), ("leave_requests", "create", "self"),
            ("leave_requests", "approve", "department"),
        ):
            leave_grants.append(models.RolePermissionGrant(
                role="Operator", module="hr", feature=feature, action=action,
                data_scope=scope, allowed=True, updated_by="test",
            ))
        db.add_all([user, customer, supplier, product, material, invoice, requisition, payment, *module_grants, *payroll_grants, *leave_grants, *finance_accounts, payroll_mapping, shift_employee, shift_type, shift_assignment, *shift_assignment_grants])
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
        ("/api/v1/hr/shift-assignments", lambda rows: [r["id"] for r in rows], "shift-assignment-a", "shift-assignment-b"),
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


def test_production_can_read_employees_but_cannot_manage_employee_records(isolated_tenants):
    client = isolated_tenants["client"]
    TenantASession = isolated_tenants["sessions"][0]

    db = TenantASession()
    employee = models.Employee(
        id="employee-production-permissions",
        emp_code="SF-001",
        name="Shop Floor Employee",
        employee_type=models.EmployeeType.shop_floor,
        department="Production",
        designation="Operator",
        active=True,
    )
    db.add(employee)
    db.add(models.User(
        username="production-user",
        full_name="Production User",
        password_hash=hash_password("Production@123"),
        role=models.Role.operator,
        active=True,
        must_change_password=False,
    ))
    db.commit()
    db.close()

    login = client.post("/api/v1/auth/login", json={
        "company_code": "AA",
        "username": "production-user",
        "password": "Production@123",
    })
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    employees = client.get("/api/v1/manufacturing/employees", headers=headers)
    assert employees.status_code == 200, employees.text
    assert any(row["id"] == "employee-production-permissions" for row in employees.json())

    # Production still needs these endpoints for the manufacturing workflow.
    assert client.get("/api/v1/manufacturing/workcenters", headers=headers).status_code == 200
    assert client.get("/api/v1/manufacturing/production-orders", headers=headers).status_code == 200

    create_employee = client.post(
        "/api/v1/manufacturing/employees",
        headers=headers,
        json={
            "emp_code": "SF-002",
            "name": "Another Employee",
            "employee_type": "shop_floor",
            "department": "Production",
            "designation": "Operator",
            "active": True,
        },
    )
    assert create_employee.status_code == 403

    update_employee = client.put(
        "/api/v1/manufacturing/employees/employee-production-permissions",
        headers=headers,
        json={
            "emp_code": "SF-001",
            "name": "Changed Name",
            "employee_type": "shop_floor",
            "department": "Production",
            "designation": "Operator",
            "active": True,
        },
    )
    assert update_employee.status_code == 403

    add_skill = client.post(
        "/api/v1/manufacturing/employees/employee-production-permissions/skills",
        headers=headers,
        json={"skill": "Welding", "level": 2, "certified": False, "active": True},
    )
    assert add_skill.status_code == 403


def test_admin_can_create_employees_and_manage_employee_skills(isolated_tenants):
    client = isolated_tenants["client"]
    _ensure_hr_reference_data(isolated_tenants["sessions"][0])
    admin = _login(client, "AA")
    headers = {"Authorization": f"Bearer {admin['access_token']}"}

    created = client.post(
        "/api/v1/manufacturing/employees",
        headers=headers,
        json={
            "emp_code": "HR-001",
            "name": "HR Managed Employee",
            "employee_type": "shop_floor",
            "department": "Production",
            "designation": "Operator",
            "active": True,
            "joining_date": "2026-01-01",
        },
    )
    assert created.status_code == 201, created.text
    employee_id = created.json()["id"]

    skill = client.post(
        f"/api/v1/manufacturing/employees/{employee_id}/skills",
        headers=headers,
        json={"skill": "Welding", "level": 3, "certified": True, "active": True},
    )
    assert skill.status_code == 201, skill.text



def _ensure_hr_reference_data(session_factory):
    """Seed the tenant-managed types needed by the employee API tests."""
    db = session_factory()
    try:
        definitions = (
            ("shop_floor", "Shop floor", "shop_floor"),
            ("staff", "Staff", "staff"),
        )
        for code, name, payout_classification in definitions:
            if db.query(models.EmployeeTypeDefinition).filter_by(code=code).first() is None:
                db.add(models.EmployeeTypeDefinition(
                    code=code,
                    name=name,
                    payout_classification=payout_classification,
                    active=True,
                ))
        db.commit()
    finally:
        db.close()


def _add_hr_api_user(session_factory, username, role, password):
    db = session_factory()
    try:
        db.add(models.User(
            username=username,
            full_name=username,
            password_hash=hash_password(password),
            role=role,
            active=True,
            must_change_password=False,
        ))
        db.commit()
    finally:
        db.close()


def _hr_api_headers(client, company_code, username, password):
    response = client.post("/api/v1/auth/login", json={
        "company_code": company_code,
        "username": username,
        "password": password,
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_hr_employee_api_generates_immutable_codes_and_handles_lifecycle(isolated_tenants):
    client = isolated_tenants["client"]
    tenant_session = isolated_tenants["sessions"][0]
    _ensure_hr_reference_data(tenant_session)
    headers = _hr_api_headers(client, "AA", "admin", "Password@123")

    config = client.put(
        "/api/v1/hr/employee-code-config",
        headers=headers,
        json={"pattern": "EMP-{SEQ:03}", "sequence_start": 17, "increment_by": 2},
    )
    assert config.status_code == 200, config.text

    created = client.post(
        "/api/v1/manufacturing/employees",
        headers=headers,
        json={
            "name": "  Alice Worker  ",
            "employee_type": "shop_floor",
            "department": "Production",
            "designation": "Operator",
            # These extra fields must not let clients control codes or status.
            "emp_code": "CLIENT-OVERRIDE",
            "active": False,
            "joining_date": "2026-01-01",
        },
    )
    assert created.status_code == 201, created.text
    employee = created.json()
    employee_id = employee["id"]
    assert employee["name"] == "Alice Worker"
    assert employee["emp_code"] == "EMP-017"
    assert employee["active"] is True

    updated = client.put(
        f"/api/v1/manufacturing/employees/{employee_id}",
        headers=headers,
        json={
            "name": "Alice Cooper",
            "employee_type": "shop_floor",
            "department": "Production",
            "designation": "Senior Operator",
            "emp_code": "CLIENT-CHANGED",
            "active": False,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Alice Cooper"
    assert updated.json()["emp_code"] == "EMP-017"
    assert updated.json()["active"] is True

    skill_payload = {"skill": "Welding", "level": 4, "certified": True, "active": True}
    skill = client.post(
        f"/api/v1/manufacturing/employees/{employee_id}/skills",
        headers=headers,
        json=skill_payload,
    )
    assert skill.status_code == 201, skill.text
    assert skill.json()["skill"] == "Welding"
    duplicate_skill = client.post(
        f"/api/v1/manufacturing/employees/{employee_id}/skills",
        headers=headers,
        json=skill_payload,
    )
    assert duplicate_skill.status_code == 400
    skills = client.get(
        f"/api/v1/manufacturing/employees/{employee_id}/skills",
        headers=headers,
    )
    assert skills.status_code == 200
    assert [row["skill"] for row in skills.json()] == ["Welding"]

    deactivated = client.patch(
        f"/api/v1/manufacturing/employees/{employee_id}/status",
        headers=headers,
        json={"active": False},
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["active"] is False

    active_rows = client.get("/api/v1/manufacturing/employees", headers=headers)
    assert active_rows.status_code == 200
    assert employee_id not in {row["id"] for row in active_rows.json()}

    history = client.get(
        "/api/v1/manufacturing/employees",
        headers=headers,
        params={"include_inactive": "true"},
    )
    assert history.status_code == 200
    assert employee_id in {row["id"] for row in history.json()}

    reactivated = client.patch(
        f"/api/v1/manufacturing/employees/{employee_id}/status",
        headers=headers,
        json={"active": True},
    )
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["active"] is True

    second = client.post(
        "/api/v1/manufacturing/employees",
        headers=headers,
        json={
            "name": "Bob Worker",
            "employee_type": "staff",
            "department": "Office",
            "designation": "Coordinator",
            "joining_date": "2026-01-01",
        },
    )
    assert second.status_code == 201, second.text
    assert second.json()["emp_code"] == "EMP-019"


def test_hr_api_authorization_separates_hr_management_from_production(isolated_tenants):
    client = isolated_tenants["client"]
    tenant_session = isolated_tenants["sessions"][0]
    _ensure_hr_reference_data(tenant_session)
    _add_hr_api_user(tenant_session, "hruser", models.Role.hr, "HR@Password123")
    _add_hr_api_user(tenant_session, "flooruser", models.Role.operator, "Floor@Password123")

    hr_headers = _hr_api_headers(client, "AA", "hruser", "HR@Password123")
    operator_headers = _hr_api_headers(client, "AA", "flooruser", "Floor@Password123")

    assert client.get("/api/v1/hr/employee-code-config", headers=hr_headers).status_code == 200
    assert client.get("/api/v1/hr/employee-types", headers=hr_headers).status_code == 200
    assert client.get("/api/v1/manufacturing/production-orders", headers=hr_headers).status_code == 403

    created = client.post(
        "/api/v1/manufacturing/employees",
        headers=hr_headers,
        json={
            "name": "HR Created Employee",
            "employee_type": "shop_floor",
            "department": "Production",
            "designation": "Operator",
            "joining_date": "2026-01-01",
        },
    )
    assert created.status_code == 201, created.text
    employee_id = created.json()["id"]

    visible = client.get("/api/v1/manufacturing/employees", headers=operator_headers)
    assert visible.status_code == 200
    assert employee_id in {row["id"] for row in visible.json()}

    denied_create = client.post(
        "/api/v1/manufacturing/employees",
        headers=operator_headers,
        json={"name": "Unauthorized Employee", "employee_type": "shop_floor"},
    )
    assert denied_create.status_code == 403

    denied_status_change = client.patch(
        f"/api/v1/manufacturing/employees/{employee_id}/status",
        headers=operator_headers,
        json={"active": False},
    )
    assert denied_status_change.status_code == 403

    denied_settings = client.get(
        "/api/v1/hr/employee-code-config",
        headers=operator_headers,
    )
    assert denied_settings.status_code == 403

    denied_history = client.get(
        "/api/v1/manufacturing/employees",
        headers=operator_headers,
        params={"include_inactive": "true"},
    )
    assert denied_history.status_code == 403


def test_hr_type_codes_are_immutable_and_code_patterns_are_validated(isolated_tenants):
    client = isolated_tenants["client"]
    tenant_session = isolated_tenants["sessions"][0]
    _ensure_hr_reference_data(tenant_session)
    headers = _hr_api_headers(client, "AA", "admin", "Password@123")

    created_type = client.post(
        "/api/v1/hr/employee-types",
        headers=headers,
        json={
            "code": "contractor",
            "name": "Contractor",
            "payout_classification": "contractor",
            "active": True,
        },
    )
    assert created_type.status_code == 201, created_type.text
    type_id = created_type.json()["id"]

    changed_code = client.patch(
        f"/api/v1/hr/employee-types/{type_id}",
        headers=headers,
        json={
            "code": "vendor",
            "name": "Contractor",
            "payout_classification": "contractor",
            "active": True,
        },
    )
    assert changed_code.status_code == 422

    invalid_pattern = client.put(
        "/api/v1/hr/employee-code-config",
        headers=headers,
        json={"pattern": "EMP-{YEAR}", "sequence_start": 4, "increment_by": 2},
    )
    assert invalid_pattern.status_code == 422

    valid_pattern = client.put(
        "/api/v1/hr/employee-code-config",
        headers=headers,
        json={
            "pattern": "NEX-{TYPE}-{SEQ:03}-{DEPT}",
            "sequence_start": 4,
            "increment_by": 2,
        },
    )
    assert valid_pattern.status_code == 200, valid_pattern.text

    employee = client.post(
        "/api/v1/manufacturing/employees",
        headers=headers,
        json={
            "name": "Contractor One",
            "employee_type": "contractor",
            "department": "Field Ops",
            "designation": "Technician",
            "joining_date": "2026-01-01",
        },
    )
    assert employee.status_code == 201, employee.text
    assert employee.json()["emp_code"] == "NEX-CONTRACTOR-004-FIELD-OPS"


def test_payroll_settings_and_data_are_tenant_scoped(isolated_tenants):
    client = isolated_tenants["client"]
    a = _login(client, "AA")
    b = _login(client, "BB")
    a_headers = {"Authorization": f"Bearer {a['access_token']}"}
    b_headers = {"Authorization": f"Bearer {b['access_token']}"}

    defaults = client.get("/api/v1/hr/payroll/settings", headers=b_headers)
    changed = client.put(
        "/api/v1/hr/payroll/settings",
        headers=a_headers,
        json={"salary_count_mode": "fixed_days", "monthly_salary_days": 27, "week_off_days": [4, 5]},
    )
    assert defaults.status_code == 200, defaults.text
    assert changed.status_code == 200, changed.text
    assert changed.json()["monthly_salary_days"] == 27
    assert changed.json()["week_off_days"] == [4, 5]

    a_result = client.get("/api/v1/hr/payroll/settings", headers=a_headers)
    b_result = client.get("/api/v1/hr/payroll/settings", headers=b_headers)
    assert a_result.json()["salary_count_mode"] == "fixed_days"
    assert a_result.json()["monthly_salary_days"] == 27
    assert b_result.json()["salary_count_mode"] == "working_days"
    assert b_result.json()["monthly_salary_days"] == 26


def test_payroll_endpoints_remain_inside_hr_role_boundary():
    from fastapi.routing import APIRoute

    from app import models
    from app.api.deps import ROLE_PERMISSIONS
    from app.main import app

    assert "hr" in ROLE_PERMISSIONS[models.Role.admin]
    assert "hr" in ROLE_PERMISSIONS[models.Role.hr]
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/v1/hr/"):
            assert any(dep.call is session_module.get_db for dep in _dependency_calls(route.dependant)), route.path


def test_payroll_salary_attendance_calendar_finalization_and_slip_flow(isolated_tenants):
    client = isolated_tenants["client"]
    token = _login(client, "AA")
    headers = {"Authorization": f"Bearer {token['access_token']}"}
    tenant_a_session, _ = isolated_tenants["sessions"]

    employee_id = "payroll-employee-a"
    tenant_a = tenant_a_session()
    try:
        tenant_a.add(
            models.Employee(
                id=employee_id,
                emp_code="PAY-A-001",
                name="Payroll Employee",
                employee_type="staff",
                department="Production",
                designation="Operator",
                joining_date=date(2026, 10, 1),
                active=True,
            )
        )
        tenant_a.commit()
    finally:
        tenant_a.close()

    tenant_a = tenant_a_session()
    approver = models.User(
        username="hr-approver", full_name="HR Approver",
        password_hash=hash_password("Password@123"), role=models.Role.hr,
        active=True, must_change_password=False,
    )
    tenant_a.add(approver)
    tenant_a.commit()
    tenant_a.close()
    approver_login = client.post(
        "/api/v1/auth/login",
        json={"company_code": "AA", "username": "hr-approver", "password": "Password@123"},
    )
    assert approver_login.status_code == 200, approver_login.text
    approver_headers = {"Authorization": f"Bearer {approver_login.json()['access_token']}"}
    settings = client.put(
        "/api/v1/hr/payroll/settings",
        headers=headers,
        json={
            "salary_count_mode": "fixed_days",
            "monthly_salary_days": 26,
            "week_off_days": [5, 6],
        },
    )
    assert settings.status_code == 200, settings.text

    holiday = client.put(
        "/api/v1/hr/calendar/2026-10-05",
        headers=headers,
        json={"day_type": "holiday", "description": "Company holiday"},
    )
    assert holiday.status_code == 200, holiday.text

    salary = client.put(
        f"/api/v1/hr/employees/{employee_id}/salary",
        headers=headers,
        json={
            "annual_salary": 600000,
            "basic_pct": 50,
            "hra_pct": 40,
            "da_pct": 0,
            "conveyance_monthly": 1000,
            "medical_allowance_monthly": 1000,
            "pf_pct": 12,
            "professional_tax_monthly": 200,
            "tds_monthly": 500,
        },
    )
    assert salary.status_code == 200, salary.text
    assert salary.json()["annual_salary"] == 600000
    assert salary.json()["monthly_gross"] == 50000

    # Every scheduled working day requires an explicit status before finalization.
    # The holiday remains excluded from attendance completeness.
    for day in range(1, 32):
        work_date = f"2026-10-{day:02d}"
        response = client.put(
            "/api/v1/hr/attendance",
            headers=headers,
            json={
                "employee_id": employee_id,
                "work_date": work_date,
                "status": "absent" if day in (5, 6) else "present",
                "overtime_minutes": 0,
                "note": "Payroll regression test",
            },
        )
        assert response.status_code == 200, response.text

    attendance = client.get(
        "/api/v1/hr/attendance/monthly",
        headers=headers,
        params={"employee_id": employee_id, "year": 2026, "month": 10},
    )
    assert attendance.status_code == 200, attendance.text
    assert len(attendance.json()) == 31
    holiday_attendance = next(row for row in attendance.json() if row["work_date"] == "2026-10-05")
    assert holiday_attendance["calendar_type"] == "holiday"
    assert holiday_attendance["status"] == "absent"

    preview = client.get(
        "/api/v1/hr/payroll/preview",
        headers=headers,
        params={"year": 2026, "month": 10},
    )
    assert preview.status_code == 200, preview.text
    item = next(row for row in preview.json()["items"] if row["employee_id"] == employee_id)
    assert item["absence_deduction"] == 1923.08
    assert item["net_pay"] == 44376.92

    prepared = client.post("/api/v1/hr/payroll/runs/2026/10/prepare", headers=headers)
    assert prepared.status_code == 200, prepared.text
    assert prepared.json()["status"] == "prepared"
    frozen_run_id = prepared.json()["id"]
    assert prepared.json()["items"][0]["monthly_gross"] == 50000

    # The preparer cannot approve their own snapshot.
    self_approval = client.post(f"/api/v1/hr/payroll/runs/{frozen_run_id}/approve", headers=headers)
    assert self_approval.status_code == 403

    changed_salary_while_prepared = client.put(
        f"/api/v1/hr/employees/{employee_id}/salary",
        headers=headers,
        json={
            "annual_salary": 1200000,
            "basic_pct": 50,
            "hra_pct": 40,
            "da_pct": 0,
            "conveyance_monthly": 1000,
            "medical_allowance_monthly": 1000,
            "pf_pct": 12,
            "professional_tax_monthly": 200,
            "tds_monthly": 500,
        },
    )
    assert changed_salary_while_prepared.status_code == 409

    approved = client.post(f"/api/v1/hr/payroll/runs/{frozen_run_id}/approve", headers=approver_headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    finalized = client.post("/api/v1/hr/payroll/runs/2026/10/finalize", headers=headers)
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["status"] == "finalized"
    payroll_journals = client.get("/api/v1/finance/journals", headers=headers, params={"source_type": "hr_payroll"})
    assert payroll_journals.status_code == 200, payroll_journals.text
    assert len(payroll_journals.json()) == 1
    original_journal = payroll_journals.json()[0]
    assert original_journal["journal_no"] == "PAY-202610-R1"
    assert round(sum(line["debit"] for line in original_journal["lines"]), 2) == round(sum(line["credit"] for line in original_journal["lines"]), 2)

    # The finalized employee snapshot remains unchanged after later profile edits.
    changed_salary = client.put(
        f"/api/v1/hr/employees/{employee_id}/salary",
        headers=headers,
        json={
            "annual_salary": 1200000,
            "basic_pct": 50,
            "hra_pct": 40,
            "da_pct": 0,
            "conveyance_monthly": 1000,
            "medical_allowance_monthly": 1000,
            "pf_pct": 12,
            "professional_tax_monthly": 200,
            "tds_monthly": 500,
        },
    )
    assert changed_salary.status_code == 200, changed_salary.text
    finalized_again = client.post("/api/v1/hr/payroll/runs/2026/10/finalize", headers=headers)
    assert finalized_again.status_code == 200, finalized_again.text
    assert finalized_again.json()["id"] == frozen_run_id
    assert finalized_again.json()["items"][0]["monthly_gross"] == 50000

    locked = client.post(f"/api/v1/hr/payroll/runs/{frozen_run_id}/lock", headers=headers)
    assert locked.status_code == 200, locked.text
    assert locked.json()["status"] == "locked"

    slip = client.get(f"/api/v1/hr/payroll/slips/{employee_id}/2026/10", headers=headers)
    assert slip.status_code == 200, slip.text
    assert slip.headers["content-type"].startswith("application/pdf")
    assert slip.content.startswith(b"%PDF-")

    reversed_run = client.post(
        f"/api/v1/hr/payroll/runs/{frozen_run_id}/reverse",
        headers=headers,
        json={"reason": "Approved payroll correction required"},
    )
    assert reversed_run.status_code == 200, reversed_run.text
    assert reversed_run.json()["status"] == "reversed"
    reversal_journals = client.get("/api/v1/finance/journals", headers=headers, params={"source_type": "hr_payroll_reversal"})
    assert reversal_journals.status_code == 200, reversal_journals.text
    assert len(reversal_journals.json()) == 1
    reversal = reversal_journals.json()[0]
    assert reversal["reversal_of_id"] == original_journal["id"]
    assert round(sum(line["debit"] for line in reversal["lines"]), 2) == round(sum(line["credit"] for line in reversal["lines"]), 2)
    slip_after_reversal = client.get(f"/api/v1/hr/payroll/slips/{employee_id}/2026/10", headers=headers)
    assert slip_after_reversal.status_code == 404

    next_revision = client.post("/api/v1/hr/payroll/runs/2026/10/prepare", headers=headers)
    assert next_revision.status_code == 200, next_revision.text
    assert next_revision.json()["revision"] == 2
    assert next_revision.json()["status"] == "prepared"

    # Company B cannot see Company A's employees or salary profiles.
    token_b = _login(client, "BB")
    b_headers = {"Authorization": f"Bearer {token_b['access_token']}"}
    b_salaries = client.get("/api/v1/hr/salaries", headers=b_headers)
    assert b_salaries.status_code == 200, b_salaries.text
    assert b_salaries.json() == []
    b_attendance = client.get(
        "/api/v1/hr/attendance/monthly",
        headers=b_headers,
        params={"employee_id": employee_id, "year": 2026, "month": 10},
    )
    assert b_attendance.status_code == 404


def test_payroll_run_and_salary_slip_validate_period_before_lookup(isolated_tenants):
    client = isolated_tenants["client"]
    token = _login(client, "AA")
    headers = {"Authorization": f"Bearer {token['access_token']}"}

    run = client.get("/api/v1/hr/payroll/runs/2026/13", headers=headers)
    slip = client.get("/api/v1/hr/payroll/slips/unknown-employee/1999/10", headers=headers)

    assert run.status_code == 422
    assert slip.status_code == 422


def test_employee_api_reads_and_mutations_are_tenant_scoped(isolated_tenants):
    client = isolated_tenants["client"]
    tenant_a, tenant_b = isolated_tenants["sessions"]

    a_db = tenant_a()
    b_db = tenant_b()
    try:
        a_db.add(models.Employee(
            id="employee-a", emp_code="EMP-A01", name="Company A Employee",
            employee_type="shop_floor", department="Production",
            designation="Operator", joining_date=date(2026, 1, 1), active=True,
        ))
        b_db.add(models.Employee(
            id="employee-b", emp_code="EMP-B01", name="Company B Employee",
            employee_type="shop_floor", department="Production",
            designation="Operator", joining_date=date(2026, 1, 1), active=True,
        ))
        a_db.commit()
        b_db.commit()
    finally:
        a_db.close()
        b_db.close()

    a = _login(client, "AA")
    b = _login(client, "BB")
    a_headers = {"Authorization": f"Bearer {a['access_token']}"}
    b_headers = {"Authorization": f"Bearer {b['access_token']}"}

    a_rows = client.get("/api/v1/manufacturing/employees", headers=a_headers)
    b_rows = client.get("/api/v1/manufacturing/employees", headers=b_headers)
    assert a_rows.status_code == 200, a_rows.text
    assert b_rows.status_code == 200, b_rows.text

    a_codes = {row["emp_code"] for row in a_rows.json()}
    b_codes = {row["emp_code"] for row in b_rows.json()}
    assert "EMP-A01" in a_codes
    assert "EMP-B01" not in a_codes
    assert "EMP-B01" in b_codes
    assert "EMP-A01" not in b_codes

    cross_tenant_update = client.put(
        "/api/v1/manufacturing/employees/employee-a",
        headers=b_headers,
        json={
            "name": "Company B attempted takeover",
            "employee_type": "shop_floor",
            "department": "Production",
            "designation": "Operator",
        },
    )
    assert cross_tenant_update.status_code == 404

    cross_tenant_deactivation = client.patch(
        "/api/v1/manufacturing/employees/employee-a/status",
        headers=b_headers,
        json={"active": False},
    )
    assert cross_tenant_deactivation.status_code == 404


def test_hr_leave_request_approval_attendance_and_carry_forward(isolated_tenants):
    from app.api.routes.approvals import Department

    client = isolated_tenants["client"]
    admin_login = _login(client, "AA")
    admin_headers = {"Authorization": f"Bearer {admin_login['access_token']}"}
    tenant_a_session, _ = isolated_tenants["sessions"]

    employee_id = "leave-employee-a"
    tenant = tenant_a_session()
    try:
        employee_user = models.User(
            username="leave-employee", full_name="Leave Employee",
            password_hash=hash_password("Password@123"), role=models.Role.operator,
            active=True, must_change_password=False,
        )
        approver = models.User(
            username="leave-approver", full_name="Leave Approver",
            password_hash=hash_password("Password@123"), role=models.Role.hr,
            active=True, must_change_password=False,
        )
        employee = models.Employee(
            id=employee_id, emp_code="LEAVE-A-001", name="Leave Employee",
            employee_type="staff", department="Operations", designation="Operator",
            joining_date=date(2026, 1, 1), active=True,
        )
        department = Department(code="OPS", name="Operations", hod_username="leave-approver", active=True)
        tenant.add_all([employee_user, approver, employee, department])
        tenant.commit()
        employee_user_id = employee_user.id
    finally:
        tenant.close()

    link = client.post(
        "/api/v1/authorization/employee-links",
        headers=admin_headers,
        json={"user_id": employee_user_id, "employee_id": employee_id},
    )
    assert link.status_code == 201, link.text
    duplicate_link = client.post(
        "/api/v1/authorization/employee-links",
        headers=admin_headers,
        json={"user_id": employee_user_id, "employee_id": employee_id},
    )
    assert duplicate_link.status_code == 409

    leave_type = client.post(
        "/api/v1/hr/leave/types",
        headers=admin_headers,
        json={
            "code": "CL", "name": "Casual Leave", "is_paid": True,
            "annual_entitlement": 12, "carry_forward_limit": 4,
            "count_week_offs": False, "count_holidays": False,
            "allow_half_day": True, "active": True,
        },
    )
    assert leave_type.status_code == 201, leave_type.text
    leave_type_id = leave_type.json()["id"]

    accrual_type = client.post(
        "/api/v1/hr/leave/types",
        headers=admin_headers,
        json={
            "code": "AL", "name": "Accrued Leave", "is_paid": True,
            "annual_entitlement": 12, "carry_forward_limit": 0,
            "accrual_method": "monthly_prorated", "accrual_effective_from": "2026-10-16",
            "count_week_offs": False, "count_holidays": False,
            "allow_half_day": True, "active": True,
        },
    )
    assert accrual_type.status_code == 201, accrual_type.text
    accrual_type_id = accrual_type.json()["id"]
    accrual = client.post("/api/v1/hr/leave/accruals/run/2026/10", headers=admin_headers)
    assert accrual.status_code == 200, accrual.text
    assert accrual.json()["created_count"] == 1
    assert accrual.json()["total_accrued"] == 0.52
    accrual_repeat = client.post("/api/v1/hr/leave/accruals/run/2026/10", headers=admin_headers)
    assert accrual_repeat.status_code == 200, accrual_repeat.text
    assert accrual_repeat.json()["created_count"] == 0
    assert accrual_repeat.json()["skipped_existing"] == 1
    accrued_balance = client.get("/api/v1/hr/leave/balances?year=2026", headers=admin_headers)
    assert accrued_balance.status_code == 200
    assert next(row for row in accrued_balance.json() if row["leave_type_id"] == accrual_type_id)["accrued"] == 0.52

    balance = client.put(
        "/api/v1/hr/leave/balances",
        headers=admin_headers,
        json={
            "employee_id": employee_id, "leave_type_id": leave_type_id,
            "year": 2026, "opening_balance": 5, "accrued": 0, "adjusted": 0,
        },
    )
    assert balance.status_code == 200, balance.text

    employee_login = client.post(
        "/api/v1/auth/login",
        json={"company_code": "AA", "username": "leave-employee", "password": "Password@123"},
    )
    approver_login = client.post(
        "/api/v1/auth/login",
        json={"company_code": "AA", "username": "leave-approver", "password": "Password@123"},
    )
    assert employee_login.status_code == 200, employee_login.text
    assert approver_login.status_code == 200, approver_login.text
    employee_headers = {"Authorization": f"Bearer {employee_login.json()['access_token']}"}
    approver_headers = {"Authorization": f"Bearer {approver_login.json()['access_token']}"}

    request = client.post(
        "/api/v1/hr/leave/requests",
        headers=employee_headers,
        json={
            "leave_type_id": leave_type_id, "start_date": "2026-10-07",
            "end_date": "2026-10-08", "reason": "Personal work",
            "approver_username": "forged-approver",
        },
    )
    assert request.status_code == 201, request.text
    request_id = request.json()["id"]
    assert request.json()["approver_username"] == "leave-approver"
    assert request.json()["total_days"] == 2

    overlapping = client.post(
        "/api/v1/hr/leave/requests",
        headers=employee_headers,
        json={
            "leave_type_id": leave_type_id, "start_date": "2026-10-08",
            "end_date": "2026-10-08", "reason": "Duplicate request",
        },
    )
    assert overlapping.status_code == 409

    self_decision = client.patch(
        f"/api/v1/hr/leave/requests/{request_id}",
        headers=employee_headers,
        json={"status": "approved", "decision_note": "Self approval"},
    )
    assert self_decision.status_code == 403

    decision = client.patch(
        f"/api/v1/hr/leave/requests/{request_id}",
        headers=approver_headers,
        json={"status": "approved", "decision_note": "Approved by HOD"},
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "approved"

    half_day = client.post(
        "/api/v1/hr/leave/requests",
        headers=employee_headers,
        json={
            "leave_type_id": leave_type_id, "start_date": "2026-10-09",
            "end_date": "2026-10-09", "half_day": True, "reason": "Personal appointment",
        },
    )
    assert half_day.status_code == 201, half_day.text
    half_day_decision = client.patch(
        f"/api/v1/hr/leave/requests/{half_day.json()['id']}",
        headers=approver_headers,
        json={"status": "approved", "decision_note": "Half-day approved"},
    )
    assert half_day_decision.status_code == 200, half_day_decision.text

    tenant = tenant_a_session()
    try:
        attendance = tenant.query(models.EmployeeAttendance).filter(
            models.EmployeeAttendance.employee_id == employee_id
        ).order_by(models.EmployeeAttendance.work_date).all()
        assert [row.status for row in attendance] == ["paid_leave", "paid_leave", "paid_half_day"]
    finally:
        tenant.close()

    carried = client.post("/api/v1/hr/leave/balances/carry-forward/2026", headers=admin_headers)
    assert carried.status_code == 200, carried.text
    assert len(carried.json()) == 1
    assert carried.json()[0]["year"] == 2027
    assert carried.json()[0]["opening_balance"] == 2.5
    carried_again = client.post("/api/v1/hr/leave/balances/carry-forward/2026", headers=admin_headers)
    assert carried_again.status_code == 200
    assert carried_again.json() == []

    non_admin_grants = client.get("/api/v1/authorization/role-grants", headers=employee_headers)
    assert non_admin_grants.status_code == 403
    updated_grant = client.put(
        "/api/v1/authorization/role-grants",
        headers=admin_headers,
        json={
            "role": "Operator", "module": "hr", "feature": "leave_requests",
            "action": "create", "data_scope": "self", "allowed": False,
        },
    )
    assert updated_grant.status_code == 200, updated_grant.text
    assert updated_grant.json()["allowed"] is False
    assert updated_grant.json()["updated_by"] == "admin"
    revoked_request = client.post(
        "/api/v1/hr/leave/requests",
        headers=employee_headers,
        json={
            "leave_type_id": leave_type_id, "start_date": "2026-10-12",
            "end_date": "2026-10-12", "reason": "Permission revocation test",
        },
    )
    assert revoked_request.status_code == 403


def test_admin_branch_and_effective_dated_reporting_assignment_apis(isolated_tenants):
    client = isolated_tenants["client"]
    TenantASession = isolated_tenants["sessions"][0]
    admin = _login(client, "AA")
    headers = {"Authorization": f"Bearer {admin['access_token']}"}
    db = TenantASession()
    try:
        manager = models.Employee(id="org-manager", emp_code="ORG-001", name="Manager", joining_date=date(2026, 1, 1), active=True)
        report = models.Employee(id="org-report", emp_code="ORG-002", name="Report", joining_date=date(2026, 1, 1), active=True)
        db.add_all([manager, report])
        db.commit()
    finally:
        db.close()

    branch = client.post("/api/v1/authorization/branches", headers=headers, json={
        "code": "PUNE", "name": "Pune Branch", "timezone": "Asia/Kolkata", "address": "Pune",
    })
    assert branch.status_code == 201, branch.text
    branch_id = branch.json()["id"]

    manager_assignment = client.post("/api/v1/authorization/employee-org-assignments", headers=headers, json={
        "employee_id": "org-manager", "branch_id": branch_id, "department": "Operations",
        "valid_from": "2026-01-01",
    })
    assert manager_assignment.status_code == 201, manager_assignment.text

    report_assignment = client.post("/api/v1/authorization/employee-org-assignments", headers=headers, json={
        "employee_id": "org-report", "branch_id": branch_id, "manager_employee_id": "org-manager",
        "department": "Operations", "valid_from": "2026-01-01",
    })
    assert report_assignment.status_code == 201, report_assignment.text

    cycle = client.post("/api/v1/authorization/employee-org-assignments", headers=headers, json={
        "employee_id": "org-manager", "branch_id": branch_id, "manager_employee_id": "org-report",
        "department": "Operations", "valid_from": "2026-02-01",
    })
    assert cycle.status_code == 422, cycle.text

    team_grant = client.put("/api/v1/authorization/role-grants", headers=headers, json={
        "role": "HR", "module": "hr", "feature": "employees", "action": "read",
        "data_scope": "team", "allowed": True,
    })
    assert team_grant.status_code == 200, team_grant.text
    assert team_grant.json()["data_scope"] == "team"


def test_feature_action_grant_can_restrict_one_route_without_revoking_module(isolated_tenants):
    client = isolated_tenants["client"]
    admin = _login(client, "AA")
    headers = {"Authorization": f"Bearer {admin['access_token']}"}
    revoked = client.put("/api/v1/authorization/role-grants", headers=headers, json={
        "role": "Admin", "module": "finance", "feature": "customer_payments",
        "action": "create", "data_scope": "tenant", "allowed": False,
    })
    assert revoked.status_code == 200, revoked.text

    # Exact denial overrides the seeded explicit allow for this feature/action.
    denied = client.post("/api/v1/finance/customer-payments", headers=headers, json={
        "payment_date": "2026-11-07", "customer_id": "missing", "amount": 10,
        "mode": "UPI", "reference": "", "remarks": "",
    })
    assert denied.status_code == 403, denied.text

    # Read access remains granted by its separate explicit read permission.
    readable = client.get("/api/v1/finance/customer-payments", headers=headers)
    assert readable.status_code == 200, readable.text
