"""Tenant-scoped HR payroll, calendar, salary and monthly attendance APIs."""
from __future__ import annotations

import calendar
import io
from datetime import date, datetime, time as time_type, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils.datetime import from_excel
from openpyxl.utils.exceptions import InvalidFileException
from zipfile import BadZipFile
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import current_user, employee_scope_ids, require_area, require_permission
from app.db.session import get_db
from app.modules.core.audit import log_audit
from app.modules.finance.payroll_posting import post_payroll_journal, reverse_payroll_journal
from app.modules.hr.shift_assignment import (
    ShiftAssignmentConfigurationError,
    localize_attendance_datetime,
    resolve_employee_work_context,
    resolve_shift_for_work_date,
)

router = APIRouter(prefix="/hr", tags=["hr", "payroll"])
hr_access = Depends(require_permission("hr", "payroll", "read", "tenant"))
_CENT = Decimal("0.01")




def _ensure_attendance_employee_scope(
    db: Session, user: models.User, employee_id: str, work_date: date, action: str,
) -> None:
    scoped_ids = employee_scope_ids(
        db, user, "hr", "employees", action, as_of_date=work_date,
    )
    if scoped_ids is not None and employee_id not in scoped_ids:
        raise HTTPException(status_code=403, detail="Employee is outside your configured attendance access scope")


def _ensure_period_not_prepared(db: Session, year: int, month: int) -> None:
    frozen = db.query(models.HRPayrollRun).filter(
        models.HRPayrollRun.year == year,
        models.HRPayrollRun.month == month,
        models.HRPayrollRun.status.in_(["prepared", "approved", "finalized", "locked"]),
    ).first()
    if frozen is not None:
        raise HTTPException(
            status_code=409,
            detail="This payroll period has a prepared or finalized snapshot. Reverse it through the controlled payroll workflow before changing its attendance or calendar inputs.",
        )


def _ensure_no_pending_payroll_snapshot(db: Session) -> None:
    frozen = db.query(models.HRPayrollRun).filter(
        models.HRPayrollRun.status.in_(["prepared", "approved"])
    ).first()
    if frozen is not None:
        raise HTTPException(
            status_code=409,
            detail="A prepared or approved payroll snapshot exists. Finalize or reverse it before changing salary profiles or payroll settings.",
        )


def _dec(value: Any) -> Decimal:
    return Decimal(str(value if value is not None else 0))


def _money(value: Decimal | float | int) -> Decimal:
    return _dec(value).quantize(_CENT, rounding=ROUND_HALF_UP)


def _ensure_settings(db: Session) -> models.HRPayrollSettings:
    row = db.get(models.HRPayrollSettings, 1)
    if row is None:
        row = models.HRPayrollSettings(id=1)
        db.add(row)
        db.flush()
        db.commit()
        db.refresh(row)
    return row


def _week_offs(settings: models.HRPayrollSettings) -> list[int]:
    try:
        values = [int(token) for token in settings.week_off_days.split(",") if token != ""]
        return sorted(set(day for day in values if 0 <= day <= 6))
    except (AttributeError, ValueError):
        return [5, 6]


def _tenant_timezone(db: Session) -> ZoneInfo:
    settings = _ensure_settings(db)
    try:
        return ZoneInfo(settings.timezone or "Asia/Kolkata")
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=500, detail="Tenant timezone is invalid; update HR payroll settings") from exc


def _attendance_context(db: Session, employee_id: str, work_date: date):
    try:
        return resolve_employee_work_context(db, employee_id, work_date)
    except ShiftAssignmentConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _attendance_timezone(db: Session, employee_id: str, work_date: date) -> ZoneInfo:
    return ZoneInfo(_attendance_context(db, employee_id, work_date).timezone_name)


def _to_utc(value: datetime | None, tenant_tz: ZoneInfo) -> datetime | None:
    if value is None:
        return None
    local_value = value.replace(tzinfo=tenant_tz) if value.tzinfo is None else value
    return local_value.astimezone(timezone.utc)


def _to_local(value: datetime | None, tenant_tz: ZoneInfo) -> datetime | None:
    if value is None:
        return None
    aware_value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return aware_value.astimezone(tenant_tz)


def _settings_output(row: models.HRPayrollSettings) -> dict[str, Any]:
    return {
        "id": row.id,
        "salary_count_mode": row.salary_count_mode,
        "monthly_salary_days": row.monthly_salary_days,
        "week_off_days": _week_offs(row),
        "timezone": row.timezone or "Asia/Kolkata",
        "updated_at": row.updated_at,
    }


def _calendar_type(day: date, week_off_days: list[int], overrides: dict[date, str]) -> str:
    return overrides.get(day, "week_off" if day.weekday() in week_off_days else "working_day")


def _salary_count_divisor(
    year: int,
    month: int,
    mode: str,
    monthly_salary_days: int,
    week_off_days: list[int],
    overrides: dict[date, str],
) -> int:
    days_in_month = calendar.monthrange(year, month)[1]
    if mode == "calendar_days":
        return days_in_month
    if mode == "fixed_days":
        return max(1, min(31, monthly_salary_days))
    return max(
        1,
        sum(
            _calendar_type(date(year, month, number), week_off_days, overrides) == "working_day"
            for number in range(1, days_in_month + 1)
        ),
    )


def _salary_components(profile: models.EmployeeSalaryProfile | None) -> dict[str, Decimal]:
    zero = Decimal("0.00")
    if profile is None:
        return {
            "annual_salary": zero, "monthly_gross": zero, "basic": zero, "hra": zero,
            "da": zero, "conveyance": zero, "medical_allowance": zero,
            "special_allowance": zero, "employee_pf": zero, "professional_tax": zero, "tds": zero,
        }
    annual = _money(_dec(profile.annual_salary))
    gross = _money(annual / Decimal("12"))
    basic = _money(gross * _dec(profile.basic_pct) / Decimal("100"))
    hra = _money(basic * _dec(profile.hra_pct) / Decimal("100"))
    da = _money(gross * _dec(profile.da_pct) / Decimal("100"))
    conveyance = _money(_dec(profile.conveyance_monthly))
    medical = _money(_dec(profile.medical_allowance_monthly))
    special = _money(gross - basic - hra - da - conveyance - medical)
    return {
        "annual_salary": annual, "monthly_gross": gross, "basic": basic, "hra": hra, "da": da,
        "conveyance": conveyance, "medical_allowance": medical, "special_allowance": special,
        "employee_pf": _money(basic * _dec(profile.pf_pct) / Decimal("100")),
        "professional_tax": _money(_dec(profile.professional_tax_monthly)),
        "tds": _money(_dec(profile.tds_monthly)),
    }


