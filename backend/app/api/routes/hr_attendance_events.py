"""Authorized raw attendance event and import-batch APIs."""
from __future__ import annotations

import hashlib
import io
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.api.deps import employee_scope_ids, require_permission
from app.db.session import get_db
from app.modules.core.audit import log_audit
from app.modules.hr.attendance_events import (
    AttendanceEventError,
    append_attendance_event,
    attendance_event_template_workbook,
    build_event_source_reference,
    parse_event_workbook,
)
from app.modules.hr.shift_assignment import (
    ShiftAssignmentConfigurationError,
    localize_attendance_datetime,
    resolve_employee_work_context,
)

router = APIRouter(prefix="/hr/attendance", tags=["hr", "attendance-events"])
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class AttendanceEventCreate(BaseModel):
    employee_id: str = Field(min_length=1, max_length=36)
    work_date: date
    event_type: Literal["punch_in", "punch_out", "break_start", "break_end"]
    occurred_at: datetime
    source_reference: str = Field(min_length=1, max_length=160)
    break_code: str | None = Field(default=None, max_length=32)
    note: str = Field(default="", max_length=1000)


class EmployeeSelfPunchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_date: date
    event_type: Literal["punch_in", "punch_out", "break_start", "break_end"]
    occurred_at: datetime
    source_reference: str = Field(min_length=1, max_length=160)
    break_code: str | None = Field(default=None, max_length=32)
    note: str = Field(default="", max_length=1000)


def _period_is_frozen(db: Session, work_date: date) -> bool:
    return db.query(models.HRPayrollRun).filter(
        models.HRPayrollRun.year == work_date.year,
        models.HRPayrollRun.month == work_date.month,
        models.HRPayrollRun.status.in_(["prepared", "approved", "finalized", "locked"]),
    ).first() is not None


def _event_output(event: models.HRAttendanceEvent) -> dict:
    return {
        "id": event.id,
        "employee_id": event.employee_id,
        "work_date": event.work_date,
        "roster_entry_id": event.roster_entry_id,
        "event_type": event.event_type,
        "occurred_at_utc": event.occurred_at_utc,
        "timezone_name": event.timezone_name,
        "source_type": event.source_type,
        "source_reference": event.source_reference,
        "import_batch_id": event.import_batch_id,
        "break_rule_id": event.break_rule_id,
        "recorded_by": event.recorded_by,
        "created_at": event.created_at,
    }


def _local_event_context(
    db: Session,
    employee_id: str,
    work_date: date,
    occurred_at: datetime,
    break_code: str | None,
):
    context = resolve_employee_work_context(db, employee_id, work_date)
    zone = ZoneInfo(context.timezone_name)
    local_value = occurred_at.astimezone(zone).replace(tzinfo=None) if occurred_at.tzinfo else occurred_at
    roster = db.query(models.HRShiftRosterEntry).filter_by(
        employee_id=employee_id, work_date=work_date,
    ).first()
    allowed_dates = {work_date}
    if roster and roster.scheduled_start_at_utc and roster.scheduled_end_at_utc:
        local_start = roster.scheduled_start_at_utc.replace(tzinfo=timezone.utc).astimezone(zone)
        local_end = roster.scheduled_end_at_utc.replace(tzinfo=timezone.utc).astimezone(zone)
        if local_end.date() > local_start.date():
            allowed_dates.add(work_date + timedelta(days=1))
    if local_value.date() not in allowed_dates:
        raise AttendanceEventError(
            f"Event local date {local_value.date()} does not belong to work date {work_date}"
        )
    try:
        occurred_at_utc = localize_attendance_datetime(occurred_at, context.timezone_name)
    except ShiftAssignmentConfigurationError as exc:
        raise AttendanceEventError(str(exc)) from exc

    break_rule_id = None
    if break_code:
        if roster is None or not roster.shift_type_id:
            raise AttendanceEventError("Break Code requires a scheduled shift roster")
        rule = db.query(models.HRShiftBreakRule).filter_by(
            shift_type_id=roster.shift_type_id, code=break_code, active=True,
        ).first()
        if rule is None:
            raise AttendanceEventError("Break Code is not active for the assigned shift")
        break_rule_id = rule.id
    return context, roster, occurred_at_utc, break_rule_id


