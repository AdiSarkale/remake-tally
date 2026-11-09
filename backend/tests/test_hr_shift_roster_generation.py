"""Tests for deterministic and safe P0.1-04 roster generation."""
from datetime import date, time, timedelta
import inspect

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi import HTTPException
from fastapi.params import Depends as DependsParam

from app import models
from app.api.routes import hr_shift_rosters
from app.modules.hr.shift_roster_schemas import ShiftRosterGenerateIn, ShiftRosterOverrideIn
from app.modules.hr.shift_roster_generation import (
    ShiftRosterGenerationError,
    generate_shift_roster,
)


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


def _seed(db, *, weekdays=None, department="Production", branch_timezone="Asia/Kolkata"):
    branch = models.HRBranch(code="PUN", name="Pune", timezone=branch_timezone)
    employee = models.Employee(
        id="roster-employee", emp_code="RS001", name="Roster Employee",
        department=department, joining_date=date(2039, 1, 1), active=True,
    )
    shift = models.HRShiftType(
        id="roster-shift", code="DAY", name="Day Shift",
        start_time=time(9), end_time=time(17), end_day_offset=0,
        active=True, created_by="admin",
    )
    db.add_all([branch, employee, shift])
    db.flush()
    db.add(models.EmployeeOrgAssignment(
        employee_id=employee.id, branch_id=branch.id, department=department,
        valid_from=date(2039, 1, 1), created_by="admin",
    ))
    db.add(models.HRShiftAssignment(
        id="roster-assignment", scope_type="employee", employee_id=employee.id,
        branch_id=branch.id, department=None, shift_type_id=shift.id,
        weekdays=weekdays or [0, 1, 2, 3, 4],
        valid_from=date(2039, 1, 1), valid_to=None, created_by="admin",
    ))
    db.add(models.HRPayrollSettings(id=1, week_off_days="5,6", timezone="Asia/Kolkata"))
    db.commit()
    return employee, branch, shift


def _generate(db, employee, start=date(2040, 1, 2), end=date(2040, 1, 8), **kwargs):
    return generate_shift_roster(
        db, start_date=start, end_date=end, created_by="test",
        employee_ids=[employee.id], **kwargs,
    )


def test_generates_scheduled_and_weekly_off_rows_and_is_idempotent(db):
    employee, _, _ = _seed(db)
    first = _generate(db, employee)
    assert first.created_count == 7
    assert first.scheduled_count == 5
    assert first.weekly_off_count == 2
    assert first.holiday_count == 0
    assert db.query(models.HRShiftRosterEntry).count() == 7

    second = _generate(db, employee)
    assert second.created_count == 0
    assert second.skipped_existing_count == 7
    assert db.query(models.HRShiftRosterEntry).count() == 7


def test_generation_preserves_existing_manual_override(db):
    employee, branch, shift = _seed(db)
    override_date = date(2040, 1, 3)
    db.add(models.HRShiftRosterEntry(
        employee_id=employee.id, work_date=override_date, status="scheduled",
        shift_type_id=shift.id, source_assignment_id=None, is_override=True,
        override_reason="Approved production demand", branch_id=branch.id,
        department_snapshot="Production", timezone_name="Asia/Kolkata",
        scheduled_start_at_utc=__import__("datetime").datetime(2040, 1, 3, 3, 30),
        scheduled_end_at_utc=__import__("datetime").datetime(2040, 1, 3, 11, 30),
        shift_code_snapshot="MANUAL", shift_name_snapshot="Manual Shift",
        break_rules_snapshot=[], policy_version_id=None, created_by="hr",
    ))
    db.commit()

    result = _generate(db, employee)
    row = db.query(models.HRShiftRosterEntry).filter_by(
        employee_id=employee.id, work_date=override_date,
    ).one()
    assert row.is_override is True
    assert row.override_reason == "Approved production demand"
    assert row.shift_code_snapshot == "MANUAL"
    assert result.skipped_existing_count == 1