def _calculate_employee_monthly_payroll(
    employee: Any,
    profile: models.EmployeeSalaryProfile | None,
    attendance_rows: list[Any],
    year: int,
    month: int,
    salary_count_mode: str,
    monthly_salary_days: int,
    week_off_days: list[int],
    calendar_overrides: dict[date, str],
) -> dict[str, Any]:
    components = _salary_components(profile)
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    employment_start = max(month_start, employee.joining_date) if employee.joining_date else month_start
    employment_end = min(month_end, employee.end_date) if employee.end_date else month_end
    employment_active = employment_start <= employment_end
    divisor = _salary_count_divisor(
        year, month, salary_count_mode, monthly_salary_days, week_off_days, calendar_overrides
    )
    scheduled_days = [
        date(year, month, number)
        for number in range(1, month_end.day + 1)
        if _calendar_type(date(year, month, number), week_off_days, calendar_overrides) == "working_day"
    ]
    eligible_working_days = [
        day for day in scheduled_days
        if employment_active and employment_start <= day <= employment_end
    ]
    eligible_calendar_days = max(0, (employment_end - employment_start).days + 1) if employment_active else 0

    # Prorate the monthly gross for partial-month employment using the configured
    # salary basis. Fixed-days mode retains its configured divisor; the employee's
    # eligible scheduled days determine the paid fraction of the standard month.
    if not employment_active:
        employment_fraction = Decimal("0")
    elif salary_count_mode == "calendar_days":
        employment_fraction = Decimal(eligible_calendar_days) / Decimal(month_end.day)
    elif salary_count_mode == "fixed_days":
        # The fixed divisor is a daily-rate basis, not a proxy for how much
        # of the month the employee was employed. Compare eligible scheduled
        # days with the month's full scheduled days so a full-month employee
        # receives a full monthly gross even when the month has fewer than 26
        # scheduled days (for example, because of holidays).
        full_month_working_days = len(scheduled_days)
        employment_fraction = (
            Decimal(len(eligible_working_days)) / Decimal(full_month_working_days)
            if full_month_working_days else Decimal("0")
        )
    else:
        full_month_working_days = len(scheduled_days)
        employment_fraction = (
            Decimal(len(eligible_working_days)) / Decimal(full_month_working_days)
            if full_month_working_days else Decimal("0")
        )
    employment_fraction = min(Decimal("1"), max(Decimal("0"), employment_fraction))
    effective_gross = _money(components["monthly_gross"] * employment_fraction)
    present_days = half_days = absent_days = paid_leave_days = unpaid_leave_days = Decimal("0")
    unpaid_equivalent_days = Decimal("0")
    overtime_minutes = 0
    for row in attendance_rows:
        work_date = getattr(row, "work_date", None)
        in_employment_period = (
            work_date is not None and employment_active
            and employment_start <= work_date <= employment_end
        )
        if not in_employment_period:
            continue
        scheduled_workday = _calendar_type(work_date, week_off_days, calendar_overrides) == "working_day"
        if row.status == "present":
            present_days += Decimal("1")
        elif row.status == "half_day":
            half_days += Decimal("1")
            if scheduled_workday:
                unpaid_equivalent_days += Decimal("0.5")
        elif row.status == "absent":
            absent_days += Decimal("1")
            if scheduled_workday:
                unpaid_equivalent_days += Decimal("1")
        elif row.status == "paid_leave":
            paid_leave_days += Decimal("1")
        elif row.status == "unpaid_leave":
            unpaid_leave_days += Decimal("1")
            if scheduled_workday:
                unpaid_equivalent_days += Decimal("1")
        elif row.status == "paid_half_day":
            half_days += Decimal("1")
            paid_leave_days += Decimal("0.5")
        elif row.status == "unpaid_half_day":
            half_days += Decimal("1")
            unpaid_leave_days += Decimal("0.5")
            if scheduled_workday:
                unpaid_equivalent_days += Decimal("0.5")
        if in_employment_period and row.status in {"present", "half_day"}:
            overtime_minutes += max(0, int(row.overtime_minutes or 0))

    absence_divisor = (
        Decimal(eligible_calendar_days) if salary_count_mode == "calendar_days"
        else Decimal(len(eligible_working_days)) if salary_count_mode == "working_days"
        else Decimal(divisor)
    )
    if salary_count_mode == "fixed_days":
        absence_divisor = Decimal(divisor)
    daily_rate = effective_gross / absence_divisor if absence_divisor > 0 else Decimal("0")
    absence_deduction = min(effective_gross, _money(daily_rate * unpaid_equivalent_days))
    overtime_pay = _money((daily_rate / Decimal("8")) * Decimal(overtime_minutes) / Decimal("60"))
    # Statutory/contractual deductions are prorated with employment fraction too;
    # jurisdiction-specific compliance and effective-dated structures remain separate work.
    prorated_pf = _money(components["employee_pf"] * employment_fraction)
    prorated_pt = _money(components["professional_tax"] * employment_fraction)
    prorated_tds = _money(components["tds"] * employment_fraction)
    net_pay = max(
        Decimal("0.00"),
        _money(effective_gross - absence_deduction - prorated_pf - prorated_pt - prorated_tds + overtime_pay),
    )
    return {
        "employee_id": employee.id, "employee_code": employee.emp_code, "employee_name": employee.name,
        "department": employee.department or "", "configured": profile is not None and components["annual_salary"] > 0,
        **components,
        "monthly_gross": effective_gross,
        "employee_pf": prorated_pf, "professional_tax": prorated_pt, "tds": prorated_tds,
        "present_days": _money(present_days), "half_days": _money(half_days),
        "absent_days": _money(absent_days), "paid_leave_days": _money(paid_leave_days),
        "unpaid_leave_days": _money(unpaid_leave_days), "overtime_minutes": overtime_minutes,
        "absence_deduction": absence_deduction, "overtime_pay": overtime_pay, "net_pay": net_pay,
    }

def _validate_period(year: int, month: int) -> None:
    if month < 1 or month > 12 or year < 2000 or year > 2100:
        raise HTTPException(
            status_code=422,
            detail="Payroll period must use a valid month and year from 2000 to 2100",
        )


def _period_data(
    db: Session, year: int, month: int
) -> tuple[date, date, models.HRPayrollSettings, dict[date, str], list[models.Employee]]:
    _validate_period(year, month)
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    settings = _ensure_settings(db)
    override_rows = db.query(models.HRCalendarDay).filter(
        models.HRCalendarDay.work_date >= start, models.HRCalendarDay.work_date <= end
    ).all()
    overrides = {row.work_date: row.day_type for row in override_rows}
    employees = db.query(models.Employee).filter(
        models.Employee.active.is_(True)
    ).order_by(models.Employee.emp_code).all()
    return start, end, settings, overrides, employees


def _preview_data(db: Session, year: int, month: int) -> dict[str, Any]:
    start, end, settings, overrides, employees = _period_data(db, year, month)
    week_off_days = _week_offs(settings)
    profiles = {row.employee_id: row for row in db.query(models.EmployeeSalaryProfile).all()}
    attendances = db.query(models.EmployeeAttendance).filter(
        models.EmployeeAttendance.work_date >= start, models.EmployeeAttendance.work_date <= end
    ).all()
    attendance_by_employee: dict[str, list[Any]] = {}
    for row in attendances:
        attendance_by_employee.setdefault(row.employee_id, []).append(row)
    items = [
        _calculate_employee_monthly_payroll(
            employee, profiles.get(employee.id), attendance_by_employee.get(employee.id, []),
            year, month, settings.salary_count_mode, settings.monthly_salary_days,
            week_off_days, overrides,
        )
        for employee in employees
    ]
    salary_count_days = _salary_count_divisor(
        year, month, settings.salary_count_mode, settings.monthly_salary_days, week_off_days, overrides
    )
    return {
        "year": year, "month": month, "salary_count_mode": settings.salary_count_mode,
        "salary_count_days": salary_count_days, "items": items,
    }


def _item_output(item: models.HRPayrollItem) -> dict[str, Any]:
    return {
        "employee_id": item.employee_id, "employee_code": item.employee_code,
        "employee_name": item.employee_name, "department": item.department, "configured": True,
        "annual_salary": float(item.annual_salary), "monthly_gross": float(item.monthly_gross),
        "basic": float(item.basic), "hra": float(item.hra), "da": float(item.da),
        "conveyance": float(item.conveyance), "medical_allowance": float(item.medical_allowance),
        "special_allowance": float(item.special_allowance), "employee_pf": float(item.employee_pf),
        "professional_tax": float(item.professional_tax), "tds": float(item.tds),
        "absence_deduction": float(item.absence_deduction), "overtime_pay": float(item.overtime_pay),
        "net_pay": float(item.net_pay), "present_days": float(item.present_days),
        "half_days": float(item.half_days), "absent_days": float(item.absent_days),
        "paid_leave_days": float(item.paid_leave_days), "unpaid_leave_days": float(item.unpaid_leave_days),
        "overtime_minutes": item.overtime_minutes,
    }


