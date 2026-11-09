"""Effective-dated HR shift assignment resolution and local shift-window calculation.

This service deliberately does not generate roster rows or apply holiday policy.
It resolves the approved assignment precedence and returns a stable schedule result
for callers that own authorization, audit, and roster persistence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.modules.hr.models import Employee, EmployeeOrgAssignment, HRBranch
from app.modules.hr.payroll import (
    HRPayrollSettings,
    HRShiftAssignment,
    HRShiftRosterEntry,
    HRShiftType,
)


class ShiftAssignmentConfigurationError(ValueError):
    """Raised when schedule data is missing, ambiguous, or internally inconsistent."""


@dataclass(frozen=True)
class ShiftResolution:
    status: str
    assignment: HRShiftAssignment | None
    shift_type: HRShiftType | None
    roster_entry: HRShiftRosterEntry | None
    branch_id: str | None
    department: str
    timezone_name: str
    scheduled_start_at_utc: datetime | None
    scheduled_end_at_utc: datetime | None


def _effective_org_assignment(
    db: Session, employee_id: str, work_date: date,
) -> EmployeeOrgAssignment | None:
    rows = db.query(EmployeeOrgAssignment).filter(
        EmployeeOrgAssignment.employee_id == employee_id,
        EmployeeOrgAssignment.valid_from <= work_date,
        (EmployeeOrgAssignment.valid_to.is_(None) | (EmployeeOrgAssignment.valid_to >= work_date)),
    ).all()
    if len(rows) > 1:
        raise ShiftAssignmentConfigurationError(
            f"Employee {employee_id} has overlapping organization assignments on {work_date}"
        )
    return rows[0] if rows else None


def _timezone_for_branch(db: Session, branch_id: str | None) -> ZoneInfo:
    if branch_id:
        branch = db.get(HRBranch, branch_id)
        if branch is None or not branch.active:
            raise ShiftAssignmentConfigurationError("The assigned branch does not exist or is inactive")
        timezone_name = (branch.timezone or "").strip()
        if not timezone_name:
            settings = db.get(HRPayrollSettings, 1)
            timezone_name = settings.timezone if settings and settings.timezone else "Asia/Kolkata"
    else:
        settings = db.get(HRPayrollSettings, 1)
        timezone_name = settings.timezone if settings and settings.timezone else "Asia/Kolkata"
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ShiftAssignmentConfigurationError(
            f"Invalid IANA timezone configured for this employee's work date: {timezone_name}"
        ) from exc


def _localize_unambiguous(value: datetime, zone: ZoneInfo) -> datetime:
    """Attach an IANA zone only when the local wall-clock time maps to one instant."""
    valid: list[datetime] = []
    for fold in (0, 1):
        candidate = value.replace(tzinfo=zone, fold=fold)
        round_trip = candidate.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
        if round_trip == value:
            valid.append(candidate)
    offsets = {candidate.utcoffset() for candidate in valid}
    if not valid:
        raise ShiftAssignmentConfigurationError(
            f"Local shift boundary {value.isoformat(sep=' ')} does not exist in timezone {zone.key}"
        )
    if len(offsets) > 1:
        raise ShiftAssignmentConfigurationError(
            f"Local shift boundary {value.isoformat(sep=' ')} is ambiguous in timezone {zone.key}"
        )
    return valid[0]


def resolve_shift_window(
    work_date: date, shift_type: HRShiftType, timezone_name: str,
) -> tuple[datetime, datetime]:
    """Resolve shift boundaries to UTC; overnight shifts remain on their start work date."""
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ShiftAssignmentConfigurationError(f"Invalid IANA timezone: {timezone_name}") from exc
    start_local = datetime.combine(work_date, shift_type.start_time)
    end_local_date = work_date + timedelta(days=shift_type.end_day_offset)
    end_local = datetime.combine(end_local_date, shift_type.end_time)
    start_aware = _localize_unambiguous(start_local, zone)
    end_aware = _localize_unambiguous(end_local, zone)
    start_utc = start_aware.astimezone(timezone.utc)
    end_utc = end_aware.astimezone(timezone.utc)
    if end_utc <= start_utc:
        raise ShiftAssignmentConfigurationError(
            f"Shift {shift_type.code} ends before or at its start after timezone resolution"
        )
    return start_utc, end_utc


def _date_ranges_overlap(
    left_from: date, left_to: date | None, right_from: date, right_to: date | None,
) -> bool:
    return (left_to is None or right_from <= left_to) and (right_to is None or left_from <= right_to)


def create_shift_assignment(
    db: Session,
    *,
    scope_type: str,
    shift_type_id: str,
    weekdays: list[int],
    valid_from: date,
    valid_to: date | None,
    created_by: str,
    employee_id: str | None = None,
    branch_id: str | None = None,
    department: str | None = None,
) -> HRShiftAssignment:
    """Create a recurring assignment and safely supersede one prior matching period."""
    if scope_type not in {"employee", "department"}:
        raise ShiftAssignmentConfigurationError("Assignment scope must be employee or department")
    if valid_to is not None and valid_to < valid_from:
        raise ShiftAssignmentConfigurationError("Assignment end date cannot precede start date")
    if (
        not weekdays
        or any(not isinstance(day, int) or isinstance(day, bool) or day < 0 or day > 6 for day in weekdays)
        or len(set(weekdays)) != len(weekdays)
    ):
        raise ShiftAssignmentConfigurationError("Weekdays must be a non-empty unique set from 0 (Monday) to 6 (Sunday)")
    if scope_type == "employee":
        if not employee_id or department is not None:
            raise ShiftAssignmentConfigurationError("Employee assignments require employee_id and cannot set department")
        employee = db.get(Employee, employee_id)
        if employee is None or not employee.active:
            raise ShiftAssignmentConfigurationError("An active employee is required for this assignment")
        if employee.joining_date and valid_from < employee.joining_date:
            raise ShiftAssignmentConfigurationError("Employee shift assignment cannot start before the joining date")
        if employee.end_date:
            if valid_from > employee.end_date:
                raise ShiftAssignmentConfigurationError("Employee shift assignment cannot start after the employment end date")
            if valid_to is None or valid_to > employee.end_date:
                valid_to = employee.end_date
        normalized_department = None
    else:
        normalized_department = (department or "").strip()
        if not normalized_department or employee_id is not None:
            raise ShiftAssignmentConfigurationError("Department assignments require department and cannot set employee_id")
        employee = None
    if branch_id:
        branch = db.get(HRBranch, branch_id)
        if branch is None or not branch.active:
            raise ShiftAssignmentConfigurationError("An active branch is required for this assignment")
    shift = db.get(HRShiftType, shift_type_id)
    if shift is None or not shift.active:
        raise ShiftAssignmentConfigurationError("An active shift definition is required for new assignments")

    candidates = db.query(HRShiftAssignment).filter(
        HRShiftAssignment.scope_type == scope_type,
    ).all()
    matching: list[HRShiftAssignment] = []
    for existing in candidates:
        if scope_type == "employee":
            same_target = existing.employee_id == employee_id
        else:
            same_department = (existing.department or "").strip().casefold() == normalized_department.casefold()
            branches_conflict = (
                existing.branch_id is None or branch_id is None or existing.branch_id == branch_id
            )
            same_target = same_department and branches_conflict
        if same_target and _date_ranges_overlap(
            existing.valid_from, existing.valid_to, valid_from, valid_to,
        ):
            matching.append(existing)

    supersedes_id: str | None = None
    if matching:
        if len(matching) != 1:
            raise ShiftAssignmentConfigurationError("Multiple overlapping assignments already match this target and period")
        existing = matching[0]
        same_exact_target = (
            existing.employee_id == employee_id if scope_type == "employee"
            else (
                (existing.department or "").strip().casefold() == normalized_department.casefold()
                and existing.branch_id == branch_id
            )
        )
        can_supersede = (
            same_exact_target
            and existing.valid_from < valid_from
            and (existing.valid_to is None or existing.valid_to >= valid_from)
            and (valid_to is None or (existing.valid_to is not None and existing.valid_to <= valid_to))
        )
        if not can_supersede:
            raise ShiftAssignmentConfigurationError(
                "This assignment overlaps an existing assignment; correct the effective dates before saving"
            )
        existing.valid_to = valid_from - timedelta(days=1)
        supersedes_id = existing.id

    row = HRShiftAssignment(
        scope_type=scope_type,
        employee_id=employee_id if scope_type == "employee" else None,
        branch_id=branch_id,
        department=normalized_department,
        shift_type_id=shift_type_id,
        weekdays=sorted(weekdays),
        valid_from=valid_from,
        valid_to=valid_to,
        supersedes_assignment_id=supersedes_id,
        created_by=created_by,
    )
    db.add(row)
    db.flush()
    return row


def resolve_shift_for_work_date(
    db: Session, employee_id: str, work_date: date,
) -> ShiftResolution | None:
    """Resolve roster override > employee assignment > department default > legacy fallback."""
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise ShiftAssignmentConfigurationError("Employee not found")
    if (
        (employee.joining_date is not None and work_date < employee.joining_date)
        or (employee.end_date is not None and work_date > employee.end_date)
    ):
        return None

    roster = db.query(HRShiftRosterEntry).filter_by(
        employee_id=employee_id, work_date=work_date,
    ).first()
    if roster is not None:
        shift = db.get(HRShiftType, roster.shift_type_id) if roster.shift_type_id else None
        assignment = db.get(HRShiftAssignment, roster.source_assignment_id) if roster.source_assignment_id else None
        return ShiftResolution(
            status=roster.status,
            assignment=assignment,
            shift_type=shift,
            roster_entry=roster,
            branch_id=roster.branch_id,
            department=roster.department_snapshot or "",
            timezone_name=roster.timezone_name,
            scheduled_start_at_utc=roster.scheduled_start_at_utc,
            scheduled_end_at_utc=roster.scheduled_end_at_utc,
        )

    org = _effective_org_assignment(db, employee_id, work_date)
    employee_assignments = db.query(HRShiftAssignment).filter(
        HRShiftAssignment.scope_type == "employee",
        HRShiftAssignment.employee_id == employee_id,
        HRShiftAssignment.valid_from <= work_date,
        (HRShiftAssignment.valid_to.is_(None) | (HRShiftAssignment.valid_to >= work_date)),
    ).all()
    if len(employee_assignments) > 1:
        raise ShiftAssignmentConfigurationError(
            f"Employee {employee_id} has overlapping shift assignments on {work_date}"
        )

    assignment = employee_assignments[0] if employee_assignments else None
    department_name = org.department if org else ""
    branch_id = (assignment.branch_id if assignment and assignment.branch_id else (org.branch_id if org else None))

    if assignment is None and org is not None and org.department.strip():
        defaults = db.query(HRShiftAssignment).filter(
            HRShiftAssignment.scope_type == "department",
            HRShiftAssignment.valid_from <= work_date,
            (HRShiftAssignment.valid_to.is_(None) | (HRShiftAssignment.valid_to >= work_date)),
        ).all()
        matches = [
            row for row in defaults
            if (row.department or "").strip().casefold() == org.department.strip().casefold()
            and (row.branch_id is None or row.branch_id == org.branch_id)
        ]
        if len(matches) > 1:
            raise ShiftAssignmentConfigurationError(
                f"Conflicting department shift defaults for {org.department!r} on {work_date}"
            )
        assignment = matches[0] if matches else None
        if assignment is not None and assignment.branch_id is not None:
            branch_id = assignment.branch_id

    if assignment is None:
        return None

    if assignment.scope_type == "employee" and assignment.branch_id and org and org.branch_id and assignment.branch_id != org.branch_id:
        raise ShiftAssignmentConfigurationError(
            f"Employee shift assignment branch does not match organization branch on {work_date}"
        )

    shift = db.get(HRShiftType, assignment.shift_type_id)
    if shift is None:
        raise ShiftAssignmentConfigurationError("Assigned shift definition is missing")
    zone = _timezone_for_branch(db, branch_id)
    weekdays = assignment.weekdays or []
    if not isinstance(weekdays, list) or any(
        not isinstance(day, int) or isinstance(day, bool) or day < 0 or day > 6 for day in weekdays
    ) or len(set(weekdays)) != len(weekdays):
        raise ShiftAssignmentConfigurationError("Stored assignment weekdays are invalid")
    if work_date.weekday() not in weekdays:
        return ShiftResolution(
            status="weekly_off",
            assignment=assignment,
            shift_type=None,
            roster_entry=None,
            branch_id=branch_id,
            department=department_name,
            timezone_name=zone.key,
            scheduled_start_at_utc=None,
            scheduled_end_at_utc=None,
        )
    start_utc, end_utc = resolve_shift_window(work_date, shift, zone.key)
    return ShiftResolution(
        status="scheduled",
        assignment=assignment,
        shift_type=shift,
        roster_entry=None,
        branch_id=branch_id,
        department=department_name,
        timezone_name=zone.key,
        scheduled_start_at_utc=start_utc,
        scheduled_end_at_utc=end_utc,
    )

@dataclass(frozen=True)
class EmployeeWorkContext:
    """Effective branch and IANA timezone for one employee's local work date."""

    branch_id: str | None
    department: str
    timezone_name: str
    organization_assignment_id: str | None