def test_holiday_on_assigned_workday_requires_explicit_versioned_policy(db):
    employee, _, _ = _seed(db)
    holiday = date(2040, 1, 3)
    db.add(models.HRCalendarDay(work_date=holiday, day_type="holiday", description="Plant holiday"))
    db.commit()

    with pytest.raises(ShiftRosterGenerationError, match="precedence policy is required"):
        _generate(db, employee, start=holiday, end=holiday)
    assert db.query(models.HRShiftRosterEntry).count() == 0

    policy = models.HRWorkforcePolicyVersion(
        version_code="ROSTER-2040-01", effective_from=date(2040, 1, 1),
        configuration={"holiday_roster_precedence": "holiday_overrides_roster"},
        created_by="admin",
    )
    db.add(policy)
    db.commit()
    result = _generate(db, employee, start=holiday, end=holiday)
    row = db.query(models.HRShiftRosterEntry).filter_by(
        employee_id=employee.id, work_date=holiday,
    ).one()
    assert result.holiday_count == 1
    assert row.status == "holiday"
    assert row.shift_type_id is None
    assert row.policy_version_id == policy.id


def test_roster_wins_policy_preserves_scheduled_shift_on_holiday(db):
    employee, _, shift = _seed(db)
    holiday = date(2040, 1, 3)
    policy = models.HRWorkforcePolicyVersion(
        version_code="ROSTER-2040-02", effective_from=date(2040, 1, 1),
        configuration={"holiday_roster_precedence": "roster_overrides_holiday"},
        created_by="admin",
    )
    db.add_all([
        models.HRCalendarDay(work_date=holiday, day_type="holiday", description="Plant holiday"),
        policy,
    ])
    db.commit()

    result = _generate(db, employee, start=holiday, end=holiday)
    row = db.query(models.HRShiftRosterEntry).filter_by(
        employee_id=employee.id, work_date=holiday,
    ).one()
    assert result.scheduled_count == 1
    assert row.status == "scheduled"
    assert row.shift_type_id == shift.id
    assert row.policy_version_id == policy.id


def test_legacy_calendar_and_week_off_fallback_when_no_shift_assignment(db):
    branch = models.HRBranch(code="PUN", name="Pune", timezone="Asia/Kolkata")
    employee = models.Employee(
        id="legacy-employee", emp_code="LEG001", name="Legacy Employee",
        joining_date=date(2039, 1, 1), active=True,
    )
    db.add_all([
        branch, employee,
        models.EmployeeOrgAssignment(
            employee_id=employee.id, branch_id=branch.id, department="Production",
            valid_from=date(2039, 1, 1), created_by="admin",
        ),
        models.HRPayrollSettings(id=1, week_off_days="5,6", timezone="Asia/Kolkata"),
        models.HRCalendarDay(work_date=date(2040, 1, 3), day_type="holiday", description="Holiday"),
    ])
    db.commit()

    result = _generate(db, employee, start=date(2040, 1, 2), end=date(2040, 1, 8))
    rows = db.query(models.HRShiftRosterEntry).filter_by(employee_id=employee.id).all()
    statuses = {row.work_date: row.status for row in rows}
    assert statuses[date(2040, 1, 3)] == "holiday"
    assert statuses[date(2040, 1, 8)] == "weekly_off"
    assert result.unassigned_working_day_count == 4
    assert result.created_count == 3


def test_generation_rejects_frozen_payroll_period(db):
    employee, _, _ = _seed(db)
    db.add(models.HRPayrollRun(
        id="frozen-run", year=2040, month=1, status="approved",
        created_by="payroll-admin", revision=1,
    ))
    db.commit()
    with pytest.raises(ShiftRosterGenerationError, match="payroll run status"):
        _generate(db, employee)


def test_generation_rejects_historical_dates(db):
    employee, _, _ = _seed(db)
    yesterday = date.today() - timedelta(days=3)
    employee.joining_date = yesterday - timedelta(days=30)
    org = db.query(models.EmployeeOrgAssignment).filter_by(employee_id=employee.id).one()
    org.valid_from = yesterday - timedelta(days=30)
    assignment = db.query(models.HRShiftAssignment).filter_by(employee_id=employee.id).one()
    assignment.valid_from = yesterday - timedelta(days=30)
    db.commit()
    with pytest.raises(ShiftRosterGenerationError, match="Historical roster generation"):
        _generate(db, employee, start=yesterday, end=yesterday)


def test_branch_and_department_filters_are_applied_per_effective_work_date(db):
    employee, branch, _ = _seed(db)
    result = generate_shift_roster(
        db, start_date=date(2040, 1, 2), end_date=date(2040, 1, 8),
        created_by="test", branch_id=branch.id, department="Production",
    )
    assert result.employee_count == 1
    assert result.created_count == 7



