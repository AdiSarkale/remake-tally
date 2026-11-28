"""P0.1-07 tenant-policy attendance source reconciliation regressions."""
from datetime import date, datetime
from io import BytesIO

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.api.routes.hr_attendance_events import (
    AttendanceAnomalyFalsePositive,
    AttendanceAnomalyResolve,
    AttendanceAnomalySettingsCreate,
    create_attendance_anomaly_settings,
    mark_attendance_anomaly_false_positive,
    resolve_attendance_anomaly,
)
from app.modules.hr.attendance_events import append_attendance_event
from app.modules.hr.attendance_reconciliation import (
    configured_attendance_margin,
    reconcile_attendance_work_date,
)


def _db():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    return engine, Session(engine)


def _employee(db):
    employee = models.Employee(
        id="reconcile-employee",
        emp_code="EMP-REC-001",
        name="Reconciliation Employee",
        joining_date=date(2026, 1, 1),
        active=True,
    )
    db.add(employee)
    db.add(models.HRPayrollSettings(id=1, timezone="Asia/Kolkata"))
    db.commit()
    return employee


def _hr_user(db):
    user = models.User(
        id="reconcile-hr-user",
        username="reconcile-hr-user",
        full_name="HR User",
        password_hash="test",
        role=models.Role.hr,
        active=True,
        must_change_password=False,
    )
    db.add(user)
    for feature, action in (("employees", "read"), ("employees", "update")):
        db.add(models.RolePermissionGrant(
            role="HR", module="hr", feature=feature, action=action,
            data_scope="tenant", allowed=True, updated_by="test",
        ))
    db.commit()
    return user


def _policy(db, *, margin=5, version="POLICY-001"):
    policy = models.HRWorkforcePolicyVersion(
        version_code=version,
        effective_from=date(2026, 1, 1),
        effective_to=None,
        configuration={"attendance_source_error_margin_minutes": margin},
        created_by="admin",
    )
    db.add(policy)
    db.commit()
    return policy


def _append(db, employee, *, source, reference, minute, event_type="punch_in"):
    return append_attendance_event(
        db,
        employee_id=employee.id,
        work_date=date(2026, 11, 10),
        event_type=event_type,
        occurred_at_utc=datetime(2026, 11, 10, 3, minute),
        timezone_name="Asia/Kolkata",
        source_type=source,
        source_reference=reference,
        recorded_by="hr-user",
    )


def test_source_mismatch_creates_one_anomaly_with_policy_threshold_snapshot():
    engine, db = _db()
    try:
        employee = _employee(db)
        policy = _policy(db, margin=5)

        first, first_created = _append(
            db, employee, source="employee", reference="employee-punch-1", minute=30,
        )
        assert first_created is True
        assert db.query(models.HRAttendanceAnomaly).count() == 0

        second, second_created = _append(
            db, employee, source="manual_hr", reference="manual-punch-1", minute=38,
        )
        db.commit()

        assert second_created is True
        anomalies = db.query(models.HRAttendanceAnomaly).all()
        assert len(anomalies) == 1
        anomaly = anomalies[0]
        assert anomaly.anomaly_type == "source_mismatch"
        assert set(anomaly.source_event_ids) == {first.id, second.id}
        assert float(anomaly.observed_delta_minutes) == 8.0
        assert anomaly.threshold_minutes == 5
        assert anomaly.policy_version_id == policy.id
        assert anomaly.status == "open"
    finally:
        db.close()
        engine.dispose()


