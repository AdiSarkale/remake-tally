"""Tenant-policy-driven comparison of immutable attendance source events."""
from __future__ import annotations

import hashlib
from datetime import date, timezone
from decimal import Decimal, InvalidOperation
from itertools import combinations

from sqlalchemy.orm import Session

from app.modules.core.audit import log_audit
from app.modules.hr.payroll import (
    HRAttendanceAnomaly,
    HRAttendanceEvent,
    HRWorkforcePolicyVersion,
)


MARGIN_CONFIGURATION_KEY = "attendance_source_error_margin_minutes"


def effective_attendance_policy(db: Session, work_date: date) -> HRWorkforcePolicyVersion | None:
    """Return the single effective workforce policy; ambiguity fails closed."""
    rows = db.query(HRWorkforcePolicyVersion).filter(
        HRWorkforcePolicyVersion.effective_from <= work_date,
        (HRWorkforcePolicyVersion.effective_to.is_(None))
        | (HRWorkforcePolicyVersion.effective_to >= work_date),
    ).order_by(HRWorkforcePolicyVersion.effective_from.desc()).all()
    return rows[0] if len(rows) == 1 else None


def configured_attendance_margin(
    db: Session, work_date: date,
) -> tuple[HRWorkforcePolicyVersion, int] | None:
    policy = effective_attendance_policy(db, work_date)
    if policy is None or not isinstance(policy.configuration, dict):
        return None
    raw = policy.configuration.get(MARGIN_CONFIGURATION_KEY)
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    if not value.is_finite() or value < 0 or value != value.to_integral_value():
        return None
    return policy, int(value)


def _as_utc(value):
    """Normalize database-returned naive timestamps as UTC before comparison."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _comparison_key(event_ids: list[str]) -> str:
    return hashlib.sha256("|".join(sorted(event_ids)).encode("utf-8")).hexdigest()


def reconcile_attendance_event(
    db: Session, event: HRAttendanceEvent,
) -> list[HRAttendanceAnomaly]:
    """Compare a new event with equivalent events from other source systems.

    Events are never edited or selected as a winner here. The anomaly stores
    both immutable event IDs and the exact policy/threshold used.
    """
    if event.voided_at is not None:
        return []
    configured = configured_attendance_margin(db, event.work_date)
    if configured is None:
        return []
    policy, threshold_minutes = configured

    candidates = db.query(HRAttendanceEvent).filter(
        HRAttendanceEvent.employee_id == event.employee_id,
        HRAttendanceEvent.work_date == event.work_date,
        HRAttendanceEvent.event_type == event.event_type,
        HRAttendanceEvent.voided_at.is_(None),
        HRAttendanceEvent.id != event.id,
        HRAttendanceEvent.source_type != event.source_type,
    ).order_by(HRAttendanceEvent.occurred_at_utc.asc()).all()

    # Superseded source facts remain in the ledger but are not current comparison
    # candidates. The superseding event itself remains available for comparison.
    superseded_ids = {
        row[0] for row in db.query(HRAttendanceEvent.supersedes_event_id).filter(
            HRAttendanceEvent.supersedes_event_id.is_not(None),
        ).all()
    }
    created: list[HRAttendanceAnomaly] = []
    for other in candidates:
        if other.id in superseded_ids:
            continue
        ids = sorted([event.id, other.id])
        if db.query(HRAttendanceAnomaly.id).filter(
            HRAttendanceAnomaly.comparison_key == _comparison_key(ids),
        ).first():
            continue

        delta_seconds = abs(
            (_as_utc(event.occurred_at_utc) - _as_utc(other.occurred_at_utc)).total_seconds()
        )
        if Decimal(str(delta_seconds)) <= Decimal(threshold_minutes) * Decimal(60):
            continue

        observed_minutes = (
            Decimal(str(delta_seconds)) / Decimal(60)
        ).quantize(Decimal("0.01"))
        anomaly = HRAttendanceAnomaly(
            comparison_key=_comparison_key(ids),
            employee_id=event.employee_id,
            work_date=event.work_date,
            roster_entry_id=event.roster_entry_id or other.roster_entry_id,
            anomaly_type="source_mismatch",
            source_event_ids=ids,
            observed_delta_minutes=observed_minutes,
            threshold_minutes=threshold_minutes,
            policy_version_id=policy.id,
            status="open",
        )
        db.add(anomaly)
        db.flush()
        log_audit(
            db,
            event.recorded_by,
            "CREATE",
            "hr_attendance_anomaly",
            f"{anomaly.id}: employee={event.employee_id}; date={event.work_date}; "
            f"events={','.join(ids)}; delta={observed_minutes}; threshold={threshold_minutes}",
        )
        created.append(anomaly)
    return created


def reconcile_attendance_work_date(
    db: Session, employee_id: str, work_date: date,
) -> list[HRAttendanceAnomaly]:
    """Re-run source comparison for a date after tenant policy configuration."""
    events = db.query(HRAttendanceEvent).filter(
        HRAttendanceEvent.employee_id == employee_id,
        HRAttendanceEvent.work_date == work_date,
        HRAttendanceEvent.voided_at.is_(None),
    ).order_by(HRAttendanceEvent.occurred_at_utc.asc()).all()
    created: list[HRAttendanceAnomaly] = []
    for event in events:
        created.extend(reconcile_attendance_event(db, event))
    return created