def _record_rejected_batch(
    db: Session,
    *,
    user: models.User,
    file_name: str,
    file_hash: str,
    branch_id: str | None,
    import_timezone: str,
    error: str,
    rows_total: int = 0,
) -> models.HRAttendanceImportBatch:
    batch = models.HRAttendanceImportBatch(
        branch_id=branch_id,
        import_timezone=import_timezone,
        template_version="event_v2",
        file_name=file_name[:255],
        file_hash=file_hash,
        uploaded_by=user.username[:64],
        status="rejected",
        rows_total=rows_total,
        rows_imported=0,
        rows_rejected=max(1, rows_total),
        error_summary=error[:4000],
    )
    db.add(batch)
    db.flush()
    log_audit(db, user.username, "REJECT", "hr_attendance_import_batch", f"{batch.id}: {error[:500]}")
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/events")
def list_attendance_events(
    employee_id: str | None = Query(default=None, max_length=36),
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission("hr", "attendance", "view", "tenant")),
):
    query = db.query(models.HRAttendanceEvent)
    if employee_id:
        query = query.filter(models.HRAttendanceEvent.employee_id == employee_id)
    if from_date:
        query = query.filter(models.HRAttendanceEvent.work_date >= from_date)
    if to_date:
        query = query.filter(models.HRAttendanceEvent.work_date <= to_date)
    rows = query.order_by(
        models.HRAttendanceEvent.work_date.desc(),
        models.HRAttendanceEvent.occurred_at_utc.desc(),
    ).limit(limit).all()

    scope_cache: dict[date, set[str] | None] = {}
    visible = []
    for row in rows:
        if row.work_date not in scope_cache:
            scoped = employee_scope_ids(
                db, user, "hr", "employees", "read", as_of_date=row.work_date,
            )
            scope_cache[row.work_date] = None if scoped is None else set(scoped)
        allowed = scope_cache[row.work_date]
        if allowed is None or row.employee_id in allowed:
            visible.append(_event_output(row))
    if employee_id and not visible and rows:
        raise HTTPException(status_code=403, detail="Employee is outside your configured attendance access scope")
    return visible


