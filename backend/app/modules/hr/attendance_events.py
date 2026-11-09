"""Raw attendance event ingestion helpers.

Raw events are append-only source facts. Payroll continues to consume the
separate employee_attendance daily summary until the later projection slice.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from typing import Any
from zoneinfo import ZoneInfo

from openpyxl import Workbook, load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy.orm import Session
from zipfile import BadZipFile

from app.modules.hr.models import Employee
from app.modules.hr.payroll import (
    HRAttendanceEvent,
    HRShiftBreakRule,
    HRShiftRosterEntry,
)
from app.modules.hr.shift_assignment import (
    ShiftAssignmentConfigurationError,
    localize_attendance_datetime,
    resolve_employee_work_context,
)


EVENT_TYPES = {"punch_in", "punch_out", "break_start", "break_end"}
EVENT_WORKBOOK_HEADERS = [
    "Employee Code", "Work Date", "Event Type", "Event DateTime (Local)",
    "Source Reference", "Break Code", "Note",
]
MAX_EVENT_IMPORT_ROWS = 5000


class AttendanceEventError(ValueError):
    """Raised when an attendance event or its source identity is invalid."""


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def build_event_source_reference(*parts: Any) -> str:
    """Build a deterministic, bounded idempotency reference from source identity."""
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def append_attendance_event(
    db: Session,
    *,
    employee_id: str,
    work_date: date,
    event_type: str,
    occurred_at_utc: datetime,
    timezone_name: str,
    source_type: str,
    source_reference: str,
    recorded_by: str,
    import_batch_id: str | None = None,
    roster_entry_id: str | None = None,
    break_rule_id: str | None = None,
    note: str = "",
) -> tuple[HRAttendanceEvent, bool]:
    """Append an event or return the identical event for an idempotent retry."""
    normalized_type = (event_type or "").strip().lower()
    normalized_source = (source_type or "").strip().lower()
    reference = (source_reference or "").strip()
    if normalized_type not in EVENT_TYPES:
        raise AttendanceEventError("Unsupported attendance event type")
    if normalized_source not in {"manual_hr", "excel_import", "employee"}:
        raise AttendanceEventError("Unsupported attendance event source")
    if not reference or len(reference) > 160:
        raise AttendanceEventError("A source reference of 1 to 160 characters is required")
    instant = _utc(occurred_at_utc)
    existing = db.query(HRAttendanceEvent).filter_by(
        source_type=normalized_source,
        source_reference=reference,
    ).first()
    if existing is not None:
        same_event = (
            existing.employee_id == employee_id
            and existing.work_date == work_date
            and existing.event_type == normalized_type
            and _utc(existing.occurred_at_utc) == instant
            and existing.timezone_name == timezone_name
            and existing.break_rule_id == break_rule_id
            and (existing.note or "") == (note or "")
        )
        if not same_event:
            raise AttendanceEventError("This source reference has already been used for a different attendance event")
        return existing, False

    event = HRAttendanceEvent(
        employee_id=employee_id,
        work_date=work_date,
        event_type=normalized_type,
        occurred_at_utc=instant,
        timezone_name=timezone_name,
        source_type=normalized_source,
        source_reference=reference,
        recorded_by=recorded_by[:64],
        import_batch_id=import_batch_id,
        roster_entry_id=roster_entry_id,
        break_rule_id=break_rule_id,
        note=note or "",
    )
    db.add(event)
    db.flush()
    return event, True


def _parse_work_date(value: Any) -> date:
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
                pass
    raise ValueError("Work Date must be an Excel date or YYYY-MM-DD")


def _parse_local_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError as exc:
            raise ValueError("Event DateTime (Local) must be a valid local datetime") from exc
    else:
        raise ValueError("Event DateTime (Local) is required and must include a date and time")
    if parsed.tzinfo is not None:
        raise ValueError("Event DateTime (Local) must be timezone-naive; the batch timezone is authoritative")
    return parsed


def attendance_event_template_workbook() -> BytesIO:
    """Build the v2 one-row-per-event workbook with optional provenance columns."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Attendance"
    sheet.append(EVENT_WORKBOOK_HEADERS)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{chr(64 + len(EVENT_WORKBOOK_HEADERS))}1"
    widths = [20, 16, 18, 28, 42, 18, 32]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[chr(64 + index)].width = width

    instructions = workbook.create_sheet("Instructions")
    instruction_rows = [
        ["Nexora Attendance Event Workbook v2"],
        ["One row represents one raw attendance event. Do not enter daily summary status in this workbook."],
        ["Required columns: Employee Code, Work Date, Event Type, Event DateTime (Local)."],
        ["Optional columns: Source Reference, Break Code, Note. Optional columns may be left blank or omitted."],
        ["Event Type must be punch_in, punch_out, break_start or break_end."],
        ["Event DateTime (Local) is interpreted using the single timezone selected for the entire import batch."],
        ["Use a full local date and time for every event; overnight events may fall on the calendar day after Work Date."],
        ["Work Date is the local shift-start date, not necessarily the calendar date of every event."],
        ["If Source Reference is blank, the importer creates a stable file/row identity for retry idempotency."],
        ["Break Code must match an active break rule on the employee's assigned shift."],
        ["Every row is validated before any event is written. One invalid row rejects the whole batch."],
        ["The legacy seven-column daily-summary workbook remains available through the legacy attendance import."],
    ]
    for row in instruction_rows:
        instructions.append(row)
    instructions.column_dimensions["A"].width = 120
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    output.seek(0)
    return output


