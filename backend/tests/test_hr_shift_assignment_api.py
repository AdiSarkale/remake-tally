"""Tests for the P0.1 shift assignment API and its access boundaries."""
import inspect
from datetime import date, time

import pytest
from fastapi import HTTPException
from fastapi.params import Depends as DependsParam
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.routes import hr_shift_assignments


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
        id="assignment-admin", username="assignment-admin", full_name="Assignment Admin",
        password_hash="test", role=models.Role.admin, active=True,
        must_change_password=False,
    )
    db.add(row)
    db.commit()
    return row


def _grant(db: Session, feature: str, action: str, data_scope: str = "tenant"):
    db.add(models.RolePermissionGrant(
        role="Admin", module="hr", feature=feature, action=action,
        data_scope=data_scope, allowed=True, updated_by="test",
    ))
    db.commit()


def _seed(db: Session):
    branch = models.HRBranch(code="PUN", name="Pune", timezone="Asia/Kolkata")
    employee = models.Employee(
        id="assignment-employee", emp_code="AS001", name="Assignment Employee",
        department="Production", joining_date=date(2026, 1, 1), active=True,
    )
    shift = models.HRShiftType(
        code="DAY", name="Day", start_time=time(9), end_time=time(17),
        end_day_offset=0, active=True, created_by="admin",
    )
    db.add_all([branch, employee, shift])
    db.flush()
    db.add(models.EmployeeOrgAssignment(
        employee_id=employee.id, branch_id=branch.id, department="Production",
        valid_from=date(2026, 1, 1), created_by="admin",
    ))
    db.commit()
    return employee, branch, shift


def _payload(employee, branch, shift, **overrides):
    values = dict(
        scope_type="employee", employee_id=employee.id, branch_id=branch.id,
        department=None, shift_type_id=shift.id, weekdays=[0, 1, 2, 3, 4],
        valid_from=date(2026, 1, 1), valid_to=None,
    )
    values.update(overrides)
    return schemas.ShiftAssignmentIn(**values)


def _write_grants(db):
    _grant(db, "shift_assignments", "read")
    _grant(db, "shift_assignments", "write")
    _grant(db, "employees", "read")
    _grant(db, "employees", "update")


def test_assignment_routes_require_exact_read_and_write_grants(db, user):
    endpoints = (
        (hr_shift_assignments.list_shift_assignments, "read"),
        (hr_shift_assignments.get_assignment, "read"),
        (hr_shift_assignments.create_assignment, "write"),
        (hr_shift_assignments.revise_assignment, "write"),
        (hr_shift_assignments.end_assignment, "write"),
    )
    dependencies = []
    for endpoint, action in endpoints:
        dependency = inspect.signature(endpoint).parameters["user"].default
        assert isinstance(dependency, DependsParam)
        assert dependency.dependency is not None
        dependencies.append(dependency)
        with pytest.raises(HTTPException) as denied:
            dependency.dependency(user=user, db=db)
        assert denied.value.status_code == 403
    _grant(db, "shift_assignments", "read")
    _grant(db, "shift_assignments", "write")
    for dependency in dependencies:
        assert dependency.dependency(user=user, db=db) is user


def test_create_list_detail_revise_and_end_employee_assignment(db, user):
    _write_grants(db)
    employee, branch, first_shift = _seed(db)
    revised_shift = models.HRShiftType(
        code="LATE", name="Late", start_time=time(12), end_time=time(20),
        end_day_offset=0, active=True, created_by="admin",
    )
    db.add(revised_shift)
    db.commit()

    first = hr_shift_assignments.create_assignment(_payload(employee, branch, first_shift), db, user)
    assert first.valid_from == date(2026, 1, 1)
    assert first.valid_to is None
    assert first.weekdays == [0, 1, 2, 3, 4]
    assert hr_shift_assignments.get_assignment(first.id, db, user).id == first.id
    assert [row.id for row in hr_shift_assignments.list_shift_assignments(None, None, None, None, 100, 0, db, user)] == [first.id]

    second = hr_shift_assignments.revise_assignment(
        first.id,
        _payload(
            employee, branch, revised_shift,
            valid_from=date(2026, 4, 1), weekdays=[0, 1, 2, 3, 4, 5],
        ),
        db,
        user,
    )
    assert first.valid_to == date(2026, 3, 31)
    assert second.supersedes_assignment_id == first.id
    assert second.shift_type_id == revised_shift.id

    ended = hr_shift_assignments.end_assignment(
        second.id, schemas.ShiftAssignmentEndIn(valid_to=date(2026, 6, 30)), db, user,
    )
    assert ended.valid_to == date(2026, 6, 30)
    audit_events = db.query(models.AuditLog).filter_by(entity="hr_shift_assignment").all()
    assert len(audit_events) == 4
    with pytest.raises(HTTPException) as cannot_extend:
        hr_shift_assignments.end_assignment(
            second.id, schemas.ShiftAssignmentEndIn(valid_to=date(2026, 7, 1)), db, user,
        )
    assert cannot_extend.value.status_code == 409


