"""P0.1-08 daily attendance summary and correction workflow regressions."""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.api.routes.hr_attendance_summary import CorrectionReview, review_attendance_correction
from app.modules.hr.attendance_events import append_attendance_event
from app.modules.hr.attendance_summary import calculate_attendance_projection, recalculate_attendance_summary


def _db():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    return engine, Session(engine)


def _employee(db):
    employee = models.Employee(
        id="summary-employee",
        emp_code="EMP-SUM-001",
        name="Summary Employee",
        joining_date=date(2026, 1, 1),
        active=True,
    )
    db.add(employee)
    db.add(models.HRPayrollSettings(id=1, timezone="Asia/Kolkata"))
    db.commit()
    return employee


def _event(db, employee, event_type, minute, reference, *, supersedes=None):
    return append_attendance_event(
        db,
        employee_id=employee.id,
        work_date=date(2026, 11, 10),
        event_type=event_type,
        occurred_at_utc=datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc) + timedelta(minutes=minute),
        timezone_name="Asia/Kolkata",
        source_type="manual_hr",
        source_reference=reference,
        recorded_by="test-hr",
        supersedes_event_id=supersedes,
    )[0]


def _user(db, username="summary-reviewer", role=models.Role.hr):
    user = models.User(
        id=username,
        username=username,
        full_name=username,
        password_hash="test",
        role=role,
        active=True,
        must_change_password=False,
    )
    db.add(user)
    if role == models.Role.hr:
        db.add(models.RolePermissionGrant(
            role="HR", module="hr", feature="attendance_corrections", action="review",
            data_scope="tenant", allowed=True, updated_by="test",
        ))
    db.commit()
    return user


def test_projection_complete_punch_pair_and_revision_is_idempotent():
    engine, db = _db()
    try:
        employee = _employee(db)
        _event(db, employee, "punch_in", 30, "summary-in")
        _event(db, employee, "punch_out", 510, "summary-out")
        db.commit()

        projection = calculate_attendance_projection(db, employee.id, date(2026, 11, 10))
        assert projection["classification"] == "complete"
        assert projection["elapsed_minutes"] == 480
        assert projection["exception_codes"] == []

        summary, revision, created = recalculate_attendance_summary(
            db, employee.id, date(2026, 11, 10), calculated_by="hr",
        )
        db.commit()
        assert created is False
        assert summary.current_revision == 2
        assert revision.revision == 2

        same_summary, same_revision, second_created = recalculate_attendance_summary(
            db, employee.id, date(2026, 11, 10), calculated_by="hr",
        )
        assert second_created is False
        assert same_summary.current_revision == 2
        assert same_revision.id == revision.id
        assert db.query(models.HRAttendanceSummaryRevision).count() == 2
    finally:
        db.close()
        engine.dispose()


def test_projection_missing_punch_out_is_incomplete_not_absence():
    engine, db = _db()
    try:
        employee = _employee(db)
        _event(db, employee, "punch_in", 30, "missing-out-in")
        db.commit()
        projection = calculate_attendance_projection(db, employee.id, date(2026, 11, 10))
        assert projection["classification"] == "incomplete"
        assert "missing_punch_out" in projection["exception_codes"]
        assert projection["elapsed_minutes"] == 0
    finally:
        db.close()
        engine.dispose()


def test_projection_unmatched_break_is_invalid_sequence():
    engine, db = _db()
    try:
        employee = _employee(db)
        _event(db, employee, "punch_in", 30, "invalid-break-in")
        _event(db, employee, "break_end", 180, "invalid-break-end")
        _event(db, employee, "punch_out", 510, "invalid-break-out")
        db.commit()
        projection = calculate_attendance_projection(db, employee.id, date(2026, 11, 10))
        assert projection["classification"] == "invalid_sequence"
        assert "break_end_without_break_start" in projection["exception_codes"]
    finally:
        db.close()
        engine.dispose()


def test_approved_correction_supersedes_prior_event_and_recalculates_summary():
    engine, db = _db()
    try:
        employee = _employee(db)
        reviewer = _user(db)
        original = _event(db, employee, "punch_in", 30, "correction-original")
        _event(db, employee, "punch_out", 510, "correction-out")
        request = models.HRAttendanceCorrectionRequest(
            id="correction-request-001",
            employee_id=employee.id,
            work_date=date(2026, 11, 10),
            correction_kind="replace",
            target_event_id=original.id,
            proposed_event_type="punch_in",
            proposed_at_utc=datetime(2026, 11, 10, 3, 45, tzinfo=timezone.utc),
            timezone_name="Asia/Kolkata",
            reason="Correct verified gate entry time",
            evidence_reference="gate-log-001",
            status="submitted",
            requested_by="employee-requester",
        )
        db.add(request)
        db.commit()

        result = review_attendance_correction(
            request.id, CorrectionReview(decision="approve", reason="Verified against gate record"),
            db, reviewer,
        )
        assert result["status"] == "applied"
        assert result["applied_event_id"]
        corrected = db.get(models.HRAttendanceEvent, result["applied_event_id"])
        assert corrected.supersedes_event_id == original.id
        assert original.voided_at is None
        projection = calculate_attendance_projection(db, employee.id, date(2026, 11, 10))
        assert original.id not in projection["source_event_ids"]
        assert corrected.id in projection["source_event_ids"]
        assert projection["classification"] == "complete"
    finally:
        db.close()
        engine.dispose()


def test_requester_cannot_review_own_correction():
    engine, db = _db()
    try:
        employee = _employee(db)
        requester = _user(db, username="self-review")
        request = models.HRAttendanceCorrectionRequest(
            id="correction-self-review",
            employee_id=employee.id,
            work_date=date(2026, 11, 10),
            correction_kind="add",
            target_event_id=None,
            proposed_event_type="punch_in",
            proposed_at_utc=datetime(2026, 11, 10, 3, 30, tzinfo=timezone.utc),
            timezone_name="Asia/Kolkata",
            reason="Forgot to punch in",
            status="submitted",
            requested_by=requester.username,
        )
        db.add(request)
        db.commit()
        with pytest.raises(Exception) as exc:
            review_attendance_correction(
                request.id, CorrectionReview(decision="approve", reason="Not allowed"),
                db, requester,
            )
        assert "Requester cannot review" in exc.value.detail
        assert request.status == "submitted"
    finally:
        db.close()
        engine.dispose()
