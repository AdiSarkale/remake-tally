"""Regression tests for the HR Foundation v1 role boundary."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import models
from app.api.deps import ROLE_PERMISSIONS, require_area


def test_admin_and_hr_have_hr_management_permission():
    assert "hr" in ROLE_PERMISSIONS[models.Role.admin]
    assert "hr" in ROLE_PERMISSIONS[models.Role.hr]
    assert "hr" not in ROLE_PERMISSIONS[models.Role.accountant]
    assert "hr" not in ROLE_PERMISSIONS[models.Role.operator]


def test_hr_role_is_isolated_from_finance_and_system_administration():
    assert ROLE_PERMISSIONS[models.Role.hr] == {"hr"}


def test_hr_guard_allows_admin():
    guard = require_area("hr")
    user = SimpleNamespace(role=models.Role.admin)

    assert guard(user) is user


@pytest.mark.parametrize("role", [models.Role.accountant, models.Role.operator])
def test_hr_guard_rejects_non_admin_roles(role):
    guard = require_area("hr")
    user = SimpleNamespace(role=role)

    with pytest.raises(HTTPException) as exc:
        guard(user)

    assert exc.value.status_code == 403


def test_production_users_retain_production_access_without_hr_management():
    assert "production" in ROLE_PERMISSIONS[models.Role.operator]
    assert "hr" not in ROLE_PERMISSIONS[models.Role.operator]


def test_employee_create_schema_validates_name_and_ignores_client_employee_code():
    from pydantic import ValidationError

    from app.schemas import EmployeeIn

    # Employee codes are server-generated and are not accepted as editable fields.
    payload = EmployeeIn(name="Valid name", emp_code="CLIENT-SUPPLIED")
    assert payload.name == "Valid name"
    assert not hasattr(payload, "emp_code")

    with pytest.raises(ValidationError):
        EmployeeIn(name="")
    with pytest.raises(ValidationError):
        EmployeeIn(name="N" * 121)



def test_legacy_model_and_schema_facades_reexport_hr_domain_definitions():
    from app import schemas
    from app.modules.hr import models as hr_models
    from app.modules.hr import schemas as hr_schemas

    assert models.Employee is hr_models.Employee
    assert models.EmployeeSkill is hr_models.EmployeeSkill
    assert models.EmployeeCodeConfig is hr_models.EmployeeCodeConfig
    assert models.EmployeeTypeDefinition is hr_models.EmployeeTypeDefinition
    assert models.Base.metadata is hr_models.Employee.__table__.metadata
    assert schemas.EmployeeIn is hr_schemas.EmployeeIn
    assert schemas.EmployeeUpdate is hr_schemas.EmployeeUpdate
    assert schemas.EmployeeStatusUpdate is hr_schemas.EmployeeStatusUpdate


def test_tenant_hr_migration_chain_has_single_latest_head():
    from pathlib import Path

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["hr_payroll_005"]
    assert script.get_revision("hr_role_001").down_revision == "employee_type_001"
    assert script.get_revision("hr_employee_types_002").down_revision == "hr_role_001"
    assert script.get_revision("hr_employee_codes_003").down_revision == "hr_employee_types_002"
    assert script.get_revision("hr_employee_type_code_length_004").down_revision == "hr_employee_codes_003"
    assert script.get_revision("hr_payroll_005").down_revision == "hr_employee_type_code_length_004"
