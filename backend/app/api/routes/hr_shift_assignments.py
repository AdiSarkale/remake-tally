"""Tenant-scoped effective-dated shift assignment APIs."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import employee_scope_ids, require_permission
from app.db.session import get_db
from app.modules.core.audit import log_audit
from app.modules.hr.shift_assignment import (
    ShiftAssignmentConfigurationError,
    create_shift_assignment,
)

router = APIRouter(prefix="/hr/shift-assignments", tags=["hr", "shift-assignments"])
read_access = Depends(require_permission("hr", "shift_assignments", "read", "tenant"))
write_access = Depends(require_permission("hr", "shift_assignments", "write", "tenant"))


def _get_assignment(db: Session, assignment_id: str) -> models.HRShiftAssignment:
    row = db.get(models.HRShiftAssignment, assignment_id)
    if row is None:
        raise HTTPException(404, "Shift assignment not found")
    return row


def _allowed_employee_ids(
    db: Session, user: models.User, action: str, as_of_date: date,
) -> set[str] | None:
    ids = employee_scope_ids(
        db, user, "hr", "employees", action, as_of_date=as_of_date,
    )
    return None if ids is None else set(ids)


def _assert_employee_scope(
    db: Session, user: models.User, employee_id: str, action: str, as_of_date: date,
) -> None:
    allowed = _allowed_employee_ids(db, user, action, as_of_date)
    if allowed is not None and employee_id not in allowed:
        raise HTTPException(403, "Employee is outside your configured access scope for this effective date")


def _assert_department_scope(
    db: Session, user: models.User, department: str, branch_id: str | None,
    action: str, as_of_date: date,
) -> None:
    allowed = _allowed_employee_ids(db, user, action, as_of_date)
    if allowed is None:
        return
    # A scoped user cannot create a global department default: it would affect
    # employees outside the user's branch/team. Permit a branch default only
    # when every currently assigned employee in that department is in scope.
    if branch_id is None:
        raise HTTPException(403, "Scoped access cannot create or view a global department default")
    org_rows = db.query(models.EmployeeOrgAssignment).filter(
        models.EmployeeOrgAssignment.branch_id == branch_id,
        models.EmployeeOrgAssignment.department.ilike(department),
        models.EmployeeOrgAssignment.valid_from <= as_of_date,
        (
            models.EmployeeOrgAssignment.valid_to.is_(None)
            | (models.EmployeeOrgAssignment.valid_to >= as_of_date)
        ),
    ).all()
    employee_ids = {row.employee_id for row in org_rows}
    if not employee_ids or not employee_ids.issubset(allowed):
        raise HTTPException(403, "Department default would affect employees outside your configured access scope")


def _authorize_assignment(
    db: Session, user: models.User, row: models.HRShiftAssignment, action: str,
) -> None:
    if row.scope_type == "employee":
        _assert_employee_scope(
            db, user, row.employee_id, action, row.valid_from,
        )
    else:
        _assert_department_scope(
            db, user, row.department, row.branch_id, action, row.valid_from,
        )


def _validate_employee_branch(
    db: Session, employee_id: str, branch_id: str | None,
    effective_date: date, effective_to: date | None,
) -> None:
    query = db.query(models.EmployeeOrgAssignment).filter(
        models.EmployeeOrgAssignment.employee_id == employee_id,
        models.EmployeeOrgAssignment.valid_from <= (effective_to or date.max),
        (
            models.EmployeeOrgAssignment.valid_to.is_(None)
            | (models.EmployeeOrgAssignment.valid_to >= effective_date)
        ),
    )
    rows = query.order_by(models.EmployeeOrgAssignment.valid_from).all()
    for index, left in enumerate(rows):
        for right in rows[index + 1:]:
            if left.valid_to is None or right.valid_from <= left.valid_to:
                raise HTTPException(409, "Employee has overlapping organization assignments during the shift assignment period")
    if branch_id and any(row.branch_id and row.branch_id != branch_id for row in rows):
        raise HTTPException(422, "Shift assignment branch must match the employee's branch throughout its effective period")


def _create_or_conflict(db: Session, user: models.User, payload: schemas.ShiftAssignmentIn):
    if payload.scope_type == "employee":
        _assert_employee_scope(
            db, user, payload.employee_id, "update", payload.valid_from,
        )
        _validate_employee_branch(
            db, payload.employee_id, payload.branch_id,
            payload.valid_from, payload.valid_to,
        )
    else:
        _assert_department_scope(
            db, user, payload.department, payload.branch_id, "update", payload.valid_from,
        )
    try:
        row = create_shift_assignment(
            db,
            scope_type=payload.scope_type,
            employee_id=payload.employee_id,
            branch_id=payload.branch_id,
            department=payload.department,
            shift_type_id=payload.shift_type_id,
            weekdays=payload.weekdays,
            valid_from=payload.valid_from,
            valid_to=payload.valid_to,
            created_by=user.username,
        )
        if row.supersedes_assignment_id:
            previous = db.get(models.HRShiftAssignment, row.supersedes_assignment_id)
            if previous is not None:
                log_audit(
                    db, user.username, "UPDATE", "hr_shift_assignment",
                    f"{previous.id}; closed at {previous.valid_to}; superseded by {row.id}",
                )
        log_audit(
            db, user.username, "CREATE", "hr_shift_assignment",
            f"{row.id}; scope={row.scope_type}; employee={row.employee_id}; "
            f"branch={row.branch_id}; department={row.department}; shift={row.shift_type_id}; "
            f"weekdays={row.weekdays}; effective={row.valid_from}..{row.valid_to}",
        )
        db.commit()
        db.refresh(row)
        return row
    except ShiftAssignmentConfigurationError as exc:
        db.rollback()
        message = str(exc)
        status_code = 409 if "overlap" in message.lower() or "conflict" in message.lower() else 422
        raise HTTPException(status_code, message) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Shift assignment conflicts with existing data") from exc


@router.get("", response_model=list[schemas.ShiftAssignmentOut])
def list_shift_assignments(
    scope_type: str | None = Query(default=None, pattern="^(employee|department)$"),
    employee_id: str | None = None,
    branch_id: str | None = None,
    department: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = read_access,
):
    query = db.query(models.HRShiftAssignment)
    if scope_type:
        query = query.filter(models.HRShiftAssignment.scope_type == scope_type)
    if employee_id:
        query = query.filter(models.HRShiftAssignment.employee_id == employee_id)
    if branch_id:
        query = query.filter(models.HRShiftAssignment.branch_id == branch_id)
    if department:
        query = query.filter(models.HRShiftAssignment.department.ilike(department.strip()))
    rows = query.order_by(
        models.HRShiftAssignment.valid_from.desc(),
        models.HRShiftAssignment.created_at.desc(),
    ).offset(offset).limit(limit).all()
    visible = []
    for row in rows:
        try:
            _authorize_assignment(db, user, row, "read")
        except HTTPException as exc:
            if exc.status_code == 403:
                continue
            raise
        visible.append(row)
    return visible


@router.post("", response_model=schemas.ShiftAssignmentOut, status_code=201)
def create_assignment(
    payload: schemas.ShiftAssignmentIn,
    db: Session = Depends(get_db),
    user: models.User = write_access,
):
    return _create_or_conflict(db, user, payload)


@router.get("/{assignment_id}", response_model=schemas.ShiftAssignmentOut)
def get_assignment(
    assignment_id: str,
    db: Session = Depends(get_db),
    user: models.User = read_access,
):
    row = _get_assignment(db, assignment_id)
    _authorize_assignment(db, user, row, "read")
    return row


@router.put("/{assignment_id}", response_model=schemas.ShiftAssignmentOut)
def revise_assignment(
    assignment_id: str,
    payload: schemas.ShiftAssignmentIn,
    db: Session = Depends(get_db),
    user: models.User = write_access,
):
    current = _get_assignment(db, assignment_id)
    _authorize_assignment(db, user, current, "update")
    if (
        payload.scope_type != current.scope_type
        or payload.employee_id != current.employee_id
        or payload.branch_id != current.branch_id
        or (payload.department or "").casefold() != (current.department or "").casefold()
    ):
        raise HTTPException(422, "Assignment target and scope are immutable; create a separate assignment for a different target")
    if payload.valid_from <= current.valid_from:
        raise HTTPException(422, "A revised assignment must start after the existing assignment's effective start date")
    return _create_or_conflict(db, user, payload)


@router.patch("/{assignment_id}/end", response_model=schemas.ShiftAssignmentOut)
def end_assignment(
    assignment_id: str,
    payload: schemas.ShiftAssignmentEndIn,
    db: Session = Depends(get_db),
    user: models.User = write_access,
):
    row = _get_assignment(db, assignment_id)
    _authorize_assignment(db, user, row, "update")
    if payload.valid_to < row.valid_from:
        raise HTTPException(422, "Assignment end date cannot precede its effective start date")
    if row.valid_to is not None and payload.valid_to > row.valid_to:
        raise HTTPException(409, "Ending an assignment cannot extend its existing effective period")
    if row.valid_to == payload.valid_to:
        return row
    previous_end = row.valid_to
    row.valid_to = payload.valid_to
    log_audit(
        db, user.username, "UPDATE", "hr_shift_assignment",
        f"{row.id}; valid_to changed from {previous_end} to {row.valid_to}",
    )
    db.commit()
    db.refresh(row)
    return row
