"""P0.1-10 daily source provenance and approved overtime integration tests."""
from datetime import date, datetime, time, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.modules.hr.payroll_integration import build_payroll_daily_inputs
from app.api.routes.hr_payroll import PayrollSupersedePayload, finalize_monthly_payroll, supersede_payroll_run


def _db():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    return engine, Session(engine)


def test_daily_snapshot_includes_only_approved_payable_overtime_and_open_anomaly():
    engine, db = _db()
    try:
        employee = models.Employee(
            id="payroll-integration-employee", emp_code="EMP-PI-001",
            name="Payroll Integration Employee", department="Production",
            joining_date=date(2026, 1, 1), active=True,
        )
        shift = models.HRShiftType(
            id="payroll-integration-shift", code="PI-DAY", name="Integration Day",
            start_time=time(9, 0), end_time=time(17, 0), end_day_offset=0,
            active=True, created_by="test",
        )
        policy = models.HROvertimePolicyVersion(
            id="payroll-integration-policy", version_code="PI-OT-1",
            effective_from=date(2026, 1, 1), status="published",
            scope={}, configuration={}, created_by="test",
        )
        workforce_policy = models.HRWorkforcePolicyVersion(
            id="payroll-integration-workforce-policy", version_code="PI-WF-1",
            effective_from=date(2026, 1, 1), configuration={}, created_by="test",
        )
        db.add_all([employee, shift, policy, workforce_policy])
        db.flush()
        roster = models.HRShiftRosterEntry(
            id="payroll-integration-roster", employee_id=employee.id,
            work_date=date(2026, 11, 10), status="scheduled",
            shift_type_id=shift.id, timezone_name="Asia/Kolkata",
            scheduled_start_at_utc=datetime(2026, 11, 10, 3, 30, tzinfo=timezone.utc),
            scheduled_end_at_utc=datetime(2026, 11, 10, 11, 30, tzinfo=timezone.utc),
            shift_code_snapshot=shift.code, shift_name_snapshot=shift.name,
            break_rules_snapshot=[], version=1, created_by="test",
        )
        approved_ot = models.HROvertimeCandidate(
            id="payroll-integration-ot-1", employee_id=employee.id,
            work_date=date(2026, 11, 10), revision=1, status="approved",
            day_type="scheduled_workday", policy_id=policy.id, policy_version=policy.version_code,
            raw_candidate_minutes=75, rounded_candidate_minutes=60,
            calculation_snapshot={"compensation_snapshot": {"method": "overtime"}},
            input_fingerprint="ot-approved-fingerprint", source_event_ids=["event-1"],
        )
        approved_comp = models.HROvertimeCandidate(
            id="payroll-integration-ot-2", employee_id=employee.id,
            work_date=date(2026, 11, 10), revision=2, status="approved",
            day_type="scheduled_workday", policy_id=policy.id, policy_version=policy.version_code,
            raw_candidate_minutes=30, rounded_candidate_minutes=30,
            calculation_snapshot={"compensation_snapshot": {"method": "compensatory_leave"}},
            input_fingerprint="ot-comp-fingerprint", source_event_ids=["event-2"],
        )
        open_anomaly = models.HRAttendanceAnomaly(
            id="payroll-integration-anomaly", comparison_key="integration-anomaly-key",
            employee_id=employee.id, work_date=date(2026, 11, 10),
            anomaly_type="source_mismatch", source_event_ids=["event-1", "event-2"],
            observed_delta_minutes=25, threshold_minutes=10, policy_version_id=workforce_policy.id,
            status="open",
        )
        db.add_all([roster, approved_ot, approved_comp, open_anomaly])
        db.commit()

        daily = build_payroll_daily_inputs(
            db, [employee], date(2026, 11, 10), date(2026, 11, 10),
            [5, 6], {}, [],
        )[employee.id][0]

        snapshot = daily["snapshot"]
        assert daily["scheduled"] is True
        assert daily["approved_overtime_minutes"] == 60
        assert snapshot["approved_payable_overtime_minutes"] == 60
        assert {row["compensation_method"] for row in snapshot["approved_overtime"]} == {
            "overtime", "compensatory_leave",
        }
        assert snapshot["source_anomalies"][0]["status"] == "open"
        assert snapshot["source_anomalies"][0]["id"] == open_anomaly.id
        assert len(daily["fingerprint"]) == 64
    finally:
        db.close()
        engine.dispose()


def test_prepared_and_approved_payroll_revisions_can_be_superseded_with_reason():
    engine, db = _db()
    try:
        prepared = models.HRPayrollRun(
            id="payroll-prepared-supersede", year=2026, month=11,
            status="prepared", created_by="preparer", revision=1,
        )
        approved = models.HRPayrollRun(
            id="payroll-approved-supersede", year=2026, month=11,
            status="approved", created_by="preparer", revision=2,
            approved_by="approver", approved_at=datetime(2026, 11, 27, tzinfo=timezone.utc),
        )
        db.add_all([prepared, approved])
        db.commit()
        actor = type("Actor", (), {"username": "payroll-admin"})()
        permission = object()
        for run_id in (prepared.id, approved.id):
            result = supersede_payroll_run(
                run_id, PayrollSupersedePayload(reason="Corrected attendance source records"),
                db, actor, permission,
            )
            assert result["status"] == "superseded"
        approved_refresh = db.get(models.HRPayrollRun, approved.id)
        assert approved_refresh.status == "superseded"
        assert approved_refresh.approved_by is None
        assert approved_refresh.approved_at is None
        assert approved_refresh.superseded_by == actor.username
        assert approved_refresh.superseded_reason == "Corrected attendance source records"
        assert approved_refresh.superseded_at is not None
    finally:
        db.close()
        engine.dispose()


def test_finalization_is_blocked_by_open_blocking_payroll_exception():
    engine, db = _db()
    try:
        run = models.HRPayrollRun(
            id="payroll-blocking-finalize", year=2026, month=11,
            status="approved", created_by="preparer", revision=1,
            approved_by="approver", approved_at=datetime(2026, 11, 27, tzinfo=timezone.utc),
        )
        db.add(run)
        db.flush()
        db.add(models.HRPayrollException(
            id="payroll-blocking-exception", payroll_run_id=run.id,
            employee_id=None, work_date=date(2026, 11, 10),
            code="attendance_summary_incomplete", severity="blocking",
            status="open", detail="Incomplete attendance source", source_reference="summary-1",
        ))
        db.commit()
        actor = type("Actor", (), {"username": "payroll-finalizer"})()
        with pytest.raises(HTTPException) as exc:
            finalize_monthly_payroll(2026, 11, db, actor, object())
        assert exc.value.status_code == 409
        assert "unresolved attendance exceptions" in exc.value.detail
        assert db.get(models.HRPayrollRun, run.id).status == "approved"
    finally:
        db.close()
        engine.dispose()