def parse_event_workbook(
    content: bytes,
    *,
    db: Session,
    employees_by_code: dict[str, Employee],
    import_timezone: str,
    branch_id: str | None,
    file_hash: str,
) -> list[dict[str, Any]]:
    """Validate a complete v2 event workbook before any attendance writes."""
    try:
        workbook = load_workbook(__import__("io").BytesIO(content), data_only=True, read_only=True)
    except (InvalidFileException, BadZipFile, OSError, ValueError) as exc:
        raise AttendanceEventError("The file is not a readable Excel .xlsx workbook") from exc
    try:
        if "Attendance" not in workbook.sheetnames:
            raise AttendanceEventError('Workbook must contain a worksheet named "Attendance"')
        sheet = workbook["Attendance"]
        first_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
        headers = [str(value).strip() if value is not None else "" for value in (first_row or ())]
        while headers and not headers[-1]:
            headers.pop()
        required_headers = EVENT_WORKBOOK_HEADERS[:4]
        optional_headers = set(EVENT_WORKBOOK_HEADERS[4:])
        if (
            headers[:4] != required_headers
            or len(headers) != len(set(headers))
            or any(header not in optional_headers for header in headers[4:])
        ):
            raise AttendanceEventError(
                "Event workbook must start with required headers "
                + ", ".join(required_headers)
                + "; optional headers are Source Reference, Break Code and Note"
            )
        header_index = {header: index for index, header in enumerate(headers)}

        parsed: list[dict[str, Any]] = []
        errors: list[str] = []
        seen_references: set[str] = set()
        row_count = 0
        for row_number, values in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            cells = list(values[:len(headers)])
            cells.extend([None] * (len(headers) - len(cells)))
            if not any(value is not None and (not isinstance(value, str) or value.strip()) for value in cells):
                continue
            row_count += 1
            if row_count > MAX_EVENT_IMPORT_ROWS:
                errors.append(f"More than {MAX_EVENT_IMPORT_ROWS} attendance events were supplied")
                break
            row_error_start = len(errors)

            def cell(header: str):
                index = header_index.get(header)
                return cells[index] if index is not None else None

            raw_code = cell("Employee Code")
            raw_work_date = cell("Work Date")
            raw_type = cell("Event Type")
            raw_datetime = cell("Event DateTime (Local)")
            raw_reference = cell("Source Reference")
            raw_break_code = cell("Break Code")
            raw_note = cell("Note")
            code = str(raw_code).strip().upper() if raw_code is not None else ""
            employee = employees_by_code.get(code)
            if not code:
                errors.append(f"Row {row_number}: Employee Code is required")
            elif employee is None:
                errors.append(f"Row {row_number}: employee code {code!r} was not found or is inactive")

            work_date = None
            try:
                work_date = _parse_work_date(raw_work_date)
            except ValueError as exc:
                errors.append(f"Row {row_number}: {exc}")
            event_type = str(raw_type or "").strip().lower()
            if event_type not in EVENT_TYPES:
                errors.append(f"Row {row_number}: Event Type must be one of {', '.join(sorted(EVENT_TYPES))}")

            local_datetime = None
            try:
                local_datetime = _parse_local_datetime(raw_datetime)
            except ValueError as exc:
                errors.append(f"Row {row_number}: {exc}")
            note = str(raw_note or "").strip()
            if len(note) > 1000:
                errors.append(f"Row {row_number}: Note must be 1000 characters or fewer")

            if employee is None or work_date is None or local_datetime is None or event_type not in EVENT_TYPES:
                continue
            try:
                context = resolve_employee_work_context(
                    db, employee.id, work_date, timezone_override=import_timezone,
                )
            except ShiftAssignmentConfigurationError as exc:
                errors.append(f"Row {row_number}: {exc}")
                continue
            if branch_id is not None and context.branch_id != branch_id:
                errors.append(f"Row {row_number}: employee {code} is not assigned to the selected branch on {work_date}")
            if branch_id is None and context.branch_id is not None:
                errors.append(f"Row {row_number}: employee {code} is assigned to branch {context.branch_id}; select that branch")

            roster = db.query(HRShiftRosterEntry).filter_by(
                employee_id=employee.id, work_date=work_date,
            ).first()
            allowed_local_dates = {work_date}
            if roster is not None and roster.scheduled_start_at_utc and roster.scheduled_end_at_utc:
                local_end = _utc(roster.scheduled_end_at_utc).astimezone(ZoneInfo(context.timezone_name))
                local_start = _utc(roster.scheduled_start_at_utc).astimezone(ZoneInfo(context.timezone_name))
                if local_end.date() > local_start.date():
                    allowed_local_dates.add(work_date + timedelta(days=1))
            if local_datetime.date() not in allowed_local_dates:
                errors.append(
                    f"Row {row_number}: event local date {local_datetime.date()} does not belong to work date {work_date}"
                )

            break_rule = None
            break_code = str(raw_break_code or "").strip()
            if break_code:
                if roster is None or not roster.shift_type_id:
                    errors.append(f"Row {row_number}: Break Code requires a scheduled shift roster")
                else:
                    break_rule = db.query(HRShiftBreakRule).filter_by(
                        shift_type_id=roster.shift_type_id,
                        code=break_code,
                        active=True,
                    ).first()
                    if break_rule is None:
                        errors.append(f"Row {row_number}: Break Code {break_code!r} is not active for the assigned shift")

            try:
                occurred_at_utc = localize_attendance_datetime(local_datetime, context.timezone_name)
            except ShiftAssignmentConfigurationError as exc:
                errors.append(f"Row {row_number}: {exc}")
                continue

            supplied_reference = str(raw_reference or "").strip()
            reference = supplied_reference or build_event_source_reference(
                "excel_event_v2", file_hash, row_number, code, work_date, event_type,
            )
            if len(reference) > 160:
                errors.append(f"Row {row_number}: Source Reference must be 160 characters or fewer")
            if reference in seen_references:
                errors.append(f"Row {row_number}: duplicate Source Reference {reference!r}")
            seen_references.add(reference)

            if len(errors) == row_error_start:
                parsed.append({
                    "employee_id": employee.id,
                    "employee_code": code,
                    "work_date": work_date,
                    "event_type": event_type,
                    "occurred_at_utc": occurred_at_utc,
                    "timezone_name": context.timezone_name,
                    "roster_entry_id": roster.id if roster else None,
                    "break_rule_id": break_rule.id if break_rule else None,
                    "source_reference": reference,
                    "note": note,
                })

        if row_count == 0:
            errors.append("Attendance worksheet has no event rows")
        if errors:
            shown = errors[:30]
            suffix = f"\n…and {len(errors) - len(shown)} additional issue(s)." if len(errors) > len(shown) else ""
            raise AttendanceEventError("Attendance event import validation failed:\n" + "\n".join(shown) + suffix)
        return parsed
    finally:
        workbook.close()