def test_controlled_override_preserves_each_previous_roster_version(db):
    from app.modules.hr.shift_roster_generation import apply_shift_roster_override

    employee, branch, original_shift = _seed(db)
    work_date = date(2040, 1, 3)
    _generate(db, employee, start=work_date, end=work_date)
    revised_shift = models.HRShiftType(
        id="roster-shift-late", code="LATE", name="Late Shift",
        start_time=time(12), end_time=time(20), end_day_offset=0,
        active=True, created_by="admin",
    )
    db.add(revised_shift)
    db.commit()

    row = apply_shift_roster_override(
        db, employee_id=employee.id, work_date=work_date,
        status="scheduled", shift_type_id=revised_shift.id,
        reason="Approved production coverage change", changed_by="hr-user",
    )
    assert row.version == 2
    assert row.is_override is True
    assert row.shift_type_id == revised_shift.id
    first_history = db.query(models.HRShiftRosterEntryHistory).filter_by(
        roster_entry_id=row.id, version=1,
    ).one()
    assert first_history.snapshot["shift_type_id"] == original_shift.id
    assert first_history.snapshot["status"] == "scheduled"

    row = apply_shift_roster_override(
        db, employee_id=employee.id, work_date=work_date,
        status="weekly_off", shift_type_id=None,
        reason="Approved plant shutdown for maintenance", changed_by="hr-user",
    )
    assert row.version == 3
    assert row.status == "weekly_off"
    assert db.query(models.HRShiftRosterEntryHistory).filter_by(
        roster_entry_id=row.id,
    ).count() == 2


def test_manual_schedule_override_on_holiday_requires_roster_wins_policy(db):
    from app.modules.hr.shift_roster_generation import apply_shift_roster_override

    employee, _, shift = _seed(db)
    work_date = date(2040, 1, 3)
    db.add(models.HRCalendarDay(work_date=work_date, day_type="holiday", description="Plant holiday"))
    db.commit()

    with pytest.raises(ShiftRosterGenerationError, match="requires an effective workforce policy"):
        apply_shift_roster_override(
            db, employee_id=employee.id, work_date=work_date,
            status="scheduled", shift_type_id=shift.id,
            reason="Approved holiday production coverage", changed_by="hr-user",
        )

    policy = models.HRWorkforcePolicyVersion(
        version_code="OVERRIDE-2040", effective_from=date(2040, 1, 1),
        configuration={"holiday_roster_precedence": "roster_overrides_holiday"},
        created_by="admin",
    )
    db.add(policy)
    db.commit()
    row = apply_shift_roster_override(
        db, employee_id=employee.id, work_date=work_date,
        status="scheduled", shift_type_id=shift.id,
        reason="Approved holiday production coverage", changed_by="hr-user",
    )
    assert row.status == "scheduled"
    assert row.is_override is True
    assert row.policy_version_id == policy.id



def test_roster_generation_route_requires_exact_write_permission_and_employee_scope(db):
    user = models.User(
        id="roster-admin", username="roster-admin", full_name="Roster Admin",
        password_hash="test", role=models.Role.admin, active=True,
        must_change_password=False,
    )
    db.add(user)
    db.commit()
    dependency = inspect.signature(hr_shift_rosters.generate_rosters).parameters["user"].default
    assert isinstance(dependency, DependsParam)
    with pytest.raises(HTTPException) as denied:
        dependency.dependency(user=user, db=db)
    assert denied.value.status_code == 403

    db.add(models.RolePermissionGrant(
        role="Admin", module="hr", feature="shift_rosters", action="write",
        data_scope="tenant", allowed=True, updated_by="test",
    ))
    db.add(models.RolePermissionGrant(
        role="Admin", module="hr", feature="employees", action="update",
        data_scope="tenant", allowed=True, updated_by="test",
    ))
    db.commit()
    assert dependency.dependency(user=user, db=db) is user

    employee, _, _ = _seed(db)
    response = hr_shift_rosters.generate_rosters(
        ShiftRosterGenerateIn(
            start_date=date(2040, 1, 2), end_date=date(2040, 1, 8),
            employee_ids=[employee.id],
        ),
        db,
        user,
    )
    assert response.created_count == 7


def test_roster_override_request_requires_a_reason_and_valid_shift_shape():
    with pytest.raises(ValueError):
        ShiftRosterOverrideIn(status="scheduled", shift_type_id=None, reason="Short")
    with pytest.raises(ValueError):
        ShiftRosterOverrideIn(status="weekly_off", shift_type_id="shift", reason="Approved maintenance day")
    valid = ShiftRosterOverrideIn(
        status="cancelled", shift_type_id=None,
        reason="Approved line shutdown for maintenance",
    )
    assert valid.reason.startswith("Approved")