def _run_output(db: Session, run: models.HRPayrollRun, include_items: bool = True) -> dict[str, Any]:
    items = db.query(models.HRPayrollItem).filter(
        models.HRPayrollItem.payroll_run_id == run.id
    ).order_by(models.HRPayrollItem.employee_code).all()
    result: dict[str, Any] = {
        "id": run.id, "year": run.year, "month": run.month, "status": run.status,
        "created_by": run.created_by, "created_at": run.created_at, "finalized_at": run.finalized_at,
        "revision": run.revision, "approved_by": run.approved_by, "approved_at": run.approved_at,
        "locked_at": run.locked_at, "reversed_at": run.reversed_at, "reversal_reason": run.reversal_reason,
        "employee_count": len(items), "net_total": round(sum(float(item.net_pay) for item in items), 2),
    }
    if include_items:
        result["items"] = [_item_output(item) for item in items]
    return result


def _attendance_output(
    employee: models.Employee, work_date: date, row: models.EmployeeAttendance | None,
    calendar_type: str, calendar_description: str, tenant_tz: ZoneInfo,
    work_timezone: ZoneInfo | None = None,
) -> dict[str, Any]:
    timezone_name = (
        row.timezone_name if row and row.timezone_name
        else (work_timezone.key if work_timezone else tenant_tz.key)
    )
    display_tz = ZoneInfo(timezone_name)
    return {
        "id": row.id if row else None, "employee_id": employee.id, "employee_code": employee.emp_code,
        "employee_name": employee.name, "work_date": work_date,
        "status": row.status if row else (calendar_type if calendar_type in {"holiday", "week_off"} else "unmarked"),
        "calendar_type": calendar_type, "calendar_description": calendar_description,
        "punch_in": _to_local(row.punch_in, display_tz) if row else None, "punch_out": _to_local(row.punch_out, display_tz) if row else None,
        "overtime_minutes": row.overtime_minutes if row else 0, "note": row.note if row else "",
    }



_ATTENDANCE_EXCEL_HEADERS = [
    "Employee Code", "Work Date", "Status", "Overtime Minutes", "Punch In", "Punch Out", "Note",
]
_ATTENDANCE_EXCEL_STATUSES = {"present", "half_day", "absent", "paid_leave", "unpaid_leave", "paid_half_day", "unpaid_half_day", "unmarked"}
_MAX_ATTENDANCE_IMPORT_BYTES = 5 * 1024 * 1024
_MAX_ATTENDANCE_IMPORT_ROWS = 10000


