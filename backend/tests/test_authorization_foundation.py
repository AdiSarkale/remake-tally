"""Regression coverage for explicit authorization foundations."""
import ast
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.modules.core.authorization import EmployeeUserLink, RolePermissionGrant
from app.api.deps import enforce_employee_data_scope
from fastapi import HTTPException
import pytest


def test_authorization_models_have_unique_account_and_employee_links():
    assert EmployeeUserLink.__tablename__ == "employee_user_links"
    assert RolePermissionGrant.__tablename__ == "role_permission_grants"
    constraints = {constraint.name for constraint in EmployeeUserLink.__table__.constraints}
    assert "uq_employee_user_links_user" in constraints
    assert "uq_employee_user_links_employee" in constraints


def test_employee_scope_rejects_unmapped_user_for_self_service():
    class Query:
        def filter_by(self, **kwargs):
            return self

        def first(self):
            return None

    class DB:
        def query(self, model):
            return Query()

    class User:
        id = "user-without-link"

    with pytest.raises(HTTPException) as error:
        enforce_employee_data_scope(DB(), User(), "employee-1", "self")
    assert error.value.status_code == 403


def test_employee_scope_rejects_unknown_scope():
    from types import SimpleNamespace

    class Query:
        def filter_by(self, **kwargs):
            return self

        def filter(self, *args):
            return self

        def first(self):
            return type("Link", (), {"employee_id": "employee-1"})()

        def all(self):
            return []

    class DB:
        def query(self, model):
            return Query()

        def get(self, model, employee_id):
            return SimpleNamespace(department="Operations", timezone="Asia/Kolkata")

    class User:
        id = "mapped-user"

    with pytest.raises(HTTPException) as error:
        enforce_employee_data_scope(DB(), User(), "employee-1", "division")
    assert error.value.status_code == 403


def test_authorization_admin_apis_do_not_accept_tenant_or_actor_ids_from_requester():
    path = Path(__file__).resolve().parents[1] / "app" / "api" / "routes" / "authorization.py"
    module = ast.parse(path.read_text(encoding="utf-8"))
    source = path.read_text(encoding="utf-8")
    assert 'user.role != models.Role.admin' in source
    assert "created_by=user.username" in source
    assert "updated_by=user.username" in source



def test_employee_scope_is_enforced_for_direct_employee_mutations_and_list_queries():
    from datetime import date
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app import models
    from app.api.deps import apply_employee_scope
    from app.api.routes.hr import _enforce_employee_scope

    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        today = date.today()
        branch = models.HRBranch(code="SCOPE", name="Scoped Branch")
        manager = models.Employee(id="scope-manager", emp_code="S-001", name="Manager", department="Ops")
        report = models.Employee(id="scope-report", emp_code="S-002", name="Report", department="Ops")
        outsider = models.Employee(id="scope-outsider", emp_code="S-003", name="Outsider", department="Ops")
        user = models.User(
            id="scope-user", username="scope-manager", full_name="Manager",
            password_hash="test", role=models.Role.hr, active=True,
            must_change_password=False,
        )
        db.add_all([branch, manager, report, outsider, user])
        db.flush()
        db.add(models.EmployeeUserLink(
            user_id=user.id, employee_id=manager.id, created_by="admin",
        ))
        db.add_all([
            models.RolePermissionGrant(
                role="HR", module="hr", feature="employees", action="read",
                data_scope="branch", allowed=True, updated_by="test",
            ),
            models.RolePermissionGrant(
                role="HR", module="hr", feature="employees", action="update",
                data_scope="branch", allowed=True, updated_by="test",
            ),
            models.EmployeeOrgAssignment(
                employee_id=manager.id, branch_id=branch.id, department="Ops",
                valid_from=today, created_by="admin",
            ),
            models.EmployeeOrgAssignment(
                employee_id=report.id, branch_id=branch.id, manager_employee_id=manager.id,
                department="Ops", valid_from=today, created_by="admin",
            ),
        ])
        db.commit()
        user = db.get(models.User, user.id)

        scoped = apply_employee_scope(
            db.query(models.Employee), db, user, "hr", "employees", "read",
        )
        assert {row.id for row in scoped.all()} == {"scope-manager", "scope-report"}
        _enforce_employee_scope(db, user, "scope-report", "update")
        with pytest.raises(HTTPException) as error:
            _enforce_employee_scope(db, user, "scope-outsider", "update")
        assert error.value.status_code == 403
    finally:
        db.close()
        engine.dispose()
