"""Authorized API for idempotent, future-only shift roster generation."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.api.deps import employee_scope_ids, require_permission
from app.db.session import get_db
from app.modules.core.audit import log_audit
from app.modules.hr.shift_roster_generation import (
    ShiftRosterGenerationError,
    generate_shift_roster,
    apply_shift_roster_override,
)
from app.modules.hr.shift_roster_schemas import (
    ShiftRosterGenerateIn, ShiftRosterGenerateOut,
    ShiftRosterOverrideIn, ShiftRosterOverrideOut,
)

router = APIRouter(prefix="/hr/shift-rosters", tags=["hr", "shift-rosters"])
read_access = Depends(require_permission("hr", "shift_rosters", "read", "tenant"))
self_read_access = Depends(require_permission("hr", "shift_rosters", "read", "self"))
write_access = Depends(require_permission("hr", "shift_rosters", "write", "tenant"))


@router.get("", response_model=list[dict])
def list_shift_rosters(
    from_date: date = Query(default_factory=date.today),
    to_date: date = Query(default_factory=lambda: date.today() + timedelta(days=6)),
    employee_id: str | None = Query(default=None, max_length=36),
    branch_id: str | None = Query(default=None, max_length=36),
    department: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
    user: models.User = read_access,
):
    if to_date < from_date:
        raise HTTPException(422, "Roster end date cannot precede start date")
    if (to_date - from_date).days + 1 > 31:
        raise HTTPException(422, "Roster query cannot exceed 31 calendar days")
    query = db.query(models.HRShiftRosterEntry).filter(
        models.HRShiftRosterEntry.work_date >= from_date,
        models.HRShiftRosterEntry.work_date <= to_date,
    )
    if employee_id:
        query = query.filter(models.HRShiftRosterEntry.employee_id == employee_id)
    if branch_id:
        query = query.filter(models.HRShiftRosterEntry.branch_id == branch_id)
    if department:
        query = query.filter(models.HRShiftRosterEntry.department_snapshot.ilike(department.strip()))

    # Keep the effective-date scope check ahead of offset/limit so restricted
    # employees never consume page slots.
    visible_query = query.order_by(
        models.HRShiftRosterEntry.work_date,
        models.HRShiftRosterEntry.employee_id,
        models.HRShiftRosterEntry.id,
    )
    scoped_ids_by_date: dict[date, set[str] | None] = {}

    # A date-specific scope can vary over the selected window. A single SQL
    # IN filter cannot express that safely, so apply scope during an ordered
    # scan and stop once the requested window has been collected.
    visible = []
    skipped = 0
    rows = visible_query.yield_per(250)
    for row in rows:
        if row.work_date not in scoped_ids_by_date:
            ids = employee_scope_ids(db, user, "hr", "employees", "read", as_of_date=row.work_date)
            scoped_ids_by_date[row.work_date] = None if ids is None else set(ids)
        scoped_ids = scoped_ids_by_date[row.work_date]
        if scoped_ids is not None and row.employee_id not in scoped_ids:
            continue
        if skipped < offset:
            skipped += 1
            continue
        employee = db.get(models.Employee, row.employee_id)
        visible.append({
            "id": row.id,
            "employee_id": row.employee_id,
            "employee_code": employee.emp_code if employee else "",
            "employee_name": employee.name if employee else "",
            "work_date": row.work_date,
            "status": row.status,
            "shift_type_id": row.shift_type_id,
            "source_assignment_id": row.source_assignment_id,
            "is_override": row.is_override,
            "override_reason": row.override_reason,
            "version": row.version,
            "branch_id": row.branch_id,
            "department": row.department_snapshot,
            "timezone_name": row.timezone_name,
            "scheduled_start_at_utc": row.scheduled_start_at_utc,
            "scheduled_end_at_utc": row.scheduled_end_at_utc,
            "shift_code": row.shift_code_snapshot,
            "shift_name": row.shift_name_snapshot,
            "break_rules": row.break_rules_snapshot,
            "created_by": row.created_by,
        })
        if len(visible) >= limit:
            break
    return visible


@router.get("/self", response_model=list[dict])
def list_self_shift_rosters(
    from_date: date = Query(default_factory=date.today),
    to_date: date = Query(default_factory=lambda: date.today() + timedelta(days=6)),
    db: Session = Depends(get_db),
    user: models.User = self_read_access,
):
    if to_date < from_date:
        raise HTTPException(422, "Roster end date cannot precede start date")
    if (to_date - from_date).days + 1 > 31:
        raise HTTPException(422, "Roster query cannot exceed 31 calendar days")
    link = db.query(models.EmployeeUserLink).filter_by(user_id=user.id).first()
    if link is None:
        raise HTTPException(403, "This login is not linked to an employee")
    rows = db.query(models.HRShiftRosterEntry).filter(
        models.HRShiftRosterEntry.employee_id == link.employee_id,
        models.HRShiftRosterEntry.work_date >= from_date,
        models.HRShiftRosterEntry.work_date <= to_date,
    ).order_by(models.HRShiftRosterEntry.work_date).limit(1000).all()
    return [{
        "id": row.id,
        "employee_id": row.employee_id,
        "work_date": row.work_date,
        "status": row.status,
        "shift_code": row.shift_code_snapshot,
        "shift_name": row.shift_name_snapshot,
        "scheduled_start_at_utc": row.scheduled_start_at_utc,
        "scheduled_end_at_utc": row.scheduled_end_at_utc,
        "timezone_name": row.timezone_name,
        "department": row.department_snapshot,
        "is_override": row.is_override,
        "override_reason": row.override_reason,
        "version": row.version,
    } for row in rows]


@router.post("/generate", response_model=ShiftRosterGenerateOut)
def generate_rosters(
    payload: ShiftRosterGenerateIn,
    db: Session = Depends(get_db),
    user: models.User = write_access,
):
    scope_cache: dict[date, set[str] | None] = {}

    def authorize_employee_date(employee_id: str, work_date: date) -> None:
        if work_date not in scope_cache:
            ids = employee_scope_ids(
                db, user, "hr", "employees", "update", as_of_date=work_date,
            )
            scope_cache[work_date] = None if ids is None else set(ids)
        allowed = scope_cache[work_date]
        if allowed is not None and employee_id not in allowed:
            raise HTTPException(
                403,
                f"Employee {employee_id} is outside your configured update scope on {work_date}",
            )

    try:
        result = generate_shift_roster(
            db,
            start_date=payload.start_date,
            end_date=payload.end_date,
            created_by=user.username,
            employee_ids=payload.employee_ids,
            branch_id=payload.branch_id,
            department=payload.department,
            all_employees=payload.all_employees,
            authorize_employee_date=authorize_employee_date,
        )
        log_audit(
            db,
            user.username,
            "GENERATE",
            "hr_shift_roster",
            f"{result.start_date}..{result.end_date}; employees={result.employee_count}; "
            f"created={result.created_count}; scheduled={result.scheduled_count}; "
            f"weekly_off={result.weekly_off_count}; holiday={result.holiday_count}; "
            f"existing={result.skipped_existing_count}; outside_employment={result.skipped_outside_employment_count}; "
            f"unassigned_workdays={result.unassigned_working_day_count}",
        )
        db.commit()
        return ShiftRosterGenerateOut(
            start_date=result.start_date,
            end_date=result.end_date,
            employee_count=result.employee_count,
            created_count=result.created_count,
            scheduled_count=result.scheduled_count,
            weekly_off_count=result.weekly_off_count,
            holiday_count=result.holiday_count,
            skipped_existing_count=result.skipped_existing_count,
            skipped_outside_employment_count=result.skipped_outside_employment_count,
            unassigned_working_day_count=result.unassigned_working_day_count,
        )
    except HTTPException:
        db.rollback()
        raise
    except ShiftRosterGenerationError as exc:
        db.rollback()
        message = str(exc)
        status_code = (
            404 if "not found in this tenant" in message.lower()
            else 409 if any(token in message.lower() for token in (
                "overlap", "conflict", "blocked", "policy", "already exists",
            ))
            else 422
        )
        raise HTTPException(status_code, message) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Roster generation conflicted with another request; retry to pick up the existing entries") from exc



@router.put("/{employee_id}/{work_date}/override", response_model=ShiftRosterOverrideOut)
def override_roster_date(
    employee_id: str,
    work_date: date,
    payload: ShiftRosterOverrideIn,
    db: Session = Depends(get_db),
    user: models.User = write_access,
):
    try:
        allowed = employee_scope_ids(
            db, user, "hr", "employees", "update", as_of_date=work_date,
        )
        if allowed is not None and employee_id not in set(allowed):
            raise HTTPException(
                403,
                "Employee is outside your configured update scope for this effective date",
            )
        row = apply_shift_roster_override(
            db,
            employee_id=employee_id,
            work_date=work_date,
            status=payload.status,
            shift_type_id=payload.shift_type_id,
            reason=payload.reason,
            changed_by=user.username,
        )
        log_audit(
            db,
            user.username,
            "OVERRIDE",
            "hr_shift_roster",
            f"employee={employee_id}; work_date={work_date}; status={row.status}; "
            f"shift={row.shift_type_id}; version={row.version}; reason={payload.reason}",
        )
        db.commit()
        return row
    except HTTPException:
        db.rollback()
        raise
    except ShiftRosterGenerationError as exc:
        db.rollback()
        message = str(exc)
        status_code = (
            404 if "not found" in message.lower()
            else 409 if any(token in message.lower() for token in (
                "blocked", "policy", "overlap", "conflict",
            ))
            else 422
        )
        raise HTTPException(status_code, message) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Roster override conflicted with another update") from exc
