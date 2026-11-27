"""P0.1-10 daily source provenance and approved overtime integration tests."""
from datetime import date, datetime, time, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.modules.hr.payroll_integration import build_payroll_daily_inputs


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