def test_department_default_is_branch_scoped_and_uses_same_assignment_engine(db, user):
    _write_grants(db)
    employee, branch, shift = _seed(db)
    payload = schemas.ShiftAssignmentIn(
        scope_type="department", employee_id=None, branch_id=branch.id,
        department="Production", shift_type_id=shift.id, weekdays=[0, 1, 2, 3, 4],
        valid_from=date(2026, 1, 1), valid_to=None,
    )
    row = hr_shift_assignments.create_assignment(payload, db, user)
    assert row.scope_type == "department"
    assert row.department == "Production"


def test_assignment_overlap_returns_conflict_and_does_not_mutate_existing(db, user):
    _write_grants(db)
    employee, branch, shift = _seed(db)
    first = hr_shift_assignments.create_assignment(_payload(employee, branch, shift), db, user)
    second_shift = models.HRShiftType(
        code="NIGHT", name="Night", start_time=time(22), end_time=time(6),
        end_day_offset=1, active=True, created_by="admin",
    )
    db.add(second_shift)
    db.commit()

    with pytest.raises(HTTPException) as conflict:
        hr_shift_assignments.create_assignment(
            _payload(
                employee, branch, second_shift,
                valid_from=date(2026, 2, 1), valid_to=date(2026, 2, 28),
            ),
            db,
            user,
        )
    assert conflict.value.status_code == 409
    db.refresh(first)
    assert first.valid_to is None


def test_assignment_branch_must_match_employee_org_assignment(db, user):
    _write_grants(db)
    employee, branch, shift = _seed(db)
    other = models.HRBranch(code="MUM", name="Mumbai", timezone="Asia/Kolkata")
    db.add(other)
    db.commit()

    with pytest.raises(HTTPException) as mismatch:
        hr_shift_assignments.create_assignment(
            _payload(employee, other, shift), db, user,
        )
    assert mismatch.value.status_code == 422


def test_scoped_user_cannot_assign_employee_outside_effective_branch_scope(db):
    employee, branch, shift = _seed(db)
    actor = models.Employee(
        id="scope-actor", emp_code="ACT001", name="Scope Actor",
        department="Production", joining_date=date(2026, 1, 1), active=True,
    )
    actor_user = models.User(
        id="scope-user", username="scope-user", full_name="Scope User",
        password_hash="test", role=models.Role.hr, active=True,
        must_change_password=False,
    )
    db.add_all([actor, actor_user])
    db.flush()
    db.add(models.EmployeeOrgAssignment(
        employee_id=actor.id, branch_id=branch.id, department="Production",
        valid_from=date(2026, 1, 1), created_by="admin",
    ))
    db.add(models.EmployeeUserLink(
        user_id=actor_user.id, employee_id=actor.id, created_by="admin",
    ))
    db.add(models.RolePermissionGrant(
        role="HR", module="hr", feature="shift_assignments", action="write",
        data_scope="tenant", allowed=True, updated_by="test",
    ))
    db.add(models.RolePermissionGrant(
        role="HR", module="hr", feature="employees", action="update",
        data_scope="branch", allowed=True, updated_by="test",
    ))
    db.commit()

    other_branch = models.HRBranch(code="NAG", name="Nagpur", timezone="Asia/Kolkata")
    other_employee = models.Employee(
        id="outside-employee", emp_code="OUT001", name="Outside",
        department="Production", joining_date=date(2026, 1, 1), active=True,
    )
    db.add_all([other_branch, other_employee])
    db.flush()
    db.add(models.EmployeeOrgAssignment(
        employee_id=other_employee.id, branch_id=other_branch.id, department="Production",
        valid_from=date(2026, 1, 1), created_by="admin",
    ))
    db.commit()

    with pytest.raises(HTTPException) as denied:
        hr_shift_assignments.create_assignment(
            _payload(other_employee, other_branch, shift), db, actor_user,
        )
    assert denied.value.status_code == 403


