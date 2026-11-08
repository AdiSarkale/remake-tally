"""Tests for shift catalog and break-rule APIs."""
import inspect
from datetime import time

import pytest
from fastapi import HTTPException
from fastapi.params import Depends as DependsParam
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.routes import hr_shifts


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def user(db):
    row = models.User(
        id="shift-admin", username="shift-admin", full_name="Shift Admin",
        password_hash="test", role=models.Role.admin, active=True,
        must_change_password=False,
    )
    db.add(row)
    db.commit()
    return row


def _grant(db: Session, action: str):
    db.add(models.RolePermissionGrant(
        role="Admin", module="hr", feature="shifts", action=action,
        data_scope="tenant", allowed=True, updated_by="test",
    ))
    db.commit()


def _shift_payload(
    code="DAY", name="Day Shift", start=time(9), end=time(17), offset=0,
):
    return schemas.ShiftTypeIn(
        code=code, name=name, start_time=start, end_time=end,
        end_day_offset=offset,
    )


def test_shift_catalog_routes_require_exact_read_and_write_grants(db, user):
    endpoints = (
        (hr_shifts.list_shifts, "read"),
        (hr_shifts.create_shift, "write"),
        (hr_shifts.update_shift, "write"),
        (hr_shifts.set_shift_active, "write"),
        (hr_shifts.create_break_rule, "write"),
    )
    dependencies = []
    for endpoint, action in endpoints:
        dependency = inspect.signature(endpoint).parameters["user"].default
        assert isinstance(dependency, DependsParam)
        assert dependency.dependency is not None
        dependencies.append((dependency, action))
        with pytest.raises(HTTPException) as denied:
            dependency.dependency(user=user, db=db)
        assert denied.value.status_code == 403

    _grant(db, "read")
    _grant(db, "write")
    for dependency, _action in dependencies:
        assert dependency.dependency(user=user, db=db) is user


def test_shift_catalog_create_list_detail_update_and_soft_deactivate(db, user):
    _grant(db, "read")
    _grant(db, "write")

    created = hr_shifts.create_shift(_shift_payload(code="day_a"), db, user)
    shift_id = created["id"]
    assert created["code"] == "DAY_A"
    assert created["active"] is True
    assert created["break_rules"] == []

    assert [row.id for row in hr_shifts.list_shifts(False, db, user)] == [shift_id]
    assert hr_shifts.get_shift(shift_id, db, user)["name"] == "Day Shift"

    updated = hr_shifts.update_shift(
        shift_id,
        _shift_payload(code="DAY_A", name="General Shift", start=time(8), end=time(16)),
        db,
        user,
    )
    assert updated["name"] == "General Shift"
    assert updated["start_time"] == time(8)

    inactive = hr_shifts.set_shift_active(
        shift_id, schemas.ShiftActiveIn(active=False), db, user,
    )
    assert inactive.active is False
    assert hr_shifts.list_shifts(False, db, user) == []
    assert hr_shifts.list_shifts(True, db, user)[0].id == shift_id


def test_shift_code_is_immutable_and_schedule_cannot_change_after_assignment(db, user):
    _grant(db, "write")
    shift = hr_shifts.create_shift(_shift_payload(), db, user)

    with pytest.raises(HTTPException) as immutable_code:
        hr_shifts.update_shift(
            shift["id"],
            _shift_payload(code="RENAMED", name="Renamed"),
            db,
            user,
        )
    assert immutable_code.value.status_code == 422

    employee = models.Employee(
        id="shift-assigned-employee", emp_code="SA001", name="Assigned",
    )
    db.add(employee)
    db.add(models.HRShiftAssignment(
        scope_type="employee", employee_id=employee.id, branch_id=None,
        department=None, shift_type_id=shift["id"], weekdays=[0, 1, 2, 3, 4],
        valid_from=__import__("datetime").date(2026, 1, 1),
        valid_to=None, created_by=user.username,
    ))
    db.commit()

    with pytest.raises(HTTPException) as schedule_locked:
        hr_shifts.update_shift(
            shift["id"],
            _shift_payload(name="Changed hours", start=time(10), end=time(18)),
            db,
            user,
        )
    assert schedule_locked.value.status_code == 409


def test_overnight_shift_and_break_rules_validate_against_local_window(db, user):
    _grant(db, "read")
    _grant(db, "write")
    shift = hr_shifts.create_shift(
        _shift_payload(code="NIGHT", name="Night Shift", start=time(22), end=time(6), offset=1),
        db,
        user,
    )

    rule = hr_shifts.create_break_rule(
        shift["id"],
        schemas.ShiftBreakRuleIn(
            code="MEAL", name="Meal Break", sequence=1, is_paid=False,
            planned_duration_minutes=30,
            scheduled_start_time=time(1), scheduled_end_time=time(1, 30),
        ),
        db,
        user,
    )
    assert rule.code == "MEAL"
    assert rule.active is True
    assert len(hr_shifts.list_break_rules(shift["id"], False, db, user)) == 1

    with pytest.raises(HTTPException) as outside_shift:
        hr_shifts.create_break_rule(
            shift["id"],
            schemas.ShiftBreakRuleIn(
                code="LATE", name="Outside Shift", planned_duration_minutes=15,
                scheduled_start_time=time(8), scheduled_end_time=time(8, 15),
            ),
            db,
            user,
        )
    assert outside_shift.value.status_code == 422


def test_break_rule_code_immutable_and_deactivation_is_soft(db, user):
    _grant(db, "read")
    _grant(db, "write")
    shift = hr_shifts.create_shift(_shift_payload(), db, user)
    rule = hr_shifts.create_break_rule(
        shift["id"],
        schemas.ShiftBreakRuleIn(
            code="TEA", name="Tea Break", planned_duration_minutes=15,
        ),
        db,
        user,
    )

    with pytest.raises(HTTPException) as immutable_code:
        hr_shifts.update_break_rule(
            shift["id"], rule.id,
            schemas.ShiftBreakRuleIn(
                code="COFFEE", name="Coffee Break", planned_duration_minutes=15,
            ),
            db,
            user,
        )
    assert immutable_code.value.status_code == 422

    inactive = hr_shifts.set_break_rule_active(
        shift["id"], rule.id, schemas.ShiftBreakRuleActiveIn(active=False), db, user,
    )
    assert inactive.active is False
    assert hr_shifts.list_break_rules(shift["id"], False, db, user) == []
    assert hr_shifts.list_break_rules(shift["id"], True, db, user)[0].id == rule.id


@pytest.mark.parametrize(
    ("start", "end", "offset"),
    [
        (time(9), time(9), 0),
        (time(17), time(9), 0),
        (time(8), time(17), 1),
    ],
)
def test_shift_schema_rejects_invalid_or_longer_than_24_hour_windows(start, end, offset):
    with pytest.raises(ValueError):
        _shift_payload(start=start, end=end, offset=offset)


def test_duplicate_shift_and_break_codes_return_conflict(db, user):
    _grant(db, "write")
    first = hr_shifts.create_shift(_shift_payload(), db, user)
    with pytest.raises(HTTPException) as duplicate_shift:
        hr_shifts.create_shift(_shift_payload(name="Duplicate"), db, user)
    assert duplicate_shift.value.status_code == 409

    payload = schemas.ShiftBreakRuleIn(
        code="MEAL", name="Meal", planned_duration_minutes=30,
    )
    hr_shifts.create_break_rule(first["id"], payload, db, user)
    with pytest.raises(HTTPException) as duplicate_break:
        hr_shifts.create_break_rule(first["id"], payload, db, user)
    assert duplicate_break.value.status_code == 409
