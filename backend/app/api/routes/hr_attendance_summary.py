"""Daily attendance summary projection and correction workflow APIs (P0.1-08)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.api.deps import current_user, employee_scope_ids, require_permission
from app.db.session import get_db
from app.modules.core.audit import log_audit
from app.modules.hr.attendance_events import AttendanceEventError, append_attendance_event
from app.modules.hr.attendance_summary import recalculate_attendance_summary, summary_output
from app.api.routes.hr_attendance_events import _local_event_context

router = APIRouter(prefix="/hr/attendance", tags=["hr", "attendance-summary-corrections"])


def _payroll_frozen(db: Session, work_date: date) -> bool:
    return db.query(models.HRPayrollRun).filter(
        models.HRPayrollRun.year == work_date.year,
        models.HRPayrollRun.month == work_date.month,
        models.HRPayrollRun.status.in_(["prepared", "approved", "finalized", "locked"]),
    ).first() is not None


def _summary_scope(db: Session, user: models.User, work_date: date, action: str = "view") -> set[str] | None:
    ids = employee_scope_ids(db, user, "hr", "attendance_summaries", action, as_of_date=work_date)
    return None if ids is None else set(ids)


def _correction_scope(db: Session, user: models.User, work_date: date, action: str) -> set[str] | None:
    ids = employee_scope_ids(db, user, "hr", "attendance_corrections", action, as_of_date=work_date)
    return None if ids is None else set(ids)


def _correction_output(row: models.HRAttendanceCorrectionRequest) -> dict:
    return {
        "id": row.id,
        "employee_id": row.employee_id,
        "work_date": row.work_date,
        "correction_kind": row.correction_kind,
        "target_event_id": row.target_event_id,
        "proposed_event_type": row.proposed_event_type,
        "proposed_at_utc": row.proposed_at_utc,
        "timezone_name": row.timezone_name,
        "break_rule_id": row.break_rule_id,
        "reason": row.reason,
        "evidence_reference": row.evidence_reference,
        "status": row.status,
        "requested_by": row.requested_by,
        "requested_at": row.requested_at,
        "reviewer": row.reviewer,
        "reviewed_at": row.reviewed_at,
        "decision_reason": row.decision_reason,
        "applied_event_id": row.applied_event_id,
    }


class SummaryRecalculate(BaseModel):
    employee_id: str = Field(min_length=1, max_length=36)
    work_date: date


class CorrectionCreate(BaseModel):
    employee_id: str | None = Field(default=None, max_length=36)
    work_date: date
    correction_kind: Literal["add", "replace"]
    target_event_id: str | None = Field(default=None, max_length=36)
    proposed_event_type: Literal["punch_in", "punch_out", "break_start", "break_end"]
    occurred_at: datetime
    break_code: str | None = Field(default=None, max_length=32)
    reason: str = Field(min_length=3, max_length=1000)
    evidence_reference: str = Field(default="", max_length=500)


class CorrectionResubmit(BaseModel):
    correction_kind: Literal["add", "replace"]
    target_event_id: str | None = Field(default=None, max_length=36)
    proposed_event_type: Literal["punch_in", "punch_out", "break_start", "break_end"]
    occurred_at: datetime
    break_code: str | None = Field(default=None, max_length=32)
    reason: str = Field(min_length=3, max_length=1000)
    evidence_reference: str = Field(default="", max_length=500)


class CorrectionReview(BaseModel):
    decision: Literal["approve", "reject", "return"]
    reason: str = Field(min_length=3, max_length=1000)


def _validate_target(db: Session, employee_id: str, work_date: date, kind: str, target_id: str | None):
    if kind == "add":
        if target_id:
            raise HTTPException(status_code=422, detail="Add correction must not reference a target event")
        return None
    if not target_id:
        raise HTTPException(status_code=422, detail="Replace correction requires a target event")
    target = db.get(models.HRAttendanceEvent, target_id)
    if target is None or target.employee_id != employee_id or target.work_date != work_date:
        raise HTTPException(status_code=422, detail="Correction target must belong to the same employee and work date")
    if target.voided_at is not None or db.query(models.HRAttendanceEvent.id).filter_by(supersedes_event_id=target.id).first():
        raise HTTPException(status_code=409, detail="Correction target is no longer an active source event")
    return target


def _create_correction_request(
    db: Session, *, employee_id: str, payload: CorrectionCreate, user: models.User,
) -> models.HRAttendanceCorrectionRequest:
    if _payroll_frozen(db, payload.work_date):
        raise HTTPException(status_code=409, detail="Attendance correction is blocked for prepared, approved, finalized or locked payroll")
    employee = db.get(models.Employee, employee_id)
    if employee is None or not employee.active:
        raise HTTPException(status_code=404, detail="Active employee not found")
    target = _validate_target(db, employee_id, payload.work_date, payload.correction_kind, payload.target_event_id)
    if payload.break_code and payload.proposed_event_type not in {"break_start", "break_end"}:
        raise HTTPException(status_code=422, detail="Break Code is only valid for break events")
    try:
        context, roster, instant, break_rule_id = _local_event_context(
            db, employee_id, payload.work_date, payload.occurred_at, payload.break_code,
        )
    except (AttendanceEventError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = models.HRAttendanceCorrectionRequest(
        employee_id=employee_id,
        work_date=payload.work_date,
        correction_kind=payload.correction_kind,
        target_event_id=target.id if target else None,
        proposed_event_type=payload.proposed_event_type,
        proposed_at_utc=instant,
        timezone_name=context.timezone_name,
        break_rule_id=break_rule_id,
        reason=payload.reason.strip(),
        evidence_reference=payload.evidence_reference.strip(),
        status="submitted",
        requested_by=user.username[:64],
    )
    db.add(row)
    db.flush()
    log_audit(
        db, user.username, "SUBMIT", "hr_attendance_correction_request",
        f"{row.id}: employee={employee_id}; date={payload.work_date}; kind={payload.correction_kind}; reason={payload.reason.strip()[:300]}",
    )
    return row


@router.get("/summaries")
def list_daily_attendance_summaries(
    from_date: date | None = None,
    to_date: date | None = None,
    employee_id: str | None = Query(default=None, max_length=36),
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission("hr", "attendance_summaries", "view", "tenant")),
):
    if from_date and to_date and to_date < from_date:
        raise HTTPException(status_code=422, detail="to_date cannot be earlier than from_date")
    if from_date and to_date and (to_date - from_date).days + 1 > 31:
        raise HTTPException(status_code=422, detail="Attendance summary query cannot exceed 31 calendar days")
    query = db.query(models.HRAttendanceDailySummary)
    if from_date:
        query = query.filter(models.HRAttendanceDailySummary.work_date >= from_date)
    if to_date:
        query = query.filter(models.HRAttendanceDailySummary.work_date <= to_date)
    if employee_id:
        query = query.filter(models.HRAttendanceDailySummary.employee_id == employee_id)

    ordered = query.order_by(
        models.HRAttendanceDailySummary.work_date.desc(),
        models.HRAttendanceDailySummary.employee_id.asc(),
        models.HRAttendanceDailySummary.id.asc(),
    )
    visible = []
    skipped = 0
    for row in ordered.yield_per(250):
        scope = _summary_scope(db, user, row.work_date)
        if scope is not None and row.employee_id not in scope:
            continue
        if skipped < offset:
            skipped += 1
            continue
        revision = db.query(models.HRAttendanceSummaryRevision).filter_by(
            employee_id=row.employee_id, work_date=row.work_date, revision=row.current_revision,
        ).first()
        visible.append(summary_output(row, revision))
        if len(visible) >= limit:
            break
    return visible


@router.get("/summaries/self")
def list_self_attendance_summaries(
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission("hr", "attendance_summaries", "view", "self")),
):
    link = db.query(models.EmployeeUserLink).filter_by(user_id=user.id).first()
    if link is None:
        raise HTTPException(status_code=403, detail="This login is not linked to an employee record")
    query = db.query(models.HRAttendanceDailySummary).filter_by(employee_id=link.employee_id)
    if from_date:
        query = query.filter(models.HRAttendanceDailySummary.work_date >= from_date)
    if to_date:
        query = query.filter(models.HRAttendanceDailySummary.work_date <= to_date)
    rows = query.order_by(models.HRAttendanceDailySummary.work_date.desc()).limit(limit).all()
    return [
        summary_output(row, db.query(models.HRAttendanceSummaryRevision).filter_by(
            employee_id=row.employee_id, work_date=row.work_date, revision=row.current_revision,
        ).first())
        for row in rows
    ]


@router.post("/summaries/recalculate")
def recalculate_daily_attendance_summary(
    payload: SummaryRecalculate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission("hr", "attendance_summaries", "calculate", "tenant")),
):
    employee = db.get(models.Employee, payload.employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    scope = _summary_scope(db, user, payload.work_date, action="calculate")
    if scope is not None and employee.id not in scope:
        raise HTTPException(status_code=403, detail="Employee is outside your summary calculation scope")
    if _payroll_frozen(db, payload.work_date):
        raise HTTPException(status_code=409, detail="Summary recalculation is blocked while payroll is prepared, approved, finalized or locked")
    summary, revision, created = recalculate_attendance_summary(
        db, employee.id, payload.work_date, calculated_by=user.username,
    )
    log_audit(
        db, user.username, "RECALCULATE", "hr_attendance_daily_summary",
        f"{employee.emp_code}:{payload.work_date}; revision={summary.current_revision}; created={created}",
    )
    db.commit()
    db.refresh(summary)
    return {**summary_output(summary, revision), "revision_created": created}


@router.get("/summaries/{employee_id}/{work_date}")
def get_daily_attendance_summary(
    employee_id: str,
    work_date: date,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission("hr", "attendance_summaries", "view", "tenant")),
):
    summary = db.query(models.HRAttendanceDailySummary).filter_by(
        employee_id=employee_id, work_date=work_date,
    ).first()
    if summary is None:
        return None
    scope = _summary_scope(db, user, work_date)
    if scope is not None and employee_id not in scope:
        raise HTTPException(status_code=403, detail="Employee is outside your attendance summary access scope")
    revision = db.query(models.HRAttendanceSummaryRevision).filter_by(
        employee_id=employee_id, work_date=work_date, revision=summary.current_revision,
    ).first()
    return summary_output(summary, revision)


@router.get("/summaries/{employee_id}/{work_date}/revisions")
def list_daily_attendance_summary_revisions(
    employee_id: str,
    work_date: date,
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission("hr", "attendance_summaries", "view", "tenant")),
):
    scope = _summary_scope(db, user, work_date)
    if scope is not None and employee_id not in scope:
        raise HTTPException(status_code=403, detail="Employee is outside your attendance summary access scope")
    rows = db.query(models.HRAttendanceSummaryRevision).filter_by(
        employee_id=employee_id, work_date=work_date,
    ).order_by(models.HRAttendanceSummaryRevision.revision.desc()).limit(limit).all()
    return [{
        "id": row.id, "employee_id": row.employee_id, "work_date": row.work_date,
        "revision": row.revision, "classification": row.classification,
        "exception_codes": row.exception_codes, "source_event_ids": row.source_event_ids,
        "roster_entry_id": row.roster_entry_id, "timezone_name": row.timezone_name,
        "first_punch_in_utc": row.first_punch_in_utc, "last_punch_out_utc": row.last_punch_out_utc,
        "elapsed_minutes": row.elapsed_minutes, "paired_break_minutes": row.paired_break_minutes,
        "input_fingerprint": row.input_fingerprint, "calculated_by": row.calculated_by,
        "calculated_at": row.calculated_at,
    } for row in rows]


@router.post("/corrections")
def create_attendance_correction(
    payload: CorrectionCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission("hr", "attendance_corrections", "create", "tenant")),
):
    if not payload.employee_id:
        raise HTTPException(status_code=422, detail="Employee ID is required for HR correction submission")
    scope = _correction_scope(db, user, payload.work_date, "create")
    if scope is not None and payload.employee_id not in scope:
        raise HTTPException(status_code=403, detail="Employee is outside your correction submission scope")
    row = _create_correction_request(db, employee_id=payload.employee_id, payload=payload, user=user)
    db.commit()
    db.refresh(row)
    return _correction_output(row)


@router.post("/corrections/self")
def create_self_attendance_correction(
    payload: CorrectionCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission("hr", "attendance_corrections", "create", "self")),
):
    link = db.query(models.EmployeeUserLink).filter_by(user_id=user.id).first()
    if link is None:
        raise HTTPException(status_code=403, detail="This login is not linked to an employee record")
    if payload.employee_id and payload.employee_id != link.employee_id:
        raise HTTPException(status_code=403, detail="Self-correction submission cannot target another employee")
    scope = _correction_scope(db, user, payload.work_date, "create")
    if scope is not None and link.employee_id not in scope:
        raise HTTPException(status_code=403, detail="Employee self-correction scope is not configured")
    row = _create_correction_request(db, employee_id=link.employee_id, payload=payload, user=user)
    db.commit()
    db.refresh(row)
    return _correction_output(row)


@router.get("/corrections")
def list_attendance_corrections(
    status: str | None = Query(default=None, max_length=20),
    employee_id: str | None = Query(default=None, max_length=36),
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0, le=1000000),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission("hr", "attendance_corrections", "view", "tenant")),
):
    if from_date and to_date and to_date < from_date:
        raise HTTPException(status_code=422, detail="to_date cannot be earlier than from_date")
    if from_date and to_date and (to_date - from_date).days + 1 > 31:
        raise HTTPException(status_code=422, detail="Attendance correction query cannot exceed 31 calendar days")
    query = db.query(models.HRAttendanceCorrectionRequest)
    if status:
        query = query.filter(models.HRAttendanceCorrectionRequest.status == status)
    if employee_id:
        query = query.filter(models.HRAttendanceCorrectionRequest.employee_id == employee_id)
    if from_date:
        query = query.filter(models.HRAttendanceCorrectionRequest.work_date >= from_date)
    if to_date:
        query = query.filter(models.HRAttendanceCorrectionRequest.work_date <= to_date)
    rows = query.order_by(
        models.HRAttendanceCorrectionRequest.requested_at.desc(),
        models.HRAttendanceCorrectionRequest.id.desc(),
    ).all()
    visible = []
    for row in rows:
        scope = _correction_scope(db, user, row.work_date, "view")
        if scope is None or row.employee_id in scope:
            visible.append(_correction_output(row))
    return visible[offset:offset + limit]


@router.get("/corrections/self")
def list_self_attendance_corrections(
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission("hr", "attendance_corrections", "view", "self")),
):
    link = db.query(models.EmployeeUserLink).filter_by(user_id=user.id).first()
    if link is None:
        raise HTTPException(status_code=403, detail="This login is not linked to an employee record")
    rows = db.query(models.HRAttendanceCorrectionRequest).filter_by(
        employee_id=link.employee_id,
    ).order_by(models.HRAttendanceCorrectionRequest.requested_at.desc()).limit(limit).all()
    return [_correction_output(row) for row in rows]


@router.post("/corrections/{request_id}/review")
def review_attendance_correction(
    request_id: str,
    payload: CorrectionReview,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission("hr", "attendance_corrections", "review", "tenant")),
):
    row = db.get(models.HRAttendanceCorrectionRequest, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Correction request not found")
    if row.status != "submitted":
        raise HTTPException(status_code=409, detail=f"Only submitted requests can be reviewed; current status is {row.status}")
    if row.requested_by == user.username:
        raise HTTPException(status_code=403, detail="Requester cannot review their own attendance correction")
    scope = _correction_scope(db, user, row.work_date, "review")
    if scope is not None and row.employee_id not in scope:
        raise HTTPException(status_code=403, detail="Employee is outside your correction review scope")
    if _payroll_frozen(db, row.work_date):
        raise HTTPException(status_code=409, detail="Attendance correction is blocked for prepared, approved, finalized or locked payroll")
    now = datetime.now(timezone.utc)
    row.reviewer = user.username[:64]
    row.reviewed_at = now
    row.decision_reason = payload.reason.strip()
    if payload.decision == "reject":
        row.status = "rejected"
        log_audit(db, user.username, "REJECT", "hr_attendance_correction_request", f"{row.id}:{payload.reason[:300]}")
    elif payload.decision == "return":
        row.status = "returned"
        log_audit(db, user.username, "RETURN", "hr_attendance_correction_request", f"{row.id}:{payload.reason[:300]}")
    else:
        try:
            target = _validate_target(db, row.employee_id, row.work_date, row.correction_kind, row.target_event_id)
            event, created = append_attendance_event(
                db,
                employee_id=row.employee_id,
                work_date=row.work_date,
                event_type=row.proposed_event_type,
                occurred_at_utc=row.proposed_at_utc,
                timezone_name=row.timezone_name,
                source_type="manual_hr",
                source_reference=f"correction-{row.id}",
                recorded_by=user.username,
                roster_entry_id=target.roster_entry_id if target else None,
                break_rule_id=row.break_rule_id,
                supersedes_event_id=target.id if target else None,
                note=f"Approved correction request {row.id}",
            )
            row.applied_event_id = event.id
            row.status = "applied"
            summary, revision, revision_created = recalculate_attendance_summary(
                db, row.employee_id, row.work_date, calculated_by=user.username,
            )
            log_audit(
                db, user.username, "APPLY", "hr_attendance_correction_request",
                f"{row.id}: event={event.id}; summary_revision={summary.current_revision}; reason={payload.reason[:300]}",
            )
        except (AttendanceEventError, IntegrityError) as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="Correction could not be applied because the source event changed or was already corrected") from exc
    db.commit()
    db.refresh(row)
    return _correction_output(row)


@router.post("/corrections/{request_id}/resubmit")
def resubmit_attendance_correction(
    request_id: str,
    payload: CorrectionResubmit,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    link = db.query(models.EmployeeUserLink).filter_by(user_id=user.id).first()
    row = db.get(models.HRAttendanceCorrectionRequest, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Correction request not found")
    grants = db.query(models.RolePermissionGrant).filter_by(
        role=user.role.value, module="hr", feature="attendance_corrections",
        action="create", allowed=True,
    ).all()
    tenant_grant = any(grant.data_scope == "tenant" for grant in grants)
    self_grant = any(grant.data_scope == "self" for grant in grants)
    if tenant_grant:
        scope = _correction_scope(db, user, row.work_date, "create")
        if scope is not None and row.employee_id not in scope:
            raise HTTPException(status_code=403, detail="Employee is outside your correction resubmission scope")
    elif self_grant and link is not None and row.employee_id == link.employee_id and row.requested_by == user.username:
        pass
    else:
        raise HTTPException(status_code=403, detail="Missing attendance correction resubmission permission")
    if row.status != "returned":
        raise HTTPException(status_code=409, detail="Only returned correction requests may be resubmitted")
    if _payroll_frozen(db, row.work_date):
        raise HTTPException(status_code=409, detail="Attendance correction is blocked for frozen payroll")
    target = _validate_target(db, row.employee_id, row.work_date, payload.correction_kind, payload.target_event_id)
    if payload.break_code and payload.proposed_event_type not in {"break_start", "break_end"}:
        raise HTTPException(status_code=422, detail="Break Code is only valid for break events")
    try:
        context, roster, instant, break_rule_id = _local_event_context(
            db, row.employee_id, row.work_date, payload.occurred_at, payload.break_code,
        )
    except (AttendanceEventError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row.correction_kind = payload.correction_kind
    row.target_event_id = target.id if target else None
    row.proposed_event_type = payload.proposed_event_type
    row.proposed_at_utc = instant
    row.timezone_name = context.timezone_name
    row.break_rule_id = break_rule_id
    row.reason = payload.reason.strip()
    row.evidence_reference = payload.evidence_reference.strip()
    row.status = "submitted"
    row.reviewer = None
    row.reviewed_at = None
    row.decision_reason = ""
    log_audit(db, user.username, "RESUBMIT", "hr_attendance_correction_request", f"{row.id}:{payload.reason[:300]}")
    db.commit()
    db.refresh(row)
    return _correction_output(row)
