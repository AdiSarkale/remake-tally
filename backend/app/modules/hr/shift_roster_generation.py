"""Deterministic, idempotent roster generation for effective-dated HR shifts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.modules.hr.models import Employee, EmployeeOrgAssignment, HRBranch
from app.modules.hr.payroll import (
    HRCalendarDay,
    HRPayrollRun,
    HRPayrollSettings,
    HRShiftAssignment,
    HRShiftBreakRule,
    HRShiftRosterEntry,
    HRWorkforcePolicyVersion,
)
from app.modules.hr.shift_assignment import (
    ShiftAssignmentConfigurationError,
    resolve_shift_for_work_date,
)


MAX_ROSTER_DAYS = 31
MAX_ROSTER_EMPLOYEES = 500
HOLIDAY_PRECEDENCE_KEY = "holiday_roster_precedence"
HOLIDAY_PRECEDENCE_VALUES = {"holiday_overrides_roster", "roster_overrides_holiday"}


class ShiftRosterGenerationError(ValueError):
    """Raised when a roster cannot be generated without guessing or mutating history."""


@dataclass(frozen=True)
class RosterGenerationResult:
    start_date: date
    end_date: date
    employee_count: int
    created_count: int
    scheduled_count: int
    weekly_off_count: int
    holiday_count: int
    skipped_existing_count: int
    skipped_outside_employment_count: int
    unassigned_working_day_count: int


def _effective_org_assignment(
    db: Session, employee_id: str, work_date: date,
) -> EmployeeOrgAssignment | None:
    rows = db.query(EmployeeOrgAssignment).filter(
        EmployeeOrgAssignment.employee_id == employee_id,
        EmployeeOrgAssignment.valid_from <= work_date,
        (EmployeeOrgAssignment.valid_to.is_(None) | (EmployeeOrgAssignment.valid_to >= work_date)),
    ).all()
    if len(rows) > 1:
        raise ShiftRosterGenerationError(
            f"Employee {employee_id} has overlapping organization assignments on {work_date}"
        )
    return rows[0] if rows else None


def _tenant_timezone_name(db: Session) -> str:
    settings = db.get(HRPayrollSettings, 1)
    name = settings.timezone if settings and settings.timezone else "Asia/Kolkata"
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ShiftRosterGenerationError(f"Invalid tenant IANA timezone: {name}") from exc
    return name


def _timezone_name(db: Session, branch_id: str | None, tenant_timezone: str) -> str:
    if not branch_id:
        return tenant_timezone
    branch = db.get(HRBranch, branch_id)
    if branch is None:
        raise ShiftRosterGenerationError("The employee's effective branch no longer exists")
    try:
        ZoneInfo(branch.timezone)
    except ZoneInfoNotFoundError as exc:
        raise ShiftRosterGenerationError(
            f"Invalid IANA timezone configured for branch {branch.code}: {branch.timezone}"
        ) from exc
    return branch.timezone


def _week_off_days(settings: HRPayrollSettings | None) -> set[int]:
    raw = settings.week_off_days if settings else "5,6"
    try:
        values = [int(token) for token in raw.split(",") if token != ""]
    except (AttributeError, ValueError):
        return {5, 6}
    return {day for day in values if 0 <= day <= 6}


def _policy_for_date(
    policies: list[HRWorkforcePolicyVersion], work_date: date,
) -> HRWorkforcePolicyVersion | None:
    matches = [
        row for row in policies
        if row.effective_from <= work_date
        and (row.effective_to is None or row.effective_to >= work_date)
    ]
    if len(matches) > 1:
        raise ShiftRosterGenerationError(
            f"Overlapping workforce policy versions apply on {work_date}"
        )
    return matches[0] if matches else None


def _break_snapshot(db: Session, shift_type_id: str) -> list[dict]:
    rules = db.query(HRShiftBreakRule).filter(
        HRShiftBreakRule.shift_type_id == shift_type_id,
        HRShiftBreakRule.active.is_(True),
    ).order_by(HRShiftBreakRule.sequence, HRShiftBreakRule.code).all()
    return [
        {
            "code": row.code,
            "name": row.name,
            "sequence": row.sequence,
            "is_paid": row.is_paid,
            "planned_duration_minutes": row.planned_duration_minutes,
            "scheduled_start_time": row.scheduled_start_time.isoformat() if row.scheduled_start_time else None,
            "scheduled_end_time": row.scheduled_end_time.isoformat() if row.scheduled_end_time else None,
        }
        for row in rules
    ]


def generate_shift_roster(
    db: Session,
    *,
    start_date: date,
    end_date: date,
    created_by: str,
    employee_ids: list[str] | None = None,
    branch_id: str | None = None,
    department: str | None = None,
    all_employees: bool = False,
    authorize_employee_date=None,
) -> RosterGenerationResult:
    """Generate future roster rows once; existing rows are immutable to this operation.

    The caller owns request validation, employee-scope authorization, audit logging
    and transaction commit. authorize_employee_date(employee_id, work_date) is
    invoked for every employee/date selected by the requested scope.
    """
    if end_date < start_date:
        raise ShiftRosterGenerationError("Roster end date cannot precede start date")
    day_count = (end_date - start_date).days + 1
    if day_count > MAX_ROSTER_DAYS:
        raise ShiftRosterGenerationError(f"A roster generation request cannot exceed {MAX_ROSTER_DAYS} calendar days")
    selectors = sum((bool(employee_ids), bool(branch_id or department), bool(all_employees)))
    if selectors != 1:
        raise ShiftRosterGenerationError(
            "Select exactly one scope: employee_ids, branch/department filters, or all_employees"
        )
    if employee_ids and len(set(employee_ids)) != len(employee_ids):
        raise ShiftRosterGenerationError("Employee IDs must not contain duplicates")
    if employee_ids and len(employee_ids) > MAX_ROSTER_EMPLOYEES:
        raise ShiftRosterGenerationError(f"A request cannot include more than {MAX_ROSTER_EMPLOYEES} employees")
    if department is not None:
        department = department.strip()
        if not department:
            raise ShiftRosterGenerationError("Department filter cannot be blank")

    # Roster generation is a future-planning operation. Historical schedule
    # reconstruction/backfill is intentionally not supported by this endpoint.
    tenant_timezone = _tenant_timezone_name(db)
    settings = db.get(HRPayrollSettings, 1)
    week_off_days = _week_off_days(settings)

    # Never add roster data after a payroll period has been prepared/approved/
    # finalized/locked/reversed. A separate authorized payroll revision workflow
    # is not part of this package.
    months = {(day.year, day.month) for day in (
        start_date + timedelta(days=offset) for offset in range(day_count)
    )}
    for year, month in months:
        frozen = db.query(HRPayrollRun).filter(
            HRPayrollRun.year == year,
            HRPayrollRun.month == month,
            HRPayrollRun.status != "draft",
        ).first()
        if frozen is not None:
            raise ShiftRosterGenerationError(
                f"Roster generation is blocked for {year}-{month:02d}: payroll run status is {frozen.status!r}"
            )

    if employee_ids:
        employees = db.query(Employee).filter(Employee.id.in_(employee_ids)).order_by(Employee.emp_code).all()
        found = {row.id for row in employees}
        missing = sorted(set(employee_ids) - found)
        if missing:
            raise ShiftRosterGenerationError(f"Employee IDs not found in this tenant: {', '.join(missing)}")
        inactive = [row.emp_code for row in employees if not row.active]
        if inactive:
            raise ShiftRosterGenerationError(f"Inactive employees cannot receive future rosters: {', '.join(inactive)}")
    else:
        employees = db.query(Employee).filter(Employee.active.is_(True)).order_by(Employee.emp_code).all()

    if len(employees) > MAX_ROSTER_EMPLOYEES:
        raise ShiftRosterGenerationError(
            f"Selected scope contains more than {MAX_ROSTER_EMPLOYEES} employees; narrow the request"
        )
    if branch_id:
        branch = db.get(HRBranch, branch_id)
        if branch is None or not branch.active:
            raise ShiftRosterGenerationError("An active branch is required for roster generation")

    # Preload tenant calendar and policy versions once for the requested range.
    calendar_rows = db.query(HRCalendarDay).filter(
        HRCalendarDay.work_date >= start_date,
        HRCalendarDay.work_date <= end_date,
    ).all()
    calendar_by_date = {row.work_date: row for row in calendar_rows}
    for row in calendar_rows:
        if row.day_type not in {"holiday", "week_off", "working_day"}:
            raise ShiftRosterGenerationError(
                f"Unsupported tenant calendar day type {row.day_type!r} on {row.work_date}"
            )
    policies = db.query(HRWorkforcePolicyVersion).filter(
        HRWorkforcePolicyVersion.effective_from <= end_date,
        (HRWorkforcePolicyVersion.effective_to.is_(None) | (HRWorkforcePolicyVersion.effective_to >= start_date)),
    ).all()

    existing_rows = db.query(HRShiftRosterEntry).filter(
        HRShiftRosterEntry.work_date >= start_date,
        HRShiftRosterEntry.work_date <= end_date,
    ).all()
    existing_keys = {(row.employee_id, row.work_date) for row in existing_rows}

    pending: list[HRShiftRosterEntry] = []
    scheduled_count = weekly_off_count = holiday_count = 0
    skipped_existing_count = skipped_outside_employment_count = unassigned_working_day_count = 0
    selected_employee_ids: set[str] = set()

    for employee in employees:
        for offset in range(day_count):
            work_date = start_date + timedelta(days=offset)
            if employee.joining_date and work_date < employee.joining_date:
                skipped_outside_employment_count += 1
                continue
            if employee.end_date and work_date > employee.end_date:
                skipped_outside_employment_count += 1
                continue

            org = _effective_org_assignment(db, employee.id, work_date)
            if branch_id and (org is None or org.branch_id != branch_id):
                continue
            if department and (
                org is None or (org.department or "").strip().casefold() != department.casefold()
            ):
                continue

            selected_employee_ids.add(employee.id)
            if authorize_employee_date is not None:
                authorize_employee_date(employee.id, work_date)

            key = (employee.id, work_date)
            if key in existing_keys:
                skipped_existing_count += 1
                continue

            try:
                resolution = resolve_shift_for_work_date(db, employee.id, work_date)
            except ShiftAssignmentConfigurationError as exc:
                raise ShiftRosterGenerationError(str(exc)) from exc

            branch_for_day = (
                resolution.branch_id if resolution and resolution.branch_id
                else (org.branch_id if org else None)
            )
            timezone_name = (
                resolution.timezone_name if resolution
                else _timezone_name(db, branch_for_day, tenant_timezone)
            )
            try:
                local_today = datetime.now(ZoneInfo(timezone_name)).date()
            except ZoneInfoNotFoundError as exc:
                raise ShiftRosterGenerationError(f"Invalid IANA timezone: {timezone_name}") from exc
            if work_date < local_today:
                raise ShiftRosterGenerationError(
                    f"Historical roster generation is not allowed: {employee.emp_code} on {work_date}"
                )

            calendar_row = calendar_by_date.get(work_date)
            calendar_type = calendar_row.day_type if calendar_row else None
            policy = _policy_for_date(policies, work_date)
            status: str | None = None
            assignment = resolution.assignment if resolution else None
            shift_type = resolution.shift_type if resolution else None
            start_utc = resolution.scheduled_start_at_utc if resolution else None
            end_utc = resolution.scheduled_end_at_utc if resolution else None

            if resolution is None:
                # Preserve the existing tenant-wide calendar/week-off behavior
                # when no shift assignment applies. Do not invent a shift.
                legacy_day_type = calendar_type or (
                    "week_off" if work_date.weekday() in week_off_days else "working_day"
                )
                if legacy_day_type == "holiday":
                    status = "holiday"
                elif legacy_day_type == "week_off":
                    status = "weekly_off"
                else:
                    unassigned_working_day_count += 1
                    continue
            elif calendar_type == "holiday":
                if policy is None:
                    raise ShiftRosterGenerationError(
                        f"Holiday/roster precedence policy is required before generating an assigned roster on holiday {work_date}"
                    )
                precedence = (policy.configuration or {}).get(HOLIDAY_PRECEDENCE_KEY)
                if precedence not in HOLIDAY_PRECEDENCE_VALUES:
                    raise ShiftRosterGenerationError(
                        f"Workforce policy {policy.version_code} must set {HOLIDAY_PRECEDENCE_KEY} to "
                        "'holiday_overrides_roster' or 'roster_overrides_holiday' before generating {work_date}"
                    )
                if precedence == "holiday_overrides_roster":
                    status = "holiday"
                    shift_type = None
                    start_utc = end_utc = None
                else:
                    status = resolution.status
            else:
                status = resolution.status

            if status not in {"scheduled", "weekly_off", "holiday"}:
                raise ShiftRosterGenerationError(
                    f"Unsupported roster resolution status {status!r} for {employee.emp_code} on {work_date}"
                )
            if status == "scheduled":
                if shift_type is None or not shift_type.active:
                    raise ShiftRosterGenerationError(
                        f"An active shift definition is required for {employee.emp_code} on {work_date}"
                    )
                if start_utc is None or end_utc is None or end_utc <= start_utc:
                    raise ShiftRosterGenerationError(
                        f"Invalid scheduled shift boundaries for {employee.emp_code} on {work_date}"
                    )
                break_snapshot = _break_snapshot(db, shift_type.id)
                scheduled_count += 1
            else:
                break_snapshot = []
                if status == "weekly_off":
                    weekly_off_count += 1
                else:
                    holiday_count += 1

            pending.append(HRShiftRosterEntry(
                employee_id=employee.id,
                work_date=work_date,
                status=status,
                shift_type_id=shift_type.id if status == "scheduled" and shift_type else None,
                source_assignment_id=assignment.id if assignment else None,
                is_override=False,
                override_reason="",
                branch_id=branch_for_day,
                department_snapshot=(resolution.department if resolution else (org.department if org else "")) or "",
                timezone_name=timezone_name,
                scheduled_start_at_utc=start_utc if status == "scheduled" else None,
                scheduled_end_at_utc=end_utc if status == "scheduled" else None,
                shift_code_snapshot=shift_type.code if status == "scheduled" and shift_type else "",
                shift_name_snapshot=shift_type.name if status == "scheduled" and shift_type else "",
                break_rules_snapshot=break_snapshot,
                policy_version_id=policy.id if policy else None,
                created_by=created_by,
            ))

    db.add_all(pending)
    db.flush()
    return RosterGenerationResult(
        start_date=start_date,
        end_date=end_date,
        employee_count=len(selected_employee_ids),
        created_count=len(pending),
        scheduled_count=scheduled_count,
        weekly_off_count=weekly_off_count,
        holiday_count=holiday_count,
        skipped_existing_count=skipped_existing_count,
        skipped_outside_employment_count=skipped_outside_employment_count,
        unassigned_working_day_count=unassigned_working_day_count,
    )
