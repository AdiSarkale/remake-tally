"""Regression tests for the HR Foundation v1 role boundary."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import models
from app.api.deps import ROLE_PERMISSIONS, require_area


def test_only_admin_has_hr_management_permission():
    assert "hr" in ROLE_PERMISSIONS[models.Role.admin]
    assert "hr" not in ROLE_PERMISSIONS[models.Role.accountant]
    assert "hr" not in ROLE_PERMISSIONS[models.Role.operator]


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
