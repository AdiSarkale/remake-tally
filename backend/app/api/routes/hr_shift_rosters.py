"""Authorized API for idempotent, future-only shift roster generation."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
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
from app.modules.hr.shift_roster_schemas import (\n    ShiftRosterGenerateIn, ShiftRosterGenerateOut,\n    ShiftRosterOverrideIn, ShiftRosterOverrideOut,\n)

router = APIRouter(prefix="/hr/shift-rosters", tags=["hr", "shift-rosters"])
write_access = Depends(require_permission("hr", "shift_rosters", "write", "tenant"))


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
        status_code = 409 if any(token in message.lower() for token in (
            "overlap", "conflict", "blocked", "policy", "historical", "already exists",
        )) else 422
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
        status_code = 409 if any(token in message.lower() for token in (
            "blocked", "policy", "historical", "overlap", "conflict",
        )) else 422
        raise HTTPException(status_code, message) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Roster override conflicted with another update") from exc
