"""Tenant HR Admin overtime policy configuration APIs (P0.1-09 slice 01)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app import models
from app.api.deps import current_user, require_permission
from app.db.session import get_db
from app.modules.core.audit import log_audit

router = APIRouter(prefix="/hr/settings/overtime-policies", tags=["hr", "overtime-policy"])


class OvertimePolicyPayload(BaseModel):
    version_code: str = Field(min_length=1, max_length=40)
    effective_from: date
    effective_to: date | None = None
    scope: dict[str, Any] = Field(default_factory=dict)
    configuration: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not precede effective_from")
        return self


def _validate_scope(scope: dict[str, Any]) -> None:
    allowed = {"branch_ids", "departments", "employee_types", "shift_ids", "day_types"}
    unknown = set(scope) - allowed
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unsupported scope keys: {sorted(unknown)}")
    for key, value in scope.items():
        if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
            raise HTTPException(status_code=422, detail=f"{key} must be a list of non-empty strings")
    day_types = scope.get("day_types", [])
    if set(day_types) - {"scheduled_workday", "weekly_off", "holiday"}:
        raise HTTPException(status_code=422, detail="Unsupported day_types value")


def _validate_configuration(config: dict[str, Any], *, publishing: bool) -> None:
    allowed = {"workday_mode", "weekly_off_mode", "holiday_mode", "eligibility", "rounding", "compensation"}
    unknown = set(config) - allowed
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unsupported configuration keys: {sorted(unknown)}")
    if not publishing:
        return
    required = allowed
    missing = required - set(config)
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required configuration: {sorted(missing)}")
    if config["workday_mode"] not in {"beyond_scheduled_net", "outside_scheduled_interval"}:
        raise HTTPException(status_code=422, detail="Invalid workday_mode")
    if config["weekly_off_mode"] not in {"actual_work", "disabled"}:
        raise HTTPException(status_code=422, detail="Invalid weekly_off_mode")
    if config["holiday_mode"] not in {"actual_work", "disabled"}:
        raise HTTPException(status_code=422, detail="Invalid holiday_mode")
    eligibility = config["eligibility"]
    if not isinstance(eligibility, dict):
        raise HTTPException(status_code=422, detail="eligibility must be an object")
    for flag in ("pre_shift", "post_shift", "require_complete_attendance"):
        if flag not in eligibility or not isinstance(eligibility[flag], bool):
            raise HTTPException(status_code=422, detail=f"eligibility.{flag} must be explicitly configured")
    min_minutes = eligibility.get("minimum_minutes")
    cap = eligibility.get("maximum_minutes_per_day")
    if min_minutes is None or not isinstance(min_minutes, int) or min_minutes < 0:
        raise HTTPException(status_code=422, detail="eligibility.minimum_minutes must be a non-negative integer")
    if cap is not None and (not isinstance(cap, int) or cap <= 0):
        raise HTTPException(status_code=422, detail="eligibility.maximum_minutes_per_day must be a positive integer or null")
    rounding = config["rounding"]
    if not isinstance(rounding, dict) or rounding.get("method") not in {"none", "floor", "ceil", "nearest"}:
        raise HTTPException(status_code=422, detail="rounding.method must be none, floor, ceil or nearest")
    increment = rounding.get("increment_minutes")
    if rounding["method"] == "none":
        if increment not in (None, 0):
            raise HTTPException(status_code=422, detail="increment_minutes must be null/0 when rounding method is none")
    elif not isinstance(increment, int) or increment <= 0:
        raise HTTPException(status_code=422, detail="increment_minutes must be a positive integer for rounding")
    compensation = config["compensation"]
    if not isinstance(compensation, dict) or compensation.get("method") not in {"overtime", "comp_leave", "both", "disabled"}:
        raise HTTPException(status_code=422, detail="compensation.method must be overtime, comp_leave, both or disabled")
    conversion = compensation.get("credit_minutes_per_source_minute")
    if compensation["method"] in {"comp_leave", "both"}:
        if not isinstance(conversion, (int, float)) or conversion <= 0:
            raise HTTPException(status_code=422, detail="Compensatory conversion ratio must be explicitly positive")
    elif conversion not in (None, 0):
        raise HTTPException(status_code=422, detail="Compensatory conversion ratio must be omitted when comp leave is disabled")


def _serialize(row: models.HROvertimePolicyVersion) -> dict[str, Any]:
    return {
        "id": row.id,
        "version_code": row.version_code,
        "effective_from": row.effective_from.isoformat(),
        "effective_to": row.effective_to.isoformat() if row.effective_to else None,
        "status": row.status,
        "scope": row.scope,
        "configuration": row.configuration,
        "created_by": row.created_by,
        "published_by": row.published_by,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("")
def list_policies(
    include_drafts: bool = Query(True),
    user: models.User = Depends(require_permission("hr", "overtime_policies", "view", "tenant")),
    db: Session = Depends(get_db),
):
    query = db.query(models.HROvertimePolicyVersion)
    if not include_drafts:
        query = query.filter(models.HROvertimePolicyVersion.status == "published")
    return [_serialize(row) for row in query.order_by(models.HROvertimePolicyVersion.effective_from.desc()).all()]


@router.post("", status_code=201)
def create_policy(
    payload: OvertimePolicyPayload,
    user: models.User = Depends(require_permission("hr", "overtime_policies", "manage", "tenant")),
    db: Session = Depends(get_db),
):
    _validate_scope(payload.scope)
    _validate_configuration(payload.configuration, publishing=False)
    if db.query(models.HROvertimePolicyVersion).filter_by(version_code=payload.version_code).first():
        raise HTTPException(status_code=409, detail="Policy version_code already exists")
    row = models.HROvertimePolicyVersion(
        version_code=payload.version_code,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        scope=payload.scope,
        configuration=payload.configuration,
        status="draft",
        created_by=user.username,
    )
    db.add(row)
    db.flush()
    log_audit(db, user.username, "CREATE", "hr_overtime_policy_version", f"{row.id}: {row.version_code}")
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.put("/{policy_id}")
def update_policy(
    policy_id: str,
    payload: OvertimePolicyPayload,
    user: models.User = Depends(require_permission("hr", "overtime_policies", "manage", "tenant")),
    db: Session = Depends(get_db),
):
    row = db.get(models.HROvertimePolicyVersion, policy_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Overtime policy not found")
    if row.status != "draft":
        raise HTTPException(status_code=409, detail="Published/retired policy versions are immutable; create a new version")
    _validate_scope(payload.scope)
    _validate_configuration(payload.configuration, publishing=False)
    duplicate = db.query(models.HROvertimePolicyVersion).filter(
        models.HROvertimePolicyVersion.version_code == payload.version_code,
        models.HROvertimePolicyVersion.id != row.id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Policy version_code already exists")
    row.version_code = payload.version_code
    row.effective_from = payload.effective_from
    row.effective_to = payload.effective_to
    row.scope = payload.scope
    row.configuration = payload.configuration
    log_audit(db, user.username, "UPDATE", "hr_overtime_policy_version", f"{row.id}: {row.version_code}")
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.post("/{policy_id}/publish")
def publish_policy(
    policy_id: str,
    user: models.User = Depends(require_permission("hr", "overtime_policies", "publish", "tenant")),
    db: Session = Depends(get_db),
):
    row = db.get(models.HROvertimePolicyVersion, policy_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Overtime policy not found")
    if row.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft policies can be published")
    _validate_scope(row.scope or {})
    _validate_configuration(row.configuration or {}, publishing=True)
    conflicts = db.query(models.HROvertimePolicyVersion).filter(
        models.HROvertimePolicyVersion.status == "published",
        models.HROvertimePolicyVersion.id != row.id,
        models.HROvertimePolicyVersion.effective_from <= (row.effective_to or date.max),
    ).filter(
        (models.HROvertimePolicyVersion.effective_to.is_(None))
        | (models.HROvertimePolicyVersion.effective_to >= row.effective_from)
    ).all()
    for existing in conflicts:
        if (existing.scope or {}) == (row.scope or {}):
            raise HTTPException(status_code=409, detail="A published policy with the same scope overlaps this effective period")
    row.status = "published"
    row.published_by = user.username
    row.published_at = datetime.now(timezone.utc)
    log_audit(db, user.username, "PUBLISH", "hr_overtime_policy_version", f"{row.id}: {row.version_code}")
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.post("/{policy_id}/retire")
def retire_policy(
    policy_id: str,
    user: models.User = Depends(require_permission("hr", "overtime_policies", "publish", "tenant")),
    db: Session = Depends(get_db),
):
    row = db.get(models.HROvertimePolicyVersion, policy_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Overtime policy not found")
    if row.status != "published":
        raise HTTPException(status_code=409, detail="Only published policies can be retired")
    row.status = "retired"
    log_audit(db, user.username, "RETIRE", "hr_overtime_policy_version", f"{row.id}: {row.version_code}")
    db.commit()
    db.refresh(row)
    return _serialize(row)

class PolicyPreviewIn(BaseModel):
    employee_id: str = Field(min_length=1)
    work_date: date

@router.post("/preview")
def preview_policy(
    payload: PolicyPreviewIn,
    user: models.User = Depends(require_permission("hr", "overtime_policies", "view", "tenant")),
    db: Session = Depends(get_db),
):
    employee = db.get(models.Employee, payload.employee_id)
    if employee is None or not employee.active:
        raise HTTPException(404, detail="Employee not found or inactive")
    roster = db.query(models.HRShiftRosterEntry).filter_by(employee_id=employee.id, work_date=payload.work_date).first()
    day_type = "weekly_off" if roster and roster.status == "weekly_off" else "holiday" if roster and roster.status == "holiday" else "scheduled_workday"
    if not roster:
        calendar = db.query(models.HRCalendarDay).filter_by(work_date=payload.work_date).first()
        if calendar and calendar.day_type == "holiday": day_type = "holiday"
        elif calendar and calendar.day_type == "week_off": day_type = "weekly_off"
    org = db.query(models.EmployeeOrgAssignment).filter(
        models.EmployeeOrgAssignment.employee_id == employee.id,
        models.EmployeeOrgAssignment.valid_from <= payload.work_date,
        (models.EmployeeOrgAssignment.valid_to.is_(None) | (models.EmployeeOrgAssignment.valid_to >= payload.work_date)),
    ).order_by(models.EmployeeOrgAssignment.valid_from.desc()).first()
    values = {
        "branch_ids": org.branch_id if org else None,
        "departments": org.department if org else employee.department,
        "employee_types": employee.employee_type,
        "shift_ids": roster.shift_type_id if roster else None,
        "day_types": day_type,
    }
    policies = db.query(models.HROvertimePolicyVersion).filter(
        models.HROvertimePolicyVersion.status == "published",
        models.HROvertimePolicyVersion.effective_from <= payload.work_date,
        (models.HROvertimePolicyVersion.effective_to.is_(None) | (models.HROvertimePolicyVersion.effective_to >= payload.work_date)),
    ).all()
    matching = [p for p in policies if all(not (p.scope or {}).get(k) or v in (p.scope or {}).get(k, []) for k, v in values.items())]
    specificity = lambda p: sum(bool((p.scope or {}).get(k)) for k in values)
    if not matching:
        return {"state": "configuration_required", "employee_id": employee.id, "work_date": payload.work_date, "day_type": day_type, "matches": []}
    top = max(specificity(p) for p in matching)
    winners = [p for p in matching if specificity(p) == top]
    return {"state": "resolved" if len(winners) == 1 else "ambiguous", "employee_id": employee.id, "work_date": payload.work_date, "day_type": day_type, "specificity": top, "selected": _serialize(winners[0]) if len(winners) == 1 else None, "matches": [_serialize(p) for p in matching]}