def test_equal_or_below_threshold_does_not_create_anomaly():
    engine, db = _db()
    try:
        employee = _employee(db)
        _policy(db, margin=5)
        _append(db, employee, source="employee", reference="employee-punch-2", minute=30)
        _append(db, employee, source="manual_hr", reference="manual-punch-2", minute=35)
        db.commit()
        assert db.query(models.HRAttendanceAnomaly).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_missing_or_ambiguous_threshold_fails_closed_without_guessed_margin():
    engine, db = _db()
    try:
        employee = _employee(db)
        _append(db, employee, source="employee", reference="employee-punch-3", minute=30)
        _append(db, employee, source="manual_hr", reference="manual-punch-3", minute=50)
        db.commit()
        assert db.query(models.HRAttendanceAnomaly).count() == 0

        _policy(db, margin=5, version="POLICY-A")
        _policy(db, margin=10, version="POLICY-B")
        db.commit()
        assert configured_attendance_margin(db, date(2026, 11, 10)) is None
        assert db.query(models.HRAttendanceAnomaly).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_same_source_events_are_not_compared_and_retry_is_idempotent():
    engine, db = _db()
    try:
        employee = _employee(db)
        _policy(db, margin=0)
        event, created = _append(
            db, employee, source="excel_import", reference="same-source-1", minute=30,
        )
        _append(
            db, employee, source="excel_import", reference="same-source-2", minute=45,
        )
        retried, retry_created = _append(
            db, employee, source="excel_import", reference="same-source-1", minute=30,
        )
        db.commit()
        assert created is True
        assert retry_created is False
        assert retried.id == event.id
        assert db.query(models.HRAttendanceAnomaly).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_reconciliation_backfills_existing_source_pairs_after_policy_is_configured():
    engine, db = _db()
    try:
        employee = _employee(db)
        _append(db, employee, source="employee", reference="backfill-employee", minute=30)
        _append(db, employee, source="manual_hr", reference="backfill-manual", minute=50)
        db.commit()
        assert db.query(models.HRAttendanceAnomaly).count() == 0

        _policy(db, margin=5)
        created = reconcile_attendance_work_date(db, employee.id, date(2026, 11, 10))
        db.commit()
        assert len(created) == 1
        assert db.query(models.HRAttendanceAnomaly).count() == 1

        again = reconcile_attendance_work_date(db, employee.id, date(2026, 11, 10))
        db.commit()
        assert again == []
        assert db.query(models.HRAttendanceAnomaly).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_anomaly_resolution_records_selected_source_and_preserves_raw_events():
    engine, db = _db()
    try:
        employee = _employee(db)
        user = _hr_user(db)
        _policy(db, margin=5)
        first, _ = _append(db, employee, source="employee", reference="resolve-employee", minute=30)
        _append(db, employee, source="manual_hr", reference="resolve-manual", minute=38)
        db.commit()
        anomaly = db.query(models.HRAttendanceAnomaly).one()

        result = resolve_attendance_anomaly(
            anomaly.id,
            AttendanceAnomalyResolve(
                reason="Reviewed the employee terminal record against supervisor evidence",
                selected_event_id=first.id,
            ),
            db=db,
            user=user,
        )
        assert result["status"] == "resolved"
        assert result["resolution_result"] == {"selected_event_id": first.id}
        assert db.query(models.HRAttendanceEvent).count() == 2
        assert db.get(models.HRAttendanceEvent, first.id) is not None
    finally:
        db.close()
        engine.dispose()


def test_false_positive_requires_reason_and_does_not_change_source_events():
    engine, db = _db()
    try:
        employee = _employee(db)
        user = _hr_user(db)
        _policy(db, margin=5)
        _append(db, employee, source="employee", reference="fp-employee", minute=30)
        _append(db, employee, source="manual_hr", reference="fp-manual", minute=38)
        db.commit()
        anomaly = db.query(models.HRAttendanceAnomaly).one()

        result = mark_attendance_anomaly_false_positive(
            anomaly.id,
            AttendanceAnomalyFalsePositive(reason="Reader clock was under maintenance"),
            db=db,
            user=user,
        )
        assert result["status"] == "false_positive"
        assert result["resolution_reason"] == "Reader clock was under maintenance"
        assert db.query(models.HRAttendanceEvent).count() == 2
    finally:
        db.close()
        engine.dispose()


def test_anomaly_policy_setting_creates_version_and_closes_previous_effective_period():
    engine, db = _db()
    try:
        _employee(db)
        user = _hr_user(db)
        first = create_attendance_anomaly_settings(
            AttendanceAnomalySettingsCreate(
                version_code="ATT-MARGIN-001",
                effective_from=date(2026, 1, 1),
                attendance_source_error_margin_minutes=5,
            ),
            db=db,
            user=user,
        )
        second = create_attendance_anomaly_settings(
            AttendanceAnomalySettingsCreate(
                version_code="ATT-MARGIN-002",
                effective_from=date(2026, 11, 1),
                attendance_source_error_margin_minutes=8,
            ),
            db=db,
            user=user,
        )
        old = db.get(models.HRWorkforcePolicyVersion, first["policy_version_id"])
        current = db.get(models.HRWorkforcePolicyVersion, second["policy_version_id"])
        assert old.effective_to == date(2026, 10, 31)
        assert old.configuration["attendance_source_error_margin_minutes"] == 5
        assert current.configuration["attendance_source_error_margin_minutes"] == 8
    finally:
        db.close()
        engine.dispose()
