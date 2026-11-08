"""Tenant-scoped HR shift catalog and break-rule APIs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app import schemas
from app.api.deps import require_permission
from app.db.session import get_db
from app.modules.core.audit import log_audit

router = APIRouter(prefix="/hr/shifts", tags=["hr", "shifts"])
read_access = Depends(require_permission("hr", "shifts", "read", "tenant"))
write_access = Depends(require_permission("hr", "shifts", "write", "tenant"))


def _get_shift(db: Session, shift_id: str) -> models.HRShiftType:
    row = db.get(models.HRShiftType, shift_id)
    if row is None:
        raise HTTPException(404, "Shift not found")
    return row


def _get_break_rule(
    db: Session, shift_id: str, rule_id: str,
) -> models.HRShiftBreakRule:
    row = db.query(models.HRShiftBreakRule).filter_by(
        id=rule_id, shift_type_id=shift_id,
    ).first()
    if row is None:
        raise HTTPException(404, "Break rule not found for this shift")
    return row


def _validate_break_window(
    payload: schemas.ShiftBreakRuleIn, shift: models.HRShiftType,
) -> None:
    if payload.scheduled_start_time is None:
        return
    shift_start = shift.start_time.hour * 60 + shift.start_time.minute
    shift_end = (
        shift.end_time.hour * 60 + shift.end_time.minute
        + shift.end_day_offset * 1440
    )
    break_start = payload.scheduled_start_time.hour * 60 + payload.scheduled_start_time.minute
    break_end = payload.scheduled_end_time.hour * 60 + payload.scheduled_end_time.minute
    if shift.end_day_offset and break_start < shift_start:
        break_start += 1440
        break_end += 1440
    if break_start < shift_start or break_end > shift_end:
        raise HTTPException(
            422,
            "Scheduled break window must fall within the shift's local-time window",
        )


def _shift_detail(db: Session, row: models.HRShiftType) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "start_time": row.start_time,
        "end_time": row.end_time,
        "end_day_offset": row.end_day_offset,
        "active": row.active,
        "break_rules": db.query(models.HRShiftBreakRule).filter_by(
            shift_type_id=row.id,
        ).order_by(models.HRShiftBreakRule.sequence, models.HRShiftBreakRule.code).all(),
    }


@router.get("", response_model=list[schemas.ShiftTypeOut])
def list_shifts(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: models.User = read_access,
):
    query = db.query(models.HRShiftType)
    if not include_inactive:
        query = query.filter(models.HRShiftType.active.is_(True))
    return query.order_by(models.HRShiftType.code).all()


@router.post("", response_model=schemas.ShiftTypeDetailOut, status_code=201)
def create_shift(
    payload: schemas.ShiftTypeIn,
    db: Session = Depends(get_db),
    user: models.User = write_access,
):
    row = models.HRShiftType(
        **payload.model_dump(),
        active=True,
        created_by=user.username,
    )
    db.add(row)
    try:
        db.flush()
        log_audit(
            db, user.username, "CREATE", "hr_shift_type",
            f"{row.code}; {row.start_time}-{row.end_time}; end_day_offset={row.end_day_offset}",
        )
        db.commit()
        db.refresh(row)
        return _shift_detail(db, row)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Shift code already exists") from exc


@router.get("/{shift_id}", response_model=schemas.ShiftTypeDetailOut)
def get_shift(
    shift_id: str,
    db: Session = Depends(get_db),
    user: models.User = read_access,
):
    return _shift_detail(db, _get_shift(db, shift_id))


@router.put("/{shift_id}", response_model=schemas.ShiftTypeDetailOut)
def update_shift(
    shift_id: str,
    payload: schemas.ShiftTypeIn,
    db: Session = Depends(get_db),
    user: models.User = write_access,
):
    row = _get_shift(db, shift_id)
    if payload.code != row.code:
        raise HTTPException(422, "Shift code is immutable after creation")
    schedule_changed = (
        payload.start_time != row.start_time
        or payload.end_time != row.end_time
        or payload.end_day_offset != row.end_day_offset
    )
    if schedule_changed:
        assigned = db.query(models.HRShiftAssignment.id).filter_by(
            shift_type_id=row.id,
        ).first()
        rostered = db.query(models.HRShiftRosterEntry.id).filter_by(
            shift_type_id=row.id,
        ).first()
        if assigned or rostered:
            raise HTTPException(
                409,
                "Shift timing is already referenced by an assignment or roster. Create a new shift code for the revised schedule.",
            )
    row.name = payload.name
    row.start_time = payload.start_time
    row.end_time = payload.end_time
    row.end_day_offset = payload.end_day_offset
    try:
        log_audit(
            db, user.username, "UPDATE", "hr_shift_type",
            f"{row.code}; {row.start_time}-{row.end_time}; end_day_offset={row.end_day_offset}",
        )
        db.commit()
        db.refresh(row)
        return _shift_detail(db, row)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Shift update conflicts with existing data") from exc


@router.patch("/{shift_id}/active", response_model=schemas.ShiftTypeOut)
def set_shift_active(
    shift_id: str,
    payload: schemas.ShiftActiveIn,
    db: Session = Depends(get_db),
    user: models.User = write_access,
):
    row = _get_shift(db, shift_id)
    row.active = payload.active
    log_audit(db, user.username, "UPDATE", "hr_shift_type", f"{row.code}; active={row.active}")
    db.commit()
    db.refresh(row)
    return row


@router.get("/{shift_id}/break-rules", response_model=list[schemas.ShiftBreakRuleOut])
def list_break_rules(
    shift_id: str,
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: models.User = read_access,
):
    _get_shift(db, shift_id)
    query = db.query(models.HRShiftBreakRule).filter_by(shift_type_id=shift_id)
    if not include_inactive:
        query = query.filter(models.HRShiftBreakRule.active.is_(True))
    return query.order_by(
        models.HRShiftBreakRule.sequence, models.HRShiftBreakRule.code,
    ).all()


@router.post(
    "/{shift_id}/break-rules",
    response_model=schemas.ShiftBreakRuleOut,
    status_code=201,
)
def create_break_rule(
    shift_id: str,
    payload: schemas.ShiftBreakRuleIn,
    db: Session = Depends(get_db),
    user: models.User = write_access,
):
    shift = _get_shift(db, shift_id)
    if not shift.active:
        raise HTTPException(409, "Cannot add break rules to an inactive shift")
    _validate_break_window(payload, shift)
    row = models.HRShiftBreakRule(
        shift_type_id=shift.id,
        **payload.model_dump(),
        active=True,
    )
    db.add(row)
    try:
        db.flush()
        log_audit(
            db, user.username, "CREATE", "hr_shift_break_rule",
            f"{shift.code}:{row.code}; paid={row.is_paid}; minutes={row.planned_duration_minutes}",
        )
        db.commit()
        db.refresh(row)
        return row
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Break rule code already exists for this shift") from exc


@router.put(
    "/{shift_id}/break-rules/{rule_id}",
    response_model=schemas.ShiftBreakRuleOut,
)
def update_break_rule(
    shift_id: str,
    rule_id: str,
    payload: schemas.ShiftBreakRuleIn,
    db: Session = Depends(get_db),
    user: models.User = write_access,
):
    shift = _get_shift(db, shift_id)
    row = _get_break_rule(db, shift_id, rule_id)
    if payload.code != row.code:
        raise HTTPException(422, "Break rule code is immutable after creation")
    _validate_break_window(payload, shift)
    for key, value in payload.model_dump(exclude={"code"}).items():
        setattr(row, key, value)
    try:
        log_audit(
            db, user.username, "UPDATE", "hr_shift_break_rule",
            f"{shift.code}:{row.code}; paid={row.is_paid}; minutes={row.planned_duration_minutes}",
        )
        db.commit()
        db.refresh(row)
        return row
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Break rule update conflicts with existing data") from exc


@router.patch(
    "/{shift_id}/break-rules/{rule_id}/active",
    response_model=schemas.ShiftBreakRuleOut,
)
def set_break_rule_active(
    shift_id: str,
    rule_id: str,
    payload: schemas.ShiftBreakRuleActiveIn,
    db: Session = Depends(get_db),
    user: models.User = write_access,
):
    shift = _get_shift(db, shift_id)
    row = _get_break_rule(db, shift_id, rule_id)
    if payload.active and not shift.active:
        raise HTTPException(409, "Cannot activate a break rule while its shift is inactive")
    row.active = payload.active
    log_audit(
        db, user.username, "UPDATE", "hr_shift_break_rule",
        f"{shift.code}:{row.code}; active={row.active}",
    )
    db.commit()
    db.refresh(row)
    return row
