"""P0.1-10 payroll schedule, overtime and provenance integration helpers."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app import models


def build_payroll_daily_inputs(
    db: Session,
    employees: list[models.Employee],
    start: date,
    end: date,
    week_off_days: list[int],
    calendar_overrides: dict[date, str],
    attendance_rows: list[models.EmployeeAttendance],
) -> dict[str, list[dict[str, Any]]]:
    """Batch-load payroll source records and create deterministic daily contexts."""
    employee_ids = [e.id for e in employees]
    departments = list({e.department or "" for e in employees})
    roster_rows = db.query(models.HRShiftRosterEntry).filter(
        models.HRShiftRosterEntry.employee_id.in_(employee_ids),
        models.HRShiftRosterEntry.work_date >= start,
        models.HRShiftRosterEntry.work_date <= end,
    ).all() if employee_ids else []
    assignment_rows = db.query(models.HRShiftAssignment).filter(
        models.HRShiftAssignment.valid_from <= end,
        (models.HRShiftAssignment.valid_to.is_(None) | (models.HRShiftAssignment.valid_to >= start)),
        (
            models.HRShiftAssignment.employee_id.in_(employee_ids)
            | (
                models.HRShiftAssignment.employee_id.is_(None)
                & models.HRShiftAssignment.department.in_(departments)
            )
        ),
    ).all() if employee_ids else []
    org_rows = db.query(models.EmployeeOrgAssignment).filter(
        models.EmployeeOrgAssignment.employee_id.in_(employee_ids),
        models.EmployeeOrgAssignment.valid_from <= end,
        (models.EmployeeOrgAssignment.valid_to.is_(None) | (models.EmployeeOrgAssignment.valid_to >= start)),
    ).all() if employee_ids else []
    summary_rows = db.query(models.HRAttendanceDailySummary).filter(
        models.HRAttendanceDailySummary.employee_id.in_(employee_ids),
        models.HRAttendanceDailySummary.work_date >= start,
        models.HRAttendanceDailySummary.work_date <= end,
    ).all() if employee_ids else []
    overtime_rows = db.query(models.HROvertimeCandidate).filter(
        models.HROvertimeCandidate.employee_id.in_(employee_ids),
        models.HROvertimeCandidate.work_date >= start,
        models.HROvertimeCandidate.work_date <= end,
    ).all() if employee_ids else []
    anomaly_rows = db.query(models.HRAttendanceAnomaly).filter(
        models.HRAttendanceAnomaly.employee_id.in_(employee_ids),
        models.HRAttendanceAnomaly.work_date >= start,
        models.HRAttendanceAnomaly.work_date <= end,
    ).all() if employee_ids else []
    anomalies_by_employee_date: dict[tuple[str, date], list] = {}
    for anomaly in anomaly_rows:
        anomalies_by_employee_date.setdefault((anomaly.employee_id, anomaly.work_date), []).append(anomaly)
    attendance_by_employee_date = {(row.employee_id, row.work_date): row for row in attendance_rows}
    roster_by_employee_date = {(row.employee_id, row.work_date): row for row in roster_rows}
    summary_by_employee_date = {(row.employee_id, row.work_date): row for row in summary_rows}
    ot_by_employee_date: dict[tuple[str, date], list] = {}
    for candidate in overtime_rows:
        if candidate.status == "approved":
            ot_by_employee_date.setdefault((candidate.employee_id, candidate.work_date), []).append(candidate)
    org_by_employee: dict[str, list] = {}
    for row in org_rows:
        org_by_employee.setdefault(row.employee_id, []).append(row)
    assignment_by_employee: dict[str, list] = {}
    assignment_by_department: dict[str, list] = {}
    for row in assignment_rows:
        if row.scope_type == "employee" and row.employee_id:
            assignment_by_employee.setdefault(row.employee_id, []).append(row)
        elif row.scope_type == "department" and row.department is not None:
            assignment_by_department.setdefault(row.department, []).append(row)

    output: dict[str, list[dict[str, Any]]] = {}
    for employee in employees:
        daily = []
        org_assignments = org_by_employee.get(employee.id, [])
        employee_assignments = assignment_by_employee.get(employee.id, [])
        department_assignments = assignment_by_department.get(employee.department or "", [])
        for ordinal in range(start.toordinal(), end.toordinal() + 1):
            work_date = date.fromordinal(ordinal)
            calendar_type = calendar_overrides.get(work_date, "week_off" if work_date.weekday() in week_off_days else "working_day")
            roster = roster_by_employee_date.get((employee.id, work_date))
            active_org = [o for o in org_assignments if o.valid_from <= work_date and (o.valid_to is None or o.valid_to >= work_date)]
            branch_id = active_org[0].branch_id if len(active_org) == 1 else None
            active_employee = [a for a in employee_assignments if a.valid_from <= work_date and (a.valid_to is None or a.valid_to >= work_date) and (a.branch_id is None or a.branch_id == branch_id)]
            active_department = [a for a in department_assignments if a.valid_from <= work_date and (a.valid_to is None or a.valid_to >= work_date) and (a.branch_id is None or a.branch_id == branch_id)]
            active_assignment = active_employee or active_department
            assignment_conflict = len(active_assignment) > 1 and len({a.valid_from for a in active_assignment}) == 1
            expected_shift_day = bool(active_assignment) and not assignment_conflict and work_date.weekday() in (active_assignment[0].weekdays or [])
            exception = "ambiguous_shift_assignment" if assignment_conflict else None
            if expected_shift_day and roster is None:
                exception = "missing_roster"
            if roster is not None:
                scheduled = roster.status == "scheduled"
                day_type = "scheduled_workday" if scheduled else roster.status
            else:
                scheduled = calendar_type == "working_day" if not expected_shift_day else True
                day_type = "scheduled_workday" if scheduled else calendar_type
            summary = summary_by_employee_date.get((employee.id, work_date))
            approved_ot = []
            payable_ot_minutes = 0
            for candidate in ot_by_employee_date.get((employee.id, work_date), []):
                compensation = (candidate.calculation_snapshot or {}).get("compensation_snapshot") or {}
                method = compensation.get("method")
                minutes = int(candidate.rounded_candidate_minutes or 0)
                if method in {"overtime", "both"}:
                    payable_ot_minutes += minutes
                approved_ot.append({
                    "candidate_id": candidate.id, "revision": candidate.revision,
                    "status": candidate.status, "minutes": minutes,
                    "compensation_method": method, "policy_id": candidate.policy_id,
                    "policy_version": candidate.policy_version,
                    "input_fingerprint": candidate.input_fingerprint,
                    "source_event_ids": list(candidate.source_event_ids or []),
                    "summary_revision": candidate.summary_revision,
                    "roster_entry_id": candidate.roster_entry_id,
                })
            attendance = attendance_by_employee_date.get((employee.id, work_date))
            snapshot = {
                "work_date": work_date.isoformat(), "day_type": day_type,
                "scheduled": scheduled, "calendar_type": calendar_type,
                "roster": {
                    "id": roster.id, "status": roster.status, "version": roster.version,
                    "shift_type_id": roster.shift_type_id, "shift_code": roster.shift_code_snapshot,
                    "shift_name": roster.shift_name_snapshot, "timezone": roster.timezone_name,
                    "scheduled_start_utc": roster.scheduled_start_at_utc.isoformat() if roster.scheduled_start_at_utc else None,
                    "scheduled_end_utc": roster.scheduled_end_at_utc.isoformat() if roster.scheduled_end_at_utc else None,
                    "break_rules": roster.break_rules_snapshot, "branch_id": roster.branch_id,
                    "department": roster.department_snapshot,
                } if roster else None,
                "attendance": {
                    "id": attendance.id, "status": attendance.status,
                    "punch_in": attendance.punch_in.isoformat() if attendance.punch_in else None,
                    "punch_out": attendance.punch_out.isoformat() if attendance.punch_out else None,
                    "legacy_overtime_minutes": int(attendance.overtime_minutes or 0),
                    "note": attendance.note,
                } if attendance else None,
                "summary": {
                    "id": summary.id if summary else None,
                    "revision": summary.current_revision if summary else None,
                    "classification": summary.classification if summary else None,
                    "source_event_ids": list(summary.source_event_ids or []) if summary else [],
                    "timezone": summary.timezone_name if summary else None,
                    "exception_codes": list(summary.exception_codes or []) if summary else [],
                    "fingerprint": summary.input_fingerprint if summary else None,
                },
                "approved_overtime": approved_ot,
                "approved_payable_overtime_minutes": payable_ot_minutes,
                "source_anomalies": [{
                    "id": anomaly.id, "type": anomaly.anomaly_type, "status": anomaly.status,
                    "delta_minutes": float(anomaly.observed_delta_minutes),
                    "threshold_minutes": anomaly.threshold_minutes,
                    "policy_version_id": anomaly.policy_version_id,
                    "source_event_ids": list(anomaly.source_event_ids or []),
                    "resolution_reason": anomaly.resolution_reason,
                    "resolution_result": anomaly.resolution_result,
                    "resolved_by": anomaly.resolved_by,
                    "resolved_at": anomaly.resolved_at.isoformat() if anomaly.resolved_at else None,
                } for anomaly in anomalies_by_employee_date.get((employee.id, work_date), [])],
            }
            fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True, default=str).encode()).hexdigest()
            daily.append({
                "work_date": work_date, "snapshot": snapshot, "fingerprint": fingerprint,
                "scheduled": scheduled, "roster": roster, "summary": summary,
                "approved_overtime_minutes": payable_ot_minutes, "exception": exception,
            })
        output[employee.id] = daily
    return output


def scheduled_days_from_daily_inputs(daily_inputs: list[dict[str, Any]]) -> list[date]:
    return [row["work_date"] for row in daily_inputs if row.get("scheduled")]
