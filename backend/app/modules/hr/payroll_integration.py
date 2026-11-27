"""P0.1-10 payroll schedule, overtime and provenance integration helpers."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app import models


def effective_shift_assignment(db: Session, employee: models.Employee, work_date: date):
    """Resolve the most specific effective shift assignment for a work date."""
    rows = db.query(models.HRShiftAssignment).filter(
        models.HRShiftAssignment.valid_from <= work_date,
        (models.HRShiftAssignment.valid_to.is_(None) | (models.HRShiftAssignment.valid_to >= work_date)),
        (
            (models.HRShiftAssignment.employee_id == employee.id)
            | (
                models.HRShiftAssignment.employee_id.is_(None)
                & (models.HRShiftAssignment.department == (employee.department or ""))
            )
        ),
    ).all()
    employee_rows = [row for row in rows if row.scope_type == "employee" and row.employee_id == employee.id]
    department_rows = [row for row in rows if row.scope_type == "department" and row.department == (employee.department or "")]
    candidates = employee_rows or department_rows
    if not candidates:
        return None, "none"
    candidates.sort(key=lambda row: (row.valid_from, row.created_at or row.valid_from), reverse=True)
    if len(candidates) > 1 and candidates[0].valid_from == candidates[1].valid_from:
        return None, "ambiguous"
    assignment = candidates[0]
    weekdays = assignment.weekdays or []
    return (assignment if work_date.weekday() in weekdays else None), "configured"


def payroll_day_context(
    db: Session,
    employee: models.Employee,
    work_date: date,
    calendar_type: str,
    attendance: models.EmployeeAttendance | None,
) -> dict[str, Any]:
    roster = db.query(models.HRShiftRosterEntry).filter_by(
        employee_id=employee.id, work_date=work_date,
    ).first()
    assignment, assignment_state = effective_shift_assignment(db, employee, work_date)
    if assignment_state == "ambiguous":
        return {"work_date": work_date.isoformat(), "day_type": calendar_type, "scheduled": None, "roster": None, "exception": "ambiguous_shift_assignment"}
    if assignment and roster is None:
        return {"work_date": work_date.isoformat(), "day_type": "scheduled_workday", "scheduled": True, "roster": None, "exception": "missing_roster"}
    if roster is not None:
        scheduled = roster.status == "scheduled"
        day_type = "scheduled_workday" if scheduled else roster.status
    else:
        scheduled = calendar_type == "working_day"
        day_type = "scheduled_workday" if scheduled else calendar_type
    summary = db.query(models.HRAttendanceDailySummary).filter_by(
        employee_id=employee.id, work_date=work_date,
    ).first()
    summary_revision = None
    summary_classification = None
    summary_exceptions = []
    if summary:
        summary_revision = summary.current_revision
        summary_classification = summary.classification
        summary_exceptions = list(summary.exception_codes or [])
    approved_candidates = db.query(models.HROvertimeCandidate).filter_by(
        employee_id=employee.id, work_date=work_date, status="approved",
    ).order_by(models.HROvertimeCandidate.revision).all()
    approved_ot = []
    payable_minutes = 0
    for candidate in approved_candidates:
        comp = (candidate.calculation_snapshot or {}).get("compensation_snapshot") or {}
        method = comp.get("method")
        minutes = int(candidate.rounded_candidate_minutes or 0)
        if method in {"overtime", "both"}:
            payable_minutes += minutes
        approved_ot.append({
            "candidate_id": candidate.id,
            "revision": candidate.revision,
            "status": candidate.status,
            "minutes": minutes,
            "compensation_method": method,
            "policy_id": candidate.policy_id,
            "policy_version": candidate.policy_version,
            "input_fingerprint": candidate.input_fingerprint,
            "source_event_ids": list(candidate.source_event_ids or []),
            "summary_revision": candidate.summary_revision,
            "roster_entry_id": candidate.roster_entry_id,
        })
    snapshot = {
        "work_date": work_date.isoformat(),
        "day_type": day_type,
        "scheduled": scheduled,
        "calendar_type": calendar_type,
        "roster": {
            "id": roster.id,
            "status": roster.status,
            "version": roster.version,
            "shift_type_id": roster.shift_type_id,
            "shift_code": roster.shift_code_snapshot,
            "shift_name": roster.shift_name_snapshot,
            "timezone": roster.timezone_name,
            "scheduled_start_utc": roster.scheduled_start_at_utc.isoformat() if roster.scheduled_start_at_utc else None,
            "scheduled_end_utc": roster.scheduled_end_at_utc.isoformat() if roster.scheduled_end_at_utc else None,
            "break_rules": roster.break_rules_snapshot,
            "branch_id": roster.branch_id,
            "department": roster.department_snapshot,
        } if roster else None,
        "attendance": {
            "id": attendance.id,
            "status": attendance.status,
            "punch_in": attendance.punch_in.isoformat() if attendance.punch_in else None,
            "punch_out": attendance.punch_out.isoformat() if attendance.punch_out else None,
            "legacy_overtime_minutes": int(attendance.overtime_minutes or 0),
            "note": attendance.note,
        } if attendance else None,
        "summary": {
            "id": summary.id if summary else None,
            "revision": summary_revision,
            "classification": summary_classification,
            "source_event_ids": list(summary.source_event_ids or []) if summary else [],
            "timezone": summary.timezone_name if summary else None,
            "exception_codes": summary_exceptions,
            "fingerprint": summary.input_fingerprint if summary else None,
        },
        "approved_overtime": approved_ot,
        "approved_payable_overtime_minutes": payable_minutes,
    }
    fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True, default=str).encode()).hexdigest()
    return {"snapshot": snapshot, "fingerprint": fingerprint, "scheduled": scheduled, "roster": roster, "summary": summary, "approved_overtime_minutes": payable_minutes, "exception": None}


def build_employee_payroll_daily_inputs(
    db: Session,
    employee: models.Employee,
    start: date,
    end: date,
    week_off_days: list[int],
    calendar_overrides: dict[date, str],
    attendance_rows: list[models.EmployeeAttendance],
) -> list[dict[str, Any]]:
    attendance_by_date = {row.work_date: row for row in attendance_rows}
    result = []
    for ordinal in range(start.toordinal(), end.toordinal() + 1):
        work_date = date.fromordinal(ordinal)
        calendar_type = calendar_overrides.get(work_date, "week_off" if work_date.weekday() in week_off_days else "working_day")
        context = payroll_day_context(db, employee, work_date, calendar_type, attendance_by_date.get(work_date))
        result.append(context)
    return result