@router.post("/events")
def create_manual_attendance_event(
    payload: AttendanceEventCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission("hr", "attendance", "event_create", "tenant")),
):
    employee = db.get(models.Employee, payload.employee_id)
    if employee is None or not employee.active:
        raise HTTPException(status_code=404, detail="Active employee not found")
    if _period_is_frozen(db, payload.work_date):
        raise HTTPException(status_code=409, detail="Attendance cannot be changed while the payroll period is prepared or finalized")
    scoped = employee_scope_ids(db, user, "hr", "employees", "update", as_of_date=payload.work_date)
    if scoped is not None and employee.id not in scoped:
        raise HTTPException(status_code=403, detail="Employee is outside your configured attendance access scope")
    try:
        context, roster, instant, break_rule_id = _local_event_context(
            db, employee.id, payload.work_date, payload.occurred_at, payload.break_code,
        )
        event, created = append_attendance_event(
            db,
            employee_id=employee.id,
            work_date=payload.work_date,
            event_type=payload.event_type,
            occurred_at_utc=instant,
            timezone_name=context.timezone_name,
            source_type="manual_hr",
            source_reference=payload.source_reference,
            recorded_by=user.username,
            roster_entry_id=roster.id if roster else None,
            break_rule_id=break_rule_id,
            note=payload.note,
        )
        if created:
            log_audit(db, user.username, "CREATE", "hr_attendance_event", f"{event.id}:{event.event_type}:{event.employee_id}:{event.work_date}")
        db.commit()
        db.refresh(event)
        return {**_event_output(event), "created": created}
    except (AttendanceEventError, ShiftAssignmentConfigurationError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Attendance event source reference was submitted concurrently") from exc


@router.post("/self-punch")
def create_employee_self_punch(
    payload: EmployeeSelfPunchCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission("hr", "attendance", "event_create", "own")),
):
    link = db.query(models.EmployeeUserLink).filter_by(user_id=user.id).first()
    if link is None:
        raise HTTPException(status_code=403, detail="This login is not linked to an employee record")
    employee = db.get(models.Employee, link.employee_id)
    if employee is None or not employee.active:
        raise HTTPException(status_code=403, detail="An active linked employee record is required")
    if _period_is_frozen(db, payload.work_date):
        raise HTTPException(status_code=409, detail="Attendance cannot be changed while the payroll period is prepared or finalized")
    try:
        context, roster, instant, break_rule_id = _local_event_context(
            db, employee.id, payload.work_date, payload.occurred_at, payload.break_code,
        )
        event, created = append_attendance_event(
            db,
            employee_id=employee.id,
            work_date=payload.work_date,
            event_type=payload.event_type,
            occurred_at_utc=instant,
            timezone_name=context.timezone_name,
            source_type="employee",
            source_reference=payload.source_reference,
            recorded_by=user.username,
            roster_entry_id=roster.id if roster else None,
            break_rule_id=break_rule_id,
            note=payload.note,
        )
        if created:
            log_audit(db, user.username, "CREATE", "hr_attendance_event", f"{event.id}:{event.event_type}:self:{event.work_date}")
        db.commit()
        db.refresh(event)
        return {**_event_output(event), "created": created}
    except (AttendanceEventError, ShiftAssignmentConfigurationError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Attendance event source reference was submitted concurrently") from exc


@router.get("/event-template")
def download_attendance_event_template(
    user: models.User = Depends(require_permission("hr", "attendance", "import", "tenant")),
):
    workbook = attendance_event_template_workbook()
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="nexora-attendance-event-template-v2.xlsx"'},
    )