def resolve_employee_work_context(
    db: Session,
    employee_id: str,
    work_date: date,
    *,
    timezone_override: str | None = None,
) -> EmployeeWorkContext:
    """Resolve effective branch membership and one local timezone for a work date.

    A caller may supply an authorized batch timezone override. The branch
    membership remains independently resolved from the effective organization
    assignment and is never inferred from the timezone string.
    """
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise ShiftAssignmentConfigurationError("Employee not found")
    if (
        (employee.joining_date is not None and work_date < employee.joining_date)
        or (employee.end_date is not None and work_date > employee.end_date)
    ):
        raise ShiftAssignmentConfigurationError(
            f"Employee {employee_id} is outside the employment period on {work_date}"
        )

    org = _effective_org_assignment(db, employee_id, work_date)
    branch_id = org.branch_id if org else None
    branch_timezone = ""
    if branch_id:
        branch = db.get(HRBranch, branch_id)
        if branch is None or not branch.active:
            raise ShiftAssignmentConfigurationError(
                f"Employee {employee_id} has no active effective branch on {work_date}"
            )
        branch_timezone = (branch.timezone or "").strip()

    settings = db.get(HRPayrollSettings, 1)
    tenant_timezone = (settings.timezone if settings else None) or "Asia/Kolkata"
    timezone_name = timezone_override or branch_timezone or tenant_timezone

    roster = db.query(HRShiftRosterEntry).filter_by(
        employee_id=employee_id, work_date=work_date,
    ).first()
    if roster is not None and timezone_override is None:
        if roster.branch_id != branch_id:
            raise ShiftAssignmentConfigurationError(
                f"Roster branch does not match the employee's effective branch on {work_date}"
            )
        timezone_name = roster.timezone_name

    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ShiftAssignmentConfigurationError(
            f"Invalid IANA timezone for employee {employee_id} on {work_date}: {timezone_name}"
        ) from exc

    return EmployeeWorkContext(
        branch_id=branch_id,
        department=(org.department if org else ""),
        timezone_name=zone.key,
        organization_assignment_id=(org.id if org else None),
    )