def _attendance_template_workbook(year: int, month: int) -> io.BytesIO:
    """Build a blank, validated workbook. Example data is kept off the import sheet."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Attendance"
    sheet.append(_ATTENDANCE_EXCEL_HEADERS)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:G1"
    widths = [20, 16, 20, 20, 14, 14, 36]
    for column, width in enumerate(widths, start=1):
        sheet.column_dimensions[chr(64 + column)].width = width
        cell = sheet.cell(row=1, column=column)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="244062")
    for row_number in range(2, 1002):
        sheet.cell(row=row_number, column=2).number_format = "yyyy-mm-dd"
        sheet.cell(row=row_number, column=4).number_format = "0"
        sheet.cell(row=row_number, column=5).number_format = "hh:mm"
        sheet.cell(row=row_number, column=6).number_format = "hh:mm"
    status_validation = DataValidation(
        type="list",
        formula1='"present,half_day,absent,paid_leave,unpaid_leave,paid_half_day,unpaid_half_day,unmarked"',
        allow_blank=False,
    )
    status_validation.errorTitle = "Invalid attendance status"
    status_validation.error = "Choose a status from the dropdown list."
    status_validation.promptTitle = "Attendance status"
    status_validation.prompt = "Choose one of the supported lowercase status values."
    sheet.add_data_validation(status_validation)
    status_validation.add("C2:C1001")

    instructions = workbook.create_sheet("Instructions")
    lines = [
        ["MiniTally Attendance Import Template"],
        [f"Selected import period: {calendar.month_name[month]} {year}"],
        ["Only the Attendance worksheet is imported. The Instructions worksheet is ignored."],
        ["Keep the seven column headers on row 1 of Attendance exactly as provided."],
        ["Use one row per employee per work date. Do not upload duplicate employee/date pairs."],
        ["Employee Code: exact code of an active employee, for example EMP-001."],
        ["Work Date: an Excel date or YYYY-MM-DD; every date must belong to the selected period."],
        ["Status: present, half_day, absent, paid_leave, unpaid_leave, paid_half_day, unpaid_half_day, or unmarked."],
        ["Overtime Minutes: whole number from 0 to 1440; leave blank or enter 0 if none."],
        ["Punch In / Punch Out: optional Excel times (HH:MM). Punch Out must be after Punch In."],
        ["Note: optional text describing the attendance entry."],
        ["Use unmarked to clear any existing attendance entry for that employee/date."],
        ["The import validates every row first. If any row is invalid, nothing is imported."],
        [""],
        ["Example (documentation only; this row is NOT imported):"],
        _ATTENDANCE_EXCEL_HEADERS,
        ["EMP-001", date(year, month, 1), "present", 0, time_type(8, 30), time_type(17, 0), "Example only"],
    ]
    for row in lines:
        instructions.append(row)
    instructions["A1"].font = Font(bold=True, size=15, color="244062")
    instructions.column_dimensions["A"].width = 110
    for cell in instructions[16]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="244062")
    instructions["B17"].number_format = "yyyy-mm-dd"
    instructions["E17"].number_format = "hh:mm"
    instructions["F17"].number_format = "hh:mm"

    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    buffer.seek(0)
    return buffer


def _parse_attendance_excel_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        raw = value.strip()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
    raise ValueError("Work Date must be an Excel date or YYYY-MM-DD")


def _parse_attendance_excel_time(value: Any) -> time_type | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, datetime):
        return value.time().replace(tzinfo=None)
    if isinstance(value, time_type):
        return value.replace(tzinfo=None)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        converted = from_excel(value)
        if isinstance(converted, datetime):
            return converted.time().replace(tzinfo=None)
        if isinstance(converted, time_type):
            return converted.replace(tzinfo=None)
    if isinstance(value, str):
        raw = value.strip()
        try:
            return time_type.fromisoformat(raw)
        except ValueError:
            for fmt in ("%H:%M", "%H:%M:%S"):
                try:
                    return datetime.strptime(raw, fmt).time()
                except ValueError:
                    continue
    raise ValueError("time must be in HH:MM or HH:MM:SS format")


def _parse_attendance_workbook(
    content: bytes,
    year: int,
    month: int,
    employees_by_code: dict[str, Any],
    tenant_tz: ZoneInfo | None = None,
    *,
    db: Session | None = None,
    branch_id: str | None = None,
    allow_overnight: bool = False,
) -> list[dict[str, Any]]:
    """Validate all workbook rows and normalize timestamps using one batch timezone."""
    _validate_period(year, month)
    selected_tz = tenant_tz or ZoneInfo("Asia/Kolkata")
    try:
        workbook = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    except (InvalidFileException, BadZipFile, OSError, ValueError) as exc:
        raise ValueError("The file is not a readable Excel .xlsx workbook. Download the MiniTally template and try again.") from exc

    try:
        if "Attendance" not in workbook.sheetnames:
            raise ValueError('Workbook must contain a worksheet named "Attendance".')
        sheet = workbook["Attendance"]
        header_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
        headers = [str(value).strip() if value is not None else "" for value in (header_row or ())]
        while headers and not headers[-1]:
            headers.pop()
        if headers != _ATTENDANCE_EXCEL_HEADERS:
            expected = ", ".join(_ATTENDANCE_EXCEL_HEADERS)
            raise ValueError(f"Attendance worksheet headers must match the template exactly: {expected}.")

        parsed: list[dict[str, Any]] = []
        errors: list[str] = []
        seen: set[tuple[str, date]] = set()
        batch_branch_ids: set[str | None] = set()
        nonempty_count = 0

        for row_number, values in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            cells = list(values[:len(_ATTENDANCE_EXCEL_HEADERS)])
            cells.extend([None] * (len(_ATTENDANCE_EXCEL_HEADERS) - len(cells)))
            if not any(value is not None and (not isinstance(value, str) or value.strip()) for value in cells):
                continue
            nonempty_count += 1
            if nonempty_count > _MAX_ATTENDANCE_IMPORT_ROWS:
                errors.append(f"More than {_MAX_ATTENDANCE_IMPORT_ROWS} attendance rows were supplied.")
                break

            row_error_start = len(errors)
            raw_code, raw_date, raw_status, raw_overtime, raw_punch_in, raw_punch_out, raw_note = cells
            code = str(raw_code).strip().upper() if raw_code is not None else ""
            employee = employees_by_code.get(code)
            if not code:
                errors.append(f"Row {row_number}: Employee Code is required.")
            elif employee is None:
                errors.append(f"Row {row_number}: employee code {code!r} was not found or is inactive.")

            work_date = None
            try:
                work_date = _parse_attendance_excel_date(raw_date)
                if work_date.year != year or work_date.month != month:
                    errors.append(f"Row {row_number}: Work Date must be in {year}-{month:02d}.")
            except ValueError as exc:
                errors.append(f"Row {row_number}: {exc}.")

            context = None
            if employee is not None and work_date is not None:
                if db is not None:
                    try:
                        context = resolve_employee_work_context(db, employee.id, work_date)
                        batch_branch_ids.add(context.branch_id)
                    except ShiftAssignmentConfigurationError as exc:
                        errors.append(f"Row {row_number}: {exc}.")
                if branch_id is not None and (context is None or context.branch_id != branch_id):
                    errors.append(f"Row {row_number}: employee {code} is not assigned to the selected branch on {work_date}.")
                if branch_id is None and context is not None and context.branch_id is not None:
                    errors.append(f"Row {row_number}: employee {code} is assigned to branch {context.branch_id}; select that branch for this batch.")

            status = str(raw_status).strip().lower().replace("-", "_").replace(" ", "_") if raw_status is not None else ""
            if status not in _ATTENDANCE_EXCEL_STATUSES:
                errors.append(f"Row {row_number}: Status must be one of {', '.join(sorted(_ATTENDANCE_EXCEL_STATUSES))}.")

            overtime_minutes = 0
            if raw_overtime is not None and str(raw_overtime).strip():
                try:
                    overtime_number = float(raw_overtime)
                    if isinstance(raw_overtime, bool) or not overtime_number.is_integer() or not 0 <= overtime_number <= 1440:
                        raise ValueError
                    overtime_minutes = int(overtime_number)
                except (TypeError, ValueError):
                    errors.append(f"Row {row_number}: Overtime Minutes must be a whole number from 0 to 1440.")

            punch_in = punch_out = None
            punch_in_local = punch_out_local = None
            try:
                punch_time = _parse_attendance_excel_time(raw_punch_in)
                if punch_time is not None and work_date is not None:
                    punch_in_local = datetime.combine(work_date, punch_time)
                    punch_in = localize_attendance_datetime(punch_in_local, selected_tz.key)
            except (ValueError, ShiftAssignmentConfigurationError) as exc:
                errors.append(f"Row {row_number}: Punch In {exc}.")

            try:
                punch_time = _parse_attendance_excel_time(raw_punch_out)
                if punch_time is not None and work_date is not None:
                    punch_out_local = datetime.combine(work_date, punch_time)
                    if punch_in_local is not None and punch_out_local <= punch_in_local:
                        scheduled = None
                        if allow_overnight and db is not None and employee is not None:
                            try:
                                scheduled = resolve_shift_for_work_date(db, employee.id, work_date)
                            except ShiftAssignmentConfigurationError as exc:
                                errors.append(f"Row {row_number}: {exc}.")
                        if (
                            scheduled is not None
                            and scheduled.scheduled_start_at_utc is not None
                            and scheduled.scheduled_end_at_utc is not None
                            and scheduled.scheduled_end_at_utc > scheduled.scheduled_start_at_utc
                        ):
                            punch_out_local += timedelta(days=1)
                        else:
                            errors.append(f"Row {row_number}: Punch Out is earlier than Punch In; a scheduled overnight shift is required.")
                    punch_out = localize_attendance_datetime(punch_out_local, selected_tz.key)
            except (ValueError, ShiftAssignmentConfigurationError) as exc:
                errors.append(f"Row {row_number}: Punch Out {exc}.")

            if punch_in is not None and punch_out is not None and punch_out <= punch_in:
                errors.append(f"Row {row_number}: Punch Out must be after Punch In.")

            note = str(raw_note).strip() if raw_note is not None else ""
            if len(note) > 4000:
                errors.append(f"Row {row_number}: Note must be 4000 characters or fewer.")

            if work_date is not None and code:
                key = (code, work_date)
                if key in seen:
                    errors.append(f"Row {row_number}: duplicate Employee Code and Work Date pair ({code}, {work_date}).")
                seen.add(key)

            if len(errors) == row_error_start and employee is not None and work_date is not None:
                parsed.append({
                    "employee_id": employee.id,
                    "employee_code": code,
                    "work_date": work_date,
                    "branch_id": context.branch_id if context else None,
                    "timezone_name": selected_tz.key,
                    "status": status,
                    "overtime_minutes": overtime_minutes,
                    "punch_in": punch_in,
                    "punch_out": punch_out,
                    "note": note,
                })

        if nonempty_count == 0:
            errors.append("Attendance worksheet has no attendance rows.")
        if len(batch_branch_ids) > 1:
            errors.append("Attendance workbook contains employees from multiple branches. Split the workbook into one import per branch.")
        if errors:
            shown = errors[:30]
            suffix = f"\n…and {len(errors) - len(shown)} additional issue(s)." if len(errors) > len(shown) else ""
            raise ValueError("Attendance import validation failed:\n" + "\n".join(shown) + suffix)
        return parsed
    finally:
        workbook.close()


@router.get("/payroll/settings", response_model=schemas.PayrollSettingsOut)
def get_payroll_settings(db: Session = Depends(get_db), user: models.User = hr_access):
    return _settings_output(_ensure_settings(db))


@router.put("/payroll/settings", response_model=schemas.PayrollSettingsOut)
def update_payroll_settings(
    payload: schemas.PayrollSettingsIn, db: Session = Depends(get_db), user: models.User = hr_access,
    permission: models.User = Depends(require_permission("hr", "payroll", "write", "tenant")),
):
    _ensure_no_pending_payroll_snapshot(db)
    row = _ensure_settings(db)
    row.salary_count_mode = payload.salary_count_mode
    row.monthly_salary_days = payload.monthly_salary_days
    row.week_off_days = ",".join(str(day) for day in payload.week_off_days)
    try:
        ZoneInfo(payload.timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail="Timezone must be a valid IANA timezone identifier") from exc
    row.timezone = payload.timezone
    log_audit(db, user.username, "UPDATE", "hr_payroll_settings", payload.salary_count_mode)
    db.commit()
    db.refresh(row)
    return _settings_output(row)


@router.get("/calendar", response_model=list[schemas.CalendarDayOut])
def get_hr_calendar(
    year: int = Query(ge=2000, le=2100), month: int = Query(ge=1, le=12),
    db: Session = Depends(get_db), user: models.User = hr_access,
):
    start, end, settings, overrides, _ = _period_data(db, year, month)
    rows = {
        row.work_date: row for row in db.query(models.HRCalendarDay).filter(
            models.HRCalendarDay.work_date >= start, models.HRCalendarDay.work_date <= end
        ).all()
    }
    week_off_days = _week_offs(settings)
    return [{
        "work_date": (day := date(year, month, number)),
        "day_type": _calendar_type(day, week_off_days, overrides),
        "description": rows[day].description if day in rows else "",
        "is_override": day in rows,
    } for number in range(1, end.day + 1)]


@router.put("/calendar/{work_date}", response_model=schemas.CalendarDayOut)
def update_hr_calendar_day(
    work_date: date, payload: schemas.CalendarDayIn,
    db: Session = Depends(get_db), user: models.User = hr_access,
    permission: models.User = Depends(require_permission("hr", "payroll", "write", "tenant")),
):
    _ensure_period_not_prepared(db, work_date.year, work_date.month)
    _ensure_settings(db)
    row = db.query(models.HRCalendarDay).filter_by(work_date=work_date).first()
    if row is None:
        row = models.HRCalendarDay(work_date=work_date, day_type=payload.day_type, description=payload.description.strip())
        db.add(row)
    else:
        row.day_type = payload.day_type
        row.description = payload.description.strip()
    log_audit(db, user.username, "UPSERT", "hr_calendar_day", f"{work_date}:{payload.day_type}")
    db.commit()
    db.refresh(row)
    return {"work_date": row.work_date, "day_type": row.day_type, "description": row.description, "is_override": True}


@router.delete("/calendar/{work_date}", status_code=204)
def delete_hr_calendar_override(
    work_date: date, db: Session = Depends(get_db), user: models.User = hr_access,
    permission: models.User = Depends(require_permission("hr", "payroll", "write", "tenant")),
):
    _ensure_period_not_prepared(db, work_date.year, work_date.month)
    row = db.query(models.HRCalendarDay).filter_by(work_date=work_date).first()
    if row is not None:
        db.delete(row)
        log_audit(db, user.username, "DELETE", "hr_calendar_day", str(work_date))
        db.commit()
    return Response(status_code=204)


def _salary_output(employee: models.Employee, profile: models.EmployeeSalaryProfile | None) -> dict[str, Any]:
    components = _salary_components(profile)
    return {
        "employee_id": employee.id, "employee_code": employee.emp_code, "employee_name": employee.name,
        "department": employee.department or "", "active": employee.active, "configured": profile is not None,
        "annual_salary": float(components["annual_salary"]),
        "basic_pct": float(profile.basic_pct) if profile else 50.0,
        "hra_pct": float(profile.hra_pct) if profile else 40.0,
        "da_pct": float(profile.da_pct) if profile else 0.0,
        "conveyance_monthly": float(profile.conveyance_monthly) if profile else 0.0,
        "medical_allowance_monthly": float(profile.medical_allowance_monthly) if profile else 0.0,
        "pf_pct": float(profile.pf_pct) if profile else 12.0,
        "professional_tax_monthly": float(profile.professional_tax_monthly) if profile else 200.0,
        "tds_monthly": float(profile.tds_monthly) if profile else 0.0,
        "monthly_gross": float(components["monthly_gross"]), "basic": float(components["basic"]),
        "hra": float(components["hra"]), "da": float(components["da"]),
        "conveyance": float(components["conveyance"]), "medical_allowance": float(components["medical_allowance"]),
        "special_allowance": float(components["special_allowance"]), "employee_pf": float(components["employee_pf"]),
        "professional_tax": float(components["professional_tax"]), "tds": float(components["tds"]),
        "updated_at": profile.updated_at if profile else None,
    }


@router.get("/salaries", response_model=list[schemas.EmployeeSalaryOut])
def list_employee_salaries(db: Session = Depends(get_db), user: models.User = hr_access):
    # Salary and attendance workflows operate on active employees. Inactive
    # employees remain available in the employee history UI, but shouldn't
    # reappear in the active Payroll workspace after a demo reset/deactivation.
    employees = db.query(models.Employee).filter(
        models.Employee.active.is_(True)
    ).order_by(models.Employee.emp_code).all()
    profiles = {row.employee_id: row for row in db.query(models.EmployeeSalaryProfile).all()}
    return [_salary_output(employee, profiles.get(employee.id)) for employee in employees]


@router.put("/employees/{employee_id}/salary", response_model=schemas.EmployeeSalaryOut)
def upsert_employee_salary(
    employee_id: str, payload: schemas.EmployeeSalaryIn,
    db: Session = Depends(get_db), user: models.User = hr_access,
    permission: models.User = Depends(require_permission("hr", "payroll", "write", "tenant")),
):
    employee = db.get(models.Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    _ensure_no_pending_payroll_snapshot(db)
    annual = _dec(payload.annual_salary)
    gross = annual / Decimal("12")
    basic = gross * _dec(payload.basic_pct) / Decimal("100")
    hra = basic * _dec(payload.hra_pct) / Decimal("100")
    da = gross * _dec(payload.da_pct) / Decimal("100")
    fixed = _dec(payload.conveyance_monthly) + _dec(payload.medical_allowance_monthly)
    if basic + hra + da + fixed > gross:
        raise HTTPException(status_code=422, detail="Salary components exceed monthly gross salary; reduce percentages or fixed allowances")
    profile = db.get(models.EmployeeSalaryProfile, employee_id)
    if profile is None:
        profile = models.EmployeeSalaryProfile(employee_id=employee_id, annual_salary=payload.annual_salary)
        db.add(profile)
    for field in (
        "annual_salary", "basic_pct", "hra_pct", "da_pct", "conveyance_monthly",
        "medical_allowance_monthly", "pf_pct", "professional_tax_monthly", "tds_monthly",
    ):
        setattr(profile, field, getattr(payload, field))
    log_audit(db, user.username, "UPSERT", "employee_salary_profile", employee.emp_code)
    db.commit()
    db.refresh(profile)
    return _salary_output(employee, profile)


@router.get("/attendance/monthly", response_model=list[schemas.EmployeeAttendanceOut])
def get_monthly_attendance(
    employee_id: str, year: int = Query(ge=2000, le=2100), month: int = Query(ge=1, le=12),
    db: Session = Depends(get_db), user: models.User = hr_access,
):
    start, end, settings, overrides, _ = _period_data(db, year, month)
    employee = db.get(models.Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    records = db.query(models.EmployeeAttendance).filter(
        models.EmployeeAttendance.employee_id == employee_id,
        models.EmployeeAttendance.work_date >= start, models.EmployeeAttendance.work_date <= end,
    ).all()
    by_date = {record.work_date: record for record in records}
    calendar_rows = db.query(models.HRCalendarDay).filter(
        models.HRCalendarDay.work_date >= start, models.HRCalendarDay.work_date <= end
    ).all()
    descriptions = {row.work_date: row.description for row in calendar_rows}
    week_off_days = _week_offs(settings)
    tenant_tz = _tenant_timezone(db)
    visible_days = []
    for day in (date(year, month, number) for number in range(1, end.day + 1)):
        scoped_ids = employee_scope_ids(
            db, user, "hr", "employees", "read", as_of_date=day,
        )
        if scoped_ids is None or employee_id in scoped_ids:
            visible_days.append(day)
    if not visible_days:
        raise HTTPException(status_code=403, detail="Employee is outside your configured attendance access scope")
    output = []
    for day in visible_days:
        record = by_date.get(day)
        if record is not None and record.timezone_name:
            display_tz = ZoneInfo(record.timezone_name)
        else:
            context = _attendance_context(db, employee.id, day)
            display_tz = ZoneInfo(context.timezone_name)
        output.append(
            _attendance_output(
                employee, day, record, _calendar_type(day, week_off_days, overrides),
                descriptions.get(day, ""), tenant_tz, display_tz,
            )
        )
    return output



@router.get("/attendance/template")
def download_attendance_template(
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
    db: Session = Depends(get_db),
    user: models.User = hr_access,
):
    _validate_period(year, month)
    workbook = _attendance_template_workbook(year, month)
    filename = f"minitally-attendance-template-{year}-{month:02d}.xlsx"
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/attendance/import")
async def import_attendance_from_excel(
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
    branch_id: str | None = Query(default=None, min_length=1, max_length=36),
    import_timezone: str | None = Query(default=None, min_length=1, max_length=64),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = hr_access,
    permission: models.User = Depends(require_permission("hr", "payroll", "write", "tenant")),
):
    _validate_period(year, month)
    _ensure_period_not_prepared(db, year, month)
    settings = _ensure_settings(db)
    if branch_id is not None:
        branch = db.get(models.HRBranch, branch_id)
        if branch is None or not branch.active:
            raise HTTPException(status_code=422, detail="Select an active branch for this attendance import")
        branch_timezone = (branch.timezone or "").strip()
        default_timezone = branch_timezone or (settings.timezone or "Asia/Kolkata")
    else:
        default_timezone = settings.timezone or "Asia/Kolkata"
    selected_timezone = import_timezone or default_timezone
    try:
        import_tz = ZoneInfo(selected_timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail="Import timezone must be a valid IANA timezone identifier") from exc

    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=415, detail="Upload an .xlsx Excel workbook using the MiniTally attendance template.")
    content = await file.read(_MAX_ATTENDANCE_IMPORT_BYTES + 1)
    await file.close()
    if len(content) > _MAX_ATTENDANCE_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="Attendance workbook must be 5 MB or smaller.")

    employees_by_code = {
        row.emp_code.strip().upper(): row
        for row in db.query(models.Employee).filter(
            models.Employee.active.is_(True),
            models.Employee.joining_date <= date(year, month, calendar.monthrange(year, month)[1]),
            (models.Employee.end_date.is_(None)) | (models.Employee.end_date >= date(year, month, 1)),
        ).all()
    }
    try:
        rows = _parse_attendance_workbook(
            content, year, month, employees_by_code, import_tz,
            db=db, branch_id=branch_id, allow_overnight=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    resolved_branches = {item["branch_id"] for item in rows}
    if len(resolved_branches) > 1:
        raise HTTPException(
            status_code=422,
            detail="Attendance workbook contains employees from multiple branches. Split the workbook into one import per branch.",
        )
    actual_branch = next(iter(resolved_branches), None)
    if actual_branch != branch_id:
        raise HTTPException(
            status_code=422,
            detail="Selected batch branch does not match every employee's effective branch for the imported work dates.",
        )

    scope_cache: dict[date, list[str] | None] = {}
    for item in rows:
        work_date = item["work_date"]
        if work_date not in scope_cache:
            scope_cache[work_date] = employee_scope_ids(
                db, user, "hr", "employees", "update", as_of_date=work_date,
            )
        scoped_ids = scope_cache[work_date]
        if scoped_ids is not None and item["employee_id"] not in scoped_ids:
            raise HTTPException(
                status_code=403,
                detail=f"Attendance import includes an employee outside your access scope on {work_date}",
            )

    created = updated = cleared = 0
    try:
        for item in rows:
            existing = db.query(models.EmployeeAttendance).filter_by(
                employee_id=item["employee_id"], work_date=item["work_date"]
            ).first()
            if item["status"] == "unmarked":
                if existing is not None:
                    db.delete(existing)
                    cleared += 1
                continue
            if existing is None:
                existing = models.EmployeeAttendance(
                    employee_id=item["employee_id"], work_date=item["work_date"],
                    branch_id=item["branch_id"], timezone_name=item["timezone_name"],
                    status=item["status"], overtime_minutes=item["overtime_minutes"],
                    punch_in=item["punch_in"], punch_out=item["punch_out"], note=item["note"],
                )
                db.add(existing)
                created += 1
            else:
                existing.branch_id = item["branch_id"]
                existing.timezone_name = item["timezone_name"]
                existing.status = item["status"]
                existing.overtime_minutes = item["overtime_minutes"]
                existing.punch_in = item["punch_in"]
                existing.punch_out = item["punch_out"]
                existing.note = item["note"]
                updated += 1
        log_audit(
            db, user.username, "IMPORT", "employee_attendance",
            f"{year}-{month:02d}: branch={actual_branch or 'unassigned'}; timezone={selected_timezone}; rows={len(rows)}; created={created}; updated={updated}; cleared={cleared}",
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Attendance changed concurrently. Refresh the month and import again.") from exc

    return {
        "year": year, "month": month, "branch_id": actual_branch,
        "timezone": selected_timezone, "rows_processed": len(rows),
        "created": created, "updated": updated, "cleared": cleared,
    }


@router.put("/attendance", response_model=schemas.EmployeeAttendanceOut)
def upsert_daily_attendance(
    payload: schemas.EmployeeAttendanceIn, db: Session = Depends(get_db), user: models.User = hr_access,
    permission: models.User = Depends(require_permission("hr", "payroll", "write", "tenant")),
):
    _ensure_period_not_prepared(db, payload.work_date.year, payload.work_date.month)
    employee = db.get(models.Employee, payload.employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    _ensure_attendance_employee_scope(db, user, payload.employee_id, payload.work_date, "update")
    context = _attendance_context(db, employee.id, payload.work_date)
    attendance_tz = ZoneInfo(context.timezone_name)
    try:
        punch_in = (
            localize_attendance_datetime(payload.punch_in, context.timezone_name)
            if payload.punch_in is not None else None
        )
        punch_out = (
            localize_attendance_datetime(payload.punch_out, context.timezone_name)
            if payload.punch_out is not None else None
        )
    except ShiftAssignmentConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if punch_in and punch_out and punch_out <= punch_in:
        raise HTTPException(status_code=422, detail="Punch-out must be after punch-in")
    row = db.query(models.EmployeeAttendance).filter_by(employee_id=payload.employee_id, work_date=payload.work_date).first()
    if payload.status == "unmarked":
        if row is not None:
            db.delete(row)
    elif row is None:
        row = models.EmployeeAttendance(
            employee_id=payload.employee_id, work_date=payload.work_date,
            branch_id=context.branch_id, timezone_name=context.timezone_name,
            status=payload.status, punch_in=punch_in, punch_out=punch_out,
            overtime_minutes=payload.overtime_minutes, note=payload.note.strip(),
        )
        db.add(row)
    else:
        row.branch_id = context.branch_id
        row.timezone_name = context.timezone_name
        row.status = payload.status
        row.punch_in = punch_in
        row.punch_out = punch_out
        row.overtime_minutes = payload.overtime_minutes
        row.note = payload.note.strip()
    log_audit(
        db, user.username, "UPSERT", "employee_attendance",
        f"{employee.emp_code}:{payload.work_date}:{payload.status}; branch={context.branch_id or 'unassigned'}; timezone={context.timezone_name}",
    )
    db.commit()
    row = db.query(models.EmployeeAttendance).filter_by(employee_id=payload.employee_id, work_date=payload.work_date).first()
    settings = _ensure_settings(db)
    override = db.query(models.HRCalendarDay).filter_by(work_date=payload.work_date).first()
    calendar_type = _calendar_type(payload.work_date, _week_offs(settings), {payload.work_date: override.day_type} if override else {})
    return _attendance_output(
        employee, payload.work_date, row, calendar_type,
        override.description if override else "", attendance_tz,
    )


@router.delete("/attendance/{employee_id}/{work_date}", status_code=204)
def clear_daily_attendance(
    employee_id: str, work_date: date, db: Session = Depends(get_db), user: models.User = hr_access,
    permission: models.User = Depends(require_permission("hr", "payroll", "write", "tenant")),
):
    employee = db.get(models.Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    _ensure_attendance_employee_scope(db, user, employee_id, work_date, "update")
    row = db.query(models.EmployeeAttendance).filter_by(employee_id=employee_id, work_date=work_date).first()
    if row is not None:
        db.delete(row)
        log_audit(db, user.username, "DELETE", "employee_attendance", f"{employee.emp_code}:{work_date}")
        db.commit()
    return Response(status_code=204)


@router.get("/payroll/preview", response_model=schemas.PayrollPreviewOut)
def preview_monthly_payroll(
    year: int = Query(ge=2000, le=2100), month: int = Query(ge=1, le=12),
    db: Session = Depends(get_db), user: models.User = hr_access,
):
    return _preview_data(db, year, month)


@router.get("/payroll/runs", response_model=list[schemas.PayrollRunSummaryOut])
def list_payroll_runs(db: Session = Depends(get_db), user: models.User = hr_access):
    runs = db.query(models.HRPayrollRun).order_by(
        models.HRPayrollRun.year.desc(), models.HRPayrollRun.month.desc(),
        models.HRPayrollRun.revision.desc(),
    ).all()
    return [_run_output(db, run, include_items=False) for run in runs]


@router.get("/payroll/runs/{year}/{month}", response_model=schemas.PayrollRunOut)
def get_payroll_run(
    year: int, month: int, db: Session = Depends(get_db), user: models.User = hr_access
):
    _validate_period(year, month)
    run = _latest_payroll_run(db, year, month)
    if run is None:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    return _run_output(db, run)


def _missing_payroll_attendance(
    db: Session, year: int, month: int
) -> tuple[list[tuple[str, date]], list[str]]:
    """Find missing daily statuses and salaried employees with unknown joining dates."""
    start, end, settings, overrides, employees = _period_data(db, year, month)
    week_off_days = _week_offs(settings)
    profiles = {
        row.employee_id: row
        for row in db.query(models.EmployeeSalaryProfile).all()
        if _dec(row.annual_salary) > 0
    }
    salaried_employees = [employee for employee in employees if employee.id in profiles]
    unknown_joining_dates = [
        employee.emp_code for employee in salaried_employees
        if employee.joining_date is None
    ]
    scheduled_days = [
        date(year, month, number)
        for number in range(1, end.day + 1)
        if _calendar_type(date(year, month, number), week_off_days, overrides) == "working_day"
    ]
    attendance_rows = db.query(models.EmployeeAttendance).filter(
        models.EmployeeAttendance.work_date >= start,
        models.EmployeeAttendance.work_date <= end,
        models.EmployeeAttendance.employee_id.in_([employee.id for employee in salaried_employees]),
    ).all() if salaried_employees else []
    recorded_statuses = {
        (row.employee_id, row.work_date): row.status
        for row in attendance_rows
    }
    explicit_statuses = {"present", "half_day", "absent", "paid_leave", "unpaid_leave", "paid_half_day", "unpaid_half_day"}
    missing: list[tuple[str, date]] = []
    for employee in salaried_employees:
        # Unknown legacy joining dates are not guessed. They are reported above,
        # and the full month remains subject to attendance completeness until HR
        # enters the actual joining date.
        eligible_days = [
            day for day in scheduled_days
            if (employee.joining_date is None or day >= employee.joining_date)
            and (employee.end_date is None or day <= employee.end_date)
        ]
        for work_date in eligible_days:
            status = recorded_statuses.get((employee.id, work_date))
            if status not in explicit_statuses:
                missing.append((employee.emp_code, work_date))
    return missing, unknown_joining_dates

def _latest_payroll_run(db: Session, year: int, month: int) -> models.HRPayrollRun | None:
    return db.query(models.HRPayrollRun).filter_by(year=year, month=month).order_by(
        models.HRPayrollRun.revision.desc()
    ).first()


def _payroll_readiness(db: Session, year: int, month: int) -> tuple[dict[str, Any], list[str]]:
    preview = _preview_data(db, year, month)
    configured_items = [item for item in preview["items"] if item["configured"] and item["annual_salary"] > 0]
    issues: list[str] = []
    if not configured_items:
        issues.append("Configure annual salary for at least one active employee")
    missing_attendance, unknown_joining_dates = _missing_payroll_attendance(db, year, month)
    if unknown_joining_dates:
        issues.append(
            "Joining dates are missing for active salaried employee(s): "
            + ", ".join(unknown_joining_dates[:20])
            + ("; additional employees require review" if len(unknown_joining_dates) > 20 else "")
        )
    if missing_attendance:
        examples = ", ".join(
            f"{employee_code} ({work_date.isoformat()})"
            for employee_code, work_date in missing_attendance[:20]
        )
        remaining = len(missing_attendance) - min(len(missing_attendance), 20)
        suffix = f"; and {remaining} more" if remaining else ""
        issues.append(
            f"{len(missing_attendance)} scheduled employee-day attendance record(s) are missing. "
            f"Record an explicit status for each working day. Missing: {examples}{suffix}"
        )
    return preview, issues


def _snapshot_payroll_run(
    db: Session, year: int, month: int, user: models.User, revision: int,
) -> models.HRPayrollRun:
    preview, issues = _payroll_readiness(db, year, month)
    if issues:
        raise HTTPException(status_code=409, detail="Payroll preparation blocked: " + " | ".join(issues))
    now = datetime.now(timezone.utc)
    run = models.HRPayrollRun(
        year=year, month=month, revision=revision, status="prepared",
        created_by=user.username, finalized_at=None,
    )
    db.add(run)
    db.flush()
    configured_items = [item for item in preview["items"] if item["configured"] and item["annual_salary"] > 0]
    for item in configured_items:
        db.add(models.HRPayrollItem(
            payroll_run_id=run.id, employee_id=item["employee_id"],
            employee_code=item["employee_code"], employee_name=item["employee_name"],
            department=item["department"], annual_salary=item["annual_salary"],
            monthly_gross=item["monthly_gross"], basic=item["basic"], hra=item["hra"], da=item["da"],
            conveyance=item["conveyance"], medical_allowance=item["medical_allowance"],
            special_allowance=item["special_allowance"], employee_pf=item["employee_pf"],
            professional_tax=item["professional_tax"], tds=item["tds"],
            absence_deduction=item["absence_deduction"], overtime_pay=item["overtime_pay"],
            net_pay=item["net_pay"], present_days=item["present_days"], half_days=item["half_days"],
            absent_days=item["absent_days"], paid_leave_days=item["paid_leave_days"],
            unpaid_leave_days=item["unpaid_leave_days"], overtime_minutes=item["overtime_minutes"],
        ))
    log_audit(db, user.username, "PREPARE", "hr_payroll_run", f"{year}-{month:02d}; revision={revision}")
    db.commit()
    db.refresh(run)
    return run


@router.post("/payroll/runs/{year}/{month}/prepare", response_model=schemas.PayrollRunOut)
def prepare_monthly_payroll(
    year: int, month: int, db: Session = Depends(get_db), user: models.User = hr_access,
    permission: models.User = Depends(require_permission("hr", "payroll", "prepare", "tenant")),
):
    _validate_period(year, month)
    existing = _latest_payroll_run(db, year, month)
    if existing is not None:
        if existing.status == "prepared":
            return _run_output(db, existing)
        if existing.status != "reversed":
            raise HTTPException(409, f"Payroll period already has a {existing.status} run; use the appropriate approval or reversal action")
        revision = existing.revision + 1
    else:
        revision = 1
    try:
        run = _snapshot_payroll_run(db, year, month, user, revision)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail="Payroll preparation conflicted with another request; refresh and retry") from exc
    return _run_output(db, run)


@router.post("/payroll/runs/{run_id}/approve", response_model=schemas.PayrollRunOut)
def approve_monthly_payroll(
    run_id: str, db: Session = Depends(get_db), user: models.User = hr_access,
    permission: models.User = Depends(require_permission("hr", "payroll", "approve", "tenant")),
):
    run = db.query(models.HRPayrollRun).filter_by(id=run_id).with_for_update().first()
    if run is None:
        raise HTTPException(404, "Payroll run not found")
    if run.status != "prepared":
        raise HTTPException(409, "Only prepared payroll runs can be approved")
    if run.created_by == user.username:
        raise HTTPException(403, "Payroll preparer cannot approve their own payroll run")
    run.status = "approved"
    run.approved_by = user.username
    run.approved_at = datetime.now(timezone.utc)
    log_audit(db, user.username, "APPROVE", "hr_payroll_run", f"{run.year}-{run.month:02d}; revision={run.revision}")
    db.commit()
    db.refresh(run)
    return _run_output(db, run)


@router.post("/payroll/runs/{year}/{month}/finalize", response_model=schemas.PayrollRunOut)
def finalize_monthly_payroll(
    year: int, month: int, db: Session = Depends(get_db), user: models.User = hr_access,
    permission: models.User = Depends(require_permission("hr", "payroll", "finalize", "tenant")),
):
    _validate_period(year, month)
    run = _latest_payroll_run(db, year, month)
    if run is None:
        raise HTTPException(409, "Prepare payroll and obtain a separate approval before finalization")
    if run.status in {"finalized", "locked"}:
        return _run_output(db, run)
    if run.status != "approved":
        raise HTTPException(409, "Payroll must be prepared and approved by a different authorized user before finalization")
    now = datetime.now(timezone.utc)
    try:
        journal = post_payroll_journal(db, run, user.username)
        db.flush()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
    run.status = "finalized"
    run.finalized_at = now
    log_audit(db, user.username, "FINALIZE", "hr_payroll_run", f"{year}-{month:02d}; revision={run.revision}; finance_journal={journal.journal_no}")
    db.commit()
    db.refresh(run)
    return _run_output(db, run)


@router.post("/payroll/runs/{run_id}/lock", response_model=schemas.PayrollRunOut)
def lock_monthly_payroll(
    run_id: str, db: Session = Depends(get_db), user: models.User = hr_access,
    permission: models.User = Depends(require_permission("hr", "payroll", "lock", "tenant")),
):
    run = db.query(models.HRPayrollRun).filter_by(id=run_id).with_for_update().first()
    if run is None:
        raise HTTPException(404, "Payroll run not found")
    if run.status != "finalized":
        raise HTTPException(409, "Only finalized payroll can be locked")
    run.status = "locked"
    run.locked_at = datetime.now(timezone.utc)
    log_audit(db, user.username, "LOCK", "hr_payroll_run", f"{run.year}-{run.month:02d}; revision={run.revision}")
    db.commit()
    db.refresh(run)
    return _run_output(db, run)


class PayrollReversalPayload(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)


@router.post("/payroll/runs/{run_id}/reverse", response_model=schemas.PayrollRunOut)
def reverse_monthly_payroll(
    run_id: str, payload: PayrollReversalPayload,
    db: Session = Depends(get_db), user: models.User = hr_access,
    permission: models.User = Depends(require_permission("hr", "payroll", "reverse", "tenant")),
):
    reason = payload.reason.strip()
    if len(reason) < 10 or len(reason) > 2000:
        raise HTTPException(422, "A reversal reason of 10 to 2000 characters is required")
    run = db.query(models.HRPayrollRun).filter_by(id=run_id).with_for_update().first()
    if run is None:
        raise HTTPException(404, "Payroll run not found")
    if run.status not in {"finalized", "locked"}:
        raise HTTPException(409, "Only finalized or locked payroll can be reversed")
    try:
        reversal_journal = reverse_payroll_journal(db, run, user.username, reason)
        db.flush()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
    run.status = "reversed"
    run.reversed_at = datetime.now(timezone.utc)
    run.reversal_reason = reason
    log_audit(db, user.username, "REVERSE", "hr_payroll_run", f"{run.year}-{run.month:02d}; revision={run.revision}; reason={reason}; finance_reversal={reversal_journal.journal_no}")
    db.commit()
    db.refresh(run)
    return _run_output(db, run)


@router.get("/payroll/slips/{employee_id}/{year}/{month}")
def download_salary_slip(
    employee_id: str, year: int, month: int, db: Session = Depends(get_db), user: models.User = Depends(current_user)
):
    _validate_period(year, month)
    run = _latest_payroll_run(db, year, month)
    if run is None or run.status not in {"finalized", "locked"}:
        raise HTTPException(status_code=404, detail="Finalize payroll for this month before downloading salary slips")
    if user.role not in (models.Role.admin, models.Role.hr):
        link = db.query(models.EmployeeUserLink).filter_by(user_id=user.id).first()
        if link is None or link.employee_id != employee_id:
            raise HTTPException(status_code=403, detail="Salary slips are available only to HR or the linked employee")
    item = db.query(models.HRPayrollItem).filter_by(payroll_run_id=run.id, employee_id=employee_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Salary slip not found for this employee and period")

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"Salary Slip {item.employee_code} {year}-{month:02d}")
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(48, 800, "MINITALLY — SALARY SLIP")
    lines = [
        ("Employee", item.employee_name), ("Employee Code", item.employee_code),
        ("Department", item.department or "—"), ("Salary Period", f"{calendar.month_name[month]} {year}"),
        ("Annual Salary", f"INR {float(item.annual_salary):,.2f}"),
        ("Monthly Gross", f"INR {float(item.monthly_gross):,.2f}"),
        ("Basic", f"INR {float(item.basic):,.2f}"), ("HRA", f"INR {float(item.hra):,.2f}"),
        ("DA", f"INR {float(item.da):,.2f}"), ("Conveyance", f"INR {float(item.conveyance):,.2f}"),
        ("Medical Allowance", f"INR {float(item.medical_allowance):,.2f}"),
        ("Special Allowance", f"INR {float(item.special_allowance):,.2f}"),
        ("Absence / Unpaid Leave", f"- INR {float(item.absence_deduction):,.2f}"),
        ("Employee PF", f"- INR {float(item.employee_pf):,.2f}"),
        ("Professional Tax", f"- INR {float(item.professional_tax):,.2f}"),
        ("TDS", f"- INR {float(item.tds):,.2f}"),
        ("Overtime Pay", f"+ INR {float(item.overtime_pay):,.2f}"),
        ("Present / Half / Absent days", f"{float(item.present_days):g} / {float(item.half_days):g} / {float(item.absent_days):g}"),
        ("Paid / Unpaid Leave", f"{float(item.paid_leave_days):g} / {float(item.unpaid_leave_days):g}"),
        ("Overtime", f"{item.overtime_minutes} minutes"),
        ("NET PAYABLE", f"INR {float(item.net_pay):,.2f}"),
    ]
    y = 765
    for label, value in lines:
        if label == "NET PAYABLE":
            y -= 6
            pdf.line(48, y + 12, 545, y + 12)
            pdf.setFont("Helvetica-Bold", 12)
        else:
            pdf.setFont("Helvetica", 10)
        pdf.drawString(55, y, label)
        pdf.drawRightString(535, y, value)
        y -= 26
    pdf.setFont("Helvetica-Oblique", 8)
    pdf.drawString(48, 35, "System-generated salary slip. Verify payroll values with your HR/payroll administrator.")
    pdf.save()
    buffer.seek(0)
    log_audit(
        db,
        user.username,
        "DOWNLOAD",
        "hr_salary_slip",
        f"{year}-{month:02d}:{item.employee_code}",
    )
    db.commit()
    filename = f"salary-slip-{item.employee_code}-{year}-{month:02d}.pdf"
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