def test_assignment_schema_rejects_bad_weekdays_and_malformed_targets():
    with pytest.raises(ValueError):
        schemas.ShiftAssignmentIn(
            scope_type="employee", employee_id="emp", department=None,
            branch_id=None, shift_type_id="shift", weekdays=[0, 0],
            valid_from=date(2026, 1, 1),
        )
    with pytest.raises(ValueError):
        schemas.ShiftAssignmentIn(
            scope_type="department", employee_id="emp", department="Production",
            branch_id=None, shift_type_id="shift", weekdays=[0],
            valid_from=date(2026, 1, 1),
        )



def test_explicit_branch_assignment_cannot_cross_a_future_employee_branch_transfer(db, user):
    _write_grants(db)
    employee, branch, shift = _seed(db)
    other = models.HRBranch(code="MUM", name="Mumbai", timezone="Asia/Kolkata")
    db.add(other)
    org = db.query(models.EmployeeOrgAssignment).filter_by(employee_id=employee.id).one()
    org.valid_to = date(2026, 3, 31)
    db.add(models.EmployeeOrgAssignment(
        employee_id=employee.id, branch_id=other.id, department="Production",
        valid_from=date(2026, 4, 1), created_by="admin",
    ))
    db.commit()

    with pytest.raises(HTTPException) as mismatch:
        hr_shift_assignments.create_assignment(
            _payload(employee, branch, shift),
            db,
            user,
        )
    assert mismatch.value.status_code == 422


def test_branch_scoped_user_can_only_create_department_default_for_fully_scoped_branch(db):
    employee, branch, shift = _seed(db)
    actor = models.Employee(
        id="dept-scope-actor", emp_code="DSA001", name="Department Scope Actor",
        department="Production", joining_date=date(2026, 1, 1), active=True,
    )
    actor_user = models.User(
        id="dept-scope-user", username="dept-scope-user", full_name="Department Scope User",
        password_hash="test", role=models.Role.hr, active=True,
        must_change_password=False,
    )
    db.add_all([actor, actor_user])
    db.flush()
    db.add(models.EmployeeOrgAssignment(
        employee_id=actor.id, branch_id=branch.id, department="Production",
        valid_from=date(2026, 1, 1), created_by="admin",
    ))
    db.add(models.EmployeeUserLink(
        user_id=actor_user.id, employee_id=actor.id, created_by="admin",
    ))
    db.add_all([
        models.RolePermissionGrant(
            role="HR", module="hr", feature="shift_assignments", action="write",
            data_scope="tenant", allowed=True, updated_by="test",
        ),
        models.RolePermissionGrant(
            role="HR", module="hr", feature="employees", action="update",
            data_scope="branch", allowed=True, updated_by="test",
        ),
    ])
    db.commit()

    global_default = schemas.ShiftAssignmentIn(
        scope_type="department", branch_id=None, department="Production",
        shift_type_id=shift.id, weekdays=[0, 1, 2, 3, 4],
        valid_from=date(2026, 1, 1),
    )
    with pytest.raises(HTTPException) as global_denied:
        hr_shift_assignments.create_assignment(global_default, db, actor_user)
    assert global_denied.value.status_code == 403

    branch_default = schemas.ShiftAssignmentIn(
        scope_type="department", branch_id=branch.id, department="Production",
        shift_type_id=shift.id, weekdays=[0, 1, 2, 3, 4],
        valid_from=date(2026, 1, 1),
    )
    created = hr_shift_assignments.create_assignment(branch_default, db, actor_user)
    assert created.branch_id == branch.id