def localize_attendance_datetime(value: datetime, timezone_name: str) -> datetime:
    """Convert a naive local wall time to an aware UTC instant without DST guessing."""
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc)
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ShiftAssignmentConfigurationError(
            f"Invalid IANA timezone: {timezone_name}"
        ) from exc
    return _localize_unambiguous(value, zone).astimezone(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def resolve_attendance_work_date(
    db: Session, employee_id: str, punch_in_utc: datetime | None,
) -> tuple[EmployeeWorkContext, date]:
    """Resolve event attribution by matching local punch-in to a persisted roster window."""
    if punch_in_utc is None:
        raise ShiftAssignmentConfigurationError("Punch In is required to resolve an attendance work date")
    instant = (
        punch_in_utc.replace(tzinfo=timezone.utc)
        if punch_in_utc.tzinfo is None else punch_in_utc.astimezone(timezone.utc)
    )

    # Roster boundaries are stored as UTC instants. Find the unique roster
    # whose window contains the event, including shifts crossing midnight.
    # Use a bounded local-date window rather than comparing timezone-aware
    # columns in SQLite, where offsets may be discarded by the test dialect.
    utc_date = instant.date()
    roster_rows = db.query(HRShiftRosterEntry).filter(
        HRShiftRosterEntry.employee_id == employee_id,
        HRShiftRosterEntry.work_date >= utc_date - timedelta(days=1),
        HRShiftRosterEntry.work_date <= utc_date + timedelta(days=1),
        HRShiftRosterEntry.status == "scheduled",
    ).all()
    roster_rows = [
        row for row in roster_rows
        if row.scheduled_start_at_utc is not None
        and row.scheduled_end_at_utc is not None
        and _as_utc(row.scheduled_start_at_utc) <= instant <= _as_utc(row.scheduled_end_at_utc)
    ]
    if len(roster_rows) > 1:
        raise ShiftAssignmentConfigurationError(
            f"More than one scheduled shift contains the punch-in instant for employee {employee_id}"
        )
    if roster_rows:
        roster = roster_rows[0]
        context = resolve_employee_work_context(db, employee_id, roster.work_date)
        if context.branch_id != roster.branch_id:
            raise ShiftAssignmentConfigurationError(
                f"Roster branch does not match effective employee branch on {roster.work_date}"
            )
        try:
            zone = ZoneInfo(roster.timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ShiftAssignmentConfigurationError(
                f"Roster has an invalid IANA timezone: {roster.timezone_name}"
            ) from exc
        return EmployeeWorkContext(
            branch_id=roster.branch_id,
            department=context.department,
            timezone_name=zone.key,
            organization_assignment_id=context.organization_assignment_id,
        ), roster.work_date

    # No roster applies: resolve against candidate local dates around the UTC
    # date. This avoids using the wrong effective assignment when a branch
    # transfer or employment start/end occurs near local midnight.
    matches: list[tuple[EmployeeWorkContext, date]] = []
    resolution_errors: list[str] = []
    for candidate_date in (
        utc_date - timedelta(days=1),
        utc_date,
        utc_date + timedelta(days=1),
    ):
        try:
            context = resolve_employee_work_context(db, employee_id, candidate_date)
        except ShiftAssignmentConfigurationError as exc:
            resolution_errors.append(str(exc))
            continue
        local_date = instant.astimezone(ZoneInfo(context.timezone_name)).date()
        if local_date == candidate_date:
            matches.append((context, candidate_date))

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ShiftAssignmentConfigurationError(
            f"Punch-in local work date is ambiguous across effective timezone assignments for employee {employee_id}"
        )
    detail = resolution_errors[0] if resolution_errors else "No effective timezone maps this punch-in to a valid local work date"
    raise ShiftAssignmentConfigurationError(detail)
