"""Regression tests for the P0.1 shift assignment engine."""
from datetime import date, time
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.modules.hr.shift_assignment import (
    ShiftAssignmentConfigurationError,
    create_shift_assignment,
    resolve_shift_for_work_date,
    resolve_shift_window,
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


def _seed_employee_and_branch(db: Session):
    branch = models.HRBranch(code="PUN", name="Pune", timezone="Asia/Kolkata")
    employee = models.Employee(
        id="shift-employee", emp_code="SH001", name="Shift Employee",
        department="Production", joining_date=date(2026, 1, 1), active=True,
    )
    db.add_all([branch, employee])
    db.flush()
    db.add(models.EmployeeOrgAssignment(
        employee_id=employee.id, branch_id=branch.id, department="Production",
        valid_from=date(2026, 1, 1), created_by="admin",
    ))
    db.flush()
    return employee, branch


def _shift(db: Session, code: str, start: time, end: time, offset: int = 0):
    row = models.HRShiftType(
        code=code, name=code, start_time=start, end_time=end,
        end_day_offset=offset, active=True, created_by="admin",
    )
    db.add(row)
    db.flush()
    return row


def _assignment(db: Session, *, scope_type: str, shift_id: str, employee_id=None,
                branch_id=None, department=None, weekdays=None, valid_from=date(2026, 1, 1),
                valid_to=None):
    row = models.HRShiftAssignment(
        scope_type=scope_type, employee_id=employee_id, branch_id=branch_id,
        department=department, shift_type_id=shift_id,
        weekdays=weekdays or [0, 1, 2, 3, 4],
        valid_from=valid_from, valid_to=valid_to, created_by="admin",
    )
    db.add(row)
    db.flush()
    return row


def test_employee_assignment_precedes_department_default(db):
    employee, branch = _seed_employee_and_branch(db)
    default_shift = _shift(db, "DAY", time(9), time(17))
    employee_shift = _shift(db, "EARLY", time(7), time(15))
    _assignment(
        db, scope_type="department", shift_id=default_shift.id,
        branch_id=branch.id, department="Production",
    )
    personal = _assignment(
        db, scope_type="employee", shift_id=employee_shift.id,
        employee_id=employee.id, branch_id=branch.id,
    )
    db.commit()

    result = resolve_shift_for_work_date(db, employee.id, date(2026, 1, 5))

    assert result is not None
    assert result.status == "scheduled"
    assert result.assignment.id == personal.id
    assert result.shift_type.code == "EARLY"


def test_department_default_requires_effective_org_assignment(db):
    employee, branch = _seed_employee_and_branch(db)
    shift = _shift(db, "DAY", time(9), time(17))
    assignment = _assignment(
        db, scope_type="department", shift_id=shift.id,
        branch_id=branch.id, department="Production",
    )
    db.commit()

    result = resolve_shift_for_work_date(db, employee.id, date(2026, 1, 5))

    assert result is not None
    assert result.assignment.id == assignment.id
    assert result.shift_type.id == shift.id


def test_employee_without_shift_assignment_uses_legacy_fallback(db):
    employee = models.Employee(
        id="legacy-employee", emp_code="LEG001", name="Legacy",
        department="Production", joining_date=date(2026, 1, 1), active=True,
    )
    db.add(employee)
    db.commit()

    assert resolve_shift_for_work_date(db, employee.id, date(2026, 1, 5)) is None


def test_employee_assignment_weekday_pattern_resolves_weekly_off(db):
    employee, branch = _seed_employee_and_branch(db)
    shift = _shift(db, "MON", time(9), time(17))
    _assignment(
        db, scope_type="employee", shift_id=shift.id,
        employee_id=employee.id, branch_id=branch.id, weekdays=[0],
    )
    db.commit()

    result = resolve_shift_for_work_date(db, employee.id, date(2026, 1, 6))

    assert result is not None
    assert result.status == "weekly_off"
    assert result.scheduled_start_at_utc is None
    assert result.scheduled_end_at_utc is None


def test_date_specific_roster_entry_precedes_recurring_assignment(db):
    employee, branch = _seed_employee_and_branch(db)
    shift = _shift(db, "DAY", time(9), time(17))
    assignment = _assignment(
        db, scope_type="employee", shift_id=shift.id,
        employee_id=employee.id, branch_id=branch.id,
    )
    roster = models.HRShiftRosterEntry(
        employee_id=employee.id, work_date=date(2026, 1, 5),
        status="cancelled", shift_type_id=None, source_assignment_id=assignment.id,
        is_override=True, override_reason="Plant shutdown", branch_id=branch.id,
        department_snapshot="Production", timezone_name="Asia/Kolkata",
        break_rules_snapshot=[], created_by="admin",
    )
    db.add(roster)
    db.commit()

    result = resolve_shift_for_work_date(db, employee.id, date(2026, 1, 5))

    assert result is not None
    assert result.status == "cancelled"
    assert result.roster_entry.id == roster.id


def test_conflicting_global_and_branch_department_defaults_fail_closed(db):
    employee, branch = _seed_employee_and_branch(db)
    global_shift = _shift(db, "GLOBAL", time(9), time(17))
    branch_shift = _shift(db, "BRANCH", time(8), time(16))
    _assignment(db, scope_type="department", shift_id=global_shift.id, department="Production")
    _assignment(
        db, scope_type="department", shift_id=branch_shift.id,
        branch_id=branch.id, department="Production",
    )
    db.commit()

    with pytest.raises(ShiftAssignmentConfigurationError, match="Conflicting department"):
        resolve_shift_for_work_date(db, employee.id, date(2026, 1, 5))


def test_new_effective_assignment_closes_and_supersedes_previous_period(db):
    employee, branch = _seed_employee_and_branch(db)
    first_shift = _shift(db, "DAY", time(9), time(17))
    second_shift = _shift(db, "LATE", time(12), time(20))
    first = create_shift_assignment(
        db, scope_type="employee", employee_id=employee.id, branch_id=branch.id,
        shift_type_id=first_shift.id, weekdays=[0, 1, 2, 3, 4],
        valid_from=date(2026, 1, 1), valid_to=None, created_by="admin",
    )
    second = create_shift_assignment(
        db, scope_type="employee", employee_id=employee.id, branch_id=branch.id,
        shift_type_id=second_shift.id, weekdays=[0, 1, 2, 3, 4],
        valid_from=date(2026, 3, 1), valid_to=None, created_by="admin",
    )
    db.commit()

    assert first.valid_to == date(2026, 2, 28)
    assert second.supersedes_assignment_id == first.id
    assert resolve_shift_for_work_date(db, employee.id, date(2026, 2, 27)).shift_type.code == "DAY"
    assert resolve_shift_for_work_date(db, employee.id, date(2026, 3, 2)).shift_type.code == "LATE"


def test_assignment_creation_rejects_overlapping_future_or_ambiguous_periods(db):
    employee, branch = _seed_employee_and_branch(db)
    first_shift = _shift(db, "DAY", time(9), time(17))
    second_shift = _shift(db, "LATE", time(12), time(20))
    create_shift_assignment(
        db, scope_type="employee", employee_id=employee.id, branch_id=branch.id,
        shift_type_id=first_shift.id, weekdays=[0, 1, 2, 3, 4],
        valid_from=date(2026, 2, 1), valid_to=None, created_by="admin",
    )
    db.flush()

    with pytest.raises(ShiftAssignmentConfigurationError, match="overlaps"):
        create_shift_assignment(
            db, scope_type="employee", employee_id=employee.id, branch_id=branch.id,
            shift_type_id=second_shift.id, weekdays=[0, 1, 2, 3, 4],
            valid_from=date(2026, 1, 15), valid_to=None, created_by="admin",
        )


def test_overnight_shift_window_uses_shift_start_work_date_and_branch_timezone(db):
    shift = _shift(db, "NIGHT", time(22), time(6), offset=1)

    start_utc, end_utc = resolve_shift_window(date(2026, 11, 10), shift, "Asia/Kolkata")

    assert start_utc.isoformat() == "2026-11-10T16:30:00+00:00"
    assert end_utc.isoformat() == "2026-11-11T00:30:00+00:00"


@pytest.mark.parametrize(
    ("work_date", "start", "end", "offset", "message"),
    [
        (date(2026, 3, 8), time(2, 30), time(4), 0, "does not exist"),
        (date(2026, 11, 1), time(1, 30), time(3), 0, "ambiguous"),
    ],
)
def test_daylight_saving_ambiguous_or_nonexistent_boundaries_fail_closed(
    db, work_date, start, end, offset, message,
):
    shift = _shift(db, "DST", start, end, offset)

    with pytest.raises(ShiftAssignmentConfigurationError, match=message):
        resolve_shift_window(work_date, shift, "America/New_York")


def test_temporary_assignment_cannot_truncate_an_open_ended_future_schedule(db):
    employee, branch = _seed_employee_and_branch(db)
    first_shift = _shift(db, "DAY", time(9), time(17))
    temporary_shift = _shift(db, "TEMP", time(10), time(18))
    existing = create_shift_assignment(
        db, scope_type="employee", employee_id=employee.id, branch_id=branch.id,
        shift_type_id=first_shift.id, weekdays=[0, 1, 2, 3, 4],
        valid_from=date(2026, 1, 1), valid_to=None, created_by="admin",
    )
    db.flush()

    with pytest.raises(ShiftAssignmentConfigurationError, match="overlaps"):
        create_shift_assignment(
            db, scope_type="employee", employee_id=employee.id, branch_id=branch.id,
            shift_type_id=temporary_shift.id, weekdays=[0, 1, 2, 3, 4],
            valid_from=date(2026, 3, 1), valid_to=date(2026, 3, 31), created_by="admin",
        )

    assert existing.valid_to is None


def test_shift_resolution_stops_outside_employee_employment_dates(db):
    employee = models.Employee(
        id="bounded-employee", emp_code="BND001", name="Bounded employment",
        department="Production", joining_date=date(2026, 1, 10),
        end_date=date(2026, 1, 20), active=False,
    )
    db.add(employee)
    db.flush()
    shift = _shift(db, "DAY", time(9), time(17))
    _assignment(
        db, scope_type="employee", shift_id=shift.id, employee_id=employee.id,
        weekdays=[0, 1, 2, 3, 4, 5, 6],
        valid_from=date(2026, 1, 10), valid_to=date(2026, 1, 20),
    )
    db.commit()

    assert resolve_shift_for_work_date(db, employee.id, date(2026, 1, 9)) is None
    assert resolve_shift_for_work_date(db, employee.id, date(2026, 1, 21)) is None
