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
    class Query:
        def filter_by(self, **kwargs):
            return self

        def first(self):
            return type("Link", (), {"employee_id": "employee-1"})()

    class DB:
        def query(self, model):
            return Query()

    class User:
        id = "mapped-user"

    with pytest.raises(HTTPException) as error:
        enforce_employee_data_scope(DB(), User(), "employee-1", "branch")
    assert error.value.status_code == 403


def test_authorization_admin_apis_do_not_accept_tenant_or_actor_ids_from_requester():
    path = Path(__file__).resolve().parents[1] / "app" / "api" / "routes" / "authorization.py"
    module = ast.parse(path.read_text(encoding="utf-8"))
    source = path.read_text(encoding="utf-8")
    assert 'user.role != models.Role.admin' in source
    assert "created_by=user.username" in source
    assert "updated_by=user.username" in source