@router.post("/import-events")
async def import_attendance_event_workbook(
    branch_id: str | None = Query(default=None, min_length=1, max_length=36),
    import_timezone: str | None = Query(default=None, min_length=1, max_length=64),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission("hr", "attendance", "import", "tenant")),
):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=415, detail="Upload an .xlsx event workbook using the Attendance Event v2 template")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Attendance workbook must be 5 MB or smaller")
    file_hash = hashlib.sha256(content).hexdigest()
    file_name = Path(file.filename).name[:255]

    settings = db.get(models.HRPayrollSettings, 1)
    selected_branch = None
    if branch_id:
        selected_branch = db.get(models.HRBranch, branch_id)
        if selected_branch is None or not selected_branch.active:
            raise HTTPException(status_code=422, detail="Select an active branch for this attendance import")
    default_timezone = (
        (selected_branch.timezone or "").strip() if selected_branch else ""
    ) or ((settings.timezone if settings else None) or "Asia/Kolkata")
    selected_timezone = import_timezone or default_timezone
    try:
        ZoneInfo(selected_timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail="Import timezone must be a valid IANA timezone identifier") from exc

    employees_by_code = {
        row.emp_code.strip().upper(): row
        for row in db.query(models.Employee).filter(models.Employee.active.is_(True)).all()
    }
    try:
        rows = parse_event_workbook(
            content,
            db=db,
            employees_by_code=employees_by_code,
            import_timezone=selected_timezone,
            branch_id=branch_id,
            file_hash=file_hash,
        )
    except AttendanceEventError as exc:
        _record_rejected_batch(
            db, user=user, file_name=file_name, file_hash=file_hash,
            branch_id=branch_id, import_timezone=selected_timezone, error=str(exc),
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    scope_cache: dict[date, set[str] | None] = {}
    for row in rows:
        if _period_is_frozen(db, row["work_date"]):
            error = f"Payroll period is frozen for {row['work_date']}"
            _record_rejected_batch(
                db, user=user, file_name=file_name, file_hash=file_hash,
                branch_id=branch_id, import_timezone=selected_timezone, error=error,
                rows_total=len(rows),
            )
            raise HTTPException(status_code=409, detail=error)
        work_date = row["work_date"]
        if work_date not in scope_cache:
            scoped = employee_scope_ids(
                db, user, "hr", "employees", "update", as_of_date=work_date,
            )
            scope_cache[work_date] = None if scoped is None else set(scoped)
        allowed = scope_cache[work_date]
        if allowed is not None and row["employee_id"] not in allowed:
            error = f"Attendance import includes an employee outside your access scope on {work_date}"
            _record_rejected_batch(
                db, user=user, file_name=file_name, file_hash=file_hash,
                branch_id=branch_id, import_timezone=selected_timezone, error=error,
                rows_total=len(rows),
            )
            raise HTTPException(status_code=403, detail=error)

    batch = models.HRAttendanceImportBatch(
        branch_id=branch_id,
        import_timezone=selected_timezone,
        template_version="event_v2",
        file_name=file_name,
        file_hash=file_hash,
        uploaded_by=user.username[:64],
        status="validated",
        rows_total=len(rows),
        rows_imported=0,
        rows_rejected=0,
        error_summary="",
    )
    db.add(batch)
    log_audit(db, user.username, "VALIDATE", "hr_attendance_import_batch", f"event_v2:{file_hash}:{len(rows)} rows")
    db.commit()
    db.refresh(batch)

    try:
        created_count = 0
        for row in rows:
            _, created = append_attendance_event(
                db,
                employee_id=row["employee_id"],
                work_date=row["work_date"],
                event_type=row["event_type"],
                occurred_at_utc=row["occurred_at_utc"],
                timezone_name=row["timezone_name"],
                source_type="excel_import",
                source_reference=row["source_reference"],
                recorded_by=user.username,
                import_batch_id=batch.id,
                roster_entry_id=row["roster_entry_id"],
                break_rule_id=row["break_rule_id"],
                note=row["note"],
            )
            created_count += int(created)
        batch.status = "imported"
        batch.rows_imported = len(rows)
        batch.rows_rejected = 0
        log_audit(db, user.username, "IMPORT", "hr_attendance_import_batch", f"{batch.id}: rows={len(rows)}; new_events={created_count}")
        db.commit()
    except (AttendanceEventError, IntegrityError) as exc:
        db.rollback()
        persisted = db.get(models.HRAttendanceImportBatch, batch.id)
        if persisted is not None:
            persisted.status = "rejected"
            persisted.rows_rejected = len(rows)
            persisted.error_summary = str(exc)[:4000]
            log_audit(db, user.username, "REJECT", "hr_attendance_import_batch", f"{batch.id}: {str(exc)[:500]}")
            db.commit()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    db.refresh(batch)
    return {
        "batch_id": batch.id,
        "status": batch.status,
        "branch_id": batch.branch_id,
        "import_timezone": batch.import_timezone,
        "template_version": batch.template_version,
        "file_hash": batch.file_hash,
        "rows_total": batch.rows_total,
        "rows_imported": batch.rows_imported,
        "rows_rejected": batch.rows_rejected,
    }


@router.get("/import-batches")
def list_attendance_import_batches(
    status: Literal["validated", "imported", "rejected"] | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission("hr", "attendance", "view", "tenant")),
):
    query = db.query(models.HRAttendanceImportBatch)
    if status:
        query = query.filter(models.HRAttendanceImportBatch.status == status)
    rows = query.order_by(models.HRAttendanceImportBatch.uploaded_at.desc()).limit(limit).all()
    return [{
        "id": row.id,
        "branch_id": row.branch_id,
        "import_timezone": row.import_timezone,
        "template_version": row.template_version,
        "file_name": row.file_name,
        "file_hash": row.file_hash,
        "uploaded_by": row.uploaded_by,
        "uploaded_at": row.uploaded_at,
        "status": row.status,
        "rows_total": row.rows_total,
        "rows_imported": row.rows_imported,
        "rows_rejected": row.rows_rejected,
        "error_summary": row.error_summary,
    } for row in rows]
