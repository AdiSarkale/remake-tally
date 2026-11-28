"""Ephemeral SQLite backend for P0.1-11 live Playwright acceptance.

This is CI-only test infrastructure. It creates isolated control/tenant SQLite
files, seeds deterministic HR attendance data, and runs the real FastAPI app.
"""
from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("P0_11_E2E_DATA_DIR", "/tmp/nexora-p0-11-live"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONTROL_URL = f"sqlite:///{DATA_DIR / 'control.db'}"
TENANT_URL = f"sqlite:///{DATA_DIR / 'tenant.db'}"

os.environ.update({
    "ENVIRONMENT": "development",
    "DATABASE_URL": TENANT_URL,
    "CONTROL_DATABASE_URL": CONTROL_URL,
    "JWT_SECRET": "p0-11-live-e2e-secret-key-32-characters-minimum",
    "SECRET_PROVIDER": "environment",
    "TENANT_DB_REQUIRE_TLS": "false",
})

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
import uvicorn

from app import models
from app.core.security import hash_password
from app.db.control_models import ControlBase, TenantCompany
from app.db.control import get_control_db
import app.api.deps as deps
import app.api.routes.auth as auth_routes
import app.db.session as session_module
from app.main import app


control_engine = create_engine(CONTROL_URL, connect_args={"check_same_thread": False})
tenant_engine = create_engine(TENANT_URL, connect_args={"check_same_thread": False})
ControlSession = sessionmaker(bind=control_engine, autoflush=False, autocommit=False)
TenantSession = sessionmaker(bind=tenant_engine, autoflush=False, autocommit=False)
ControlBase.metadata.create_all(control_engine)
models.Base.metadata.create_all(tenant_engine)

TODAY = date.today()
EMPLOYEE_ID = "p0-11-live-employee"
SHIFT_ID = "p0-11-live-shift"
ROSTER_ID = "p0-11-live-roster"
EVENT_IN_ID = "p0-11-live-event-in"
EVENT_OUT_ID = "p0-11-live-event-out"
SUMMARY_ID = "p0-11-live-summary"
REVISION_ID = "p0-11-live-revision"
CORRECTION_ID = "p0-11-live-correction"
BREAK_ID = "p0-11-live-break"


def seed() -> None:
    control = ControlSession()
    company = control.get(TenantCompany, "p0-11-live-company")
    if company is None:
        control.add(TenantCompany(
            id="p0-11-live-company", code="P011", name="P0.1-11 Live Acceptance",
            database_secret_ref="P0_11_LIVE_TEST", active=True, provisioning_status="ready",
        ))
        control.commit()
    control.close()

    db = TenantSession()
    if db.get(models.User, "p0-11-live-admin") is None:
        db.add(models.User(
            id="p0-11-live-admin", username="admin", full_name="P0.1-11 Acceptance Admin",
            password_hash=hash_password("P0.1-11-E2E!"), role=models.Role.admin,
            active=True, must_change_password=False,
        ))
    if db.get(models.Employee, EMPLOYEE_ID) is None:
        db.add(models.Employee(
            id=EMPLOYEE_ID, emp_code="P011-001", name="P0.1-11 Live Employee",
            employee_type="staff", department="Production", designation="Operator",
            joining_date=TODAY - timedelta(days=30), active=True,
        ))
    if db.get(models.HRBranch, "p0-11-live-branch") is None:
        db.add(models.HRBranch(
            id="p0-11-live-branch", code="P011", name="Live Test Plant",
            timezone="Asia/Kolkata", active=True,
        ))
        db.add(models.EmployeeOrgAssignment(
            id="p0-11-live-org", employee_id=EMPLOYEE_ID, branch_id="p0-11-live-branch",
            department="Production", valid_from=TODAY - timedelta(days=30), created_by="admin",
        ))
    if db.get(models.HRPayrollSettings, 1) is None:
        db.add(models.HRPayrollSettings(id=1, timezone="Asia/Kolkata", week_off_days="5,6"))
    if db.get(models.HRShiftType, SHIFT_ID) is None:
        db.add(models.HRShiftType(
            id=SHIFT_ID, code="DAY", name="Day Shift", start_time=time(9), end_time=time(17),
            end_day_offset=0, active=True, created_by="admin",
        ))
    if db.get(models.HRShiftBreakRule, BREAK_ID) is None:
        db.add(models.HRShiftBreakRule(
            id=BREAK_ID, shift_type_id=SHIFT_ID, code="LUNCH", name="Lunch break",
            sequence=1, is_paid=False, planned_duration_minutes=30,
            scheduled_start_time=time(13), scheduled_end_time=time(13, 30), active=True,
        ))
    local_tz = ZoneInfo("Asia/Kolkata")
    start_utc = datetime.combine(TODAY, time(9), tzinfo=local_tz).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    end_utc = datetime.combine(TODAY, time(17), tzinfo=local_tz).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    if db.get(models.HRShiftRosterEntry, ROSTER_ID) is None:
        db.add(models.HRShiftRosterEntry(
            id=ROSTER_ID, employee_id=EMPLOYEE_ID, work_date=TODAY, status="scheduled",
            shift_type_id=SHIFT_ID, source_assignment_id=None,
            is_override=False, override_reason="", branch_id="p0-11-live-branch",
            department_snapshot="Production", timezone_name="Asia/Kolkata",
            scheduled_start_at_utc=start_utc, scheduled_end_at_utc=end_utc,
            shift_code_snapshot="DAY", shift_name_snapshot="Day Shift",
            break_rules_snapshot=[{"id": BREAK_ID, "code": "LUNCH", "name": "Lunch break", "sequence": 1, "is_paid": False, "planned_duration_minutes": 30, "scheduled_start_time": "13:00", "scheduled_end_time": "13:30"}],
            policy_version_id=None, created_by="admin",
        ))
    if db.get(models.HRAttendanceEvent, EVENT_IN_ID) is None:
        db.add(models.HRAttendanceEvent(
            id=EVENT_IN_ID, employee_id=EMPLOYEE_ID, roster_entry_id=ROSTER_ID,
            work_date=TODAY, event_type="punch_in", occurred_at_utc=start_utc,
            timezone_name="Asia/Kolkata", source_type="manual_hr",
            source_reference="p0-11-live-in", recorded_by="admin", note="Live acceptance seed",
        ))
        db.add(models.HRAttendanceEvent(
            id=EVENT_OUT_ID, employee_id=EMPLOYEE_ID, roster_entry_id=ROSTER_ID,
            work_date=TODAY, event_type="punch_out", occurred_at_utc=end_utc,
            timezone_name="Asia/Kolkata", source_type="manual_hr",
            source_reference="p0-11-live-out", recorded_by="admin", note="Live acceptance seed",
        ))
    fingerprint = "p0-11-live-summary-fingerprint-" + str(TODAY)
    if db.get(models.HRAttendanceDailySummary, SUMMARY_ID) is None:
        db.add(models.HRAttendanceDailySummary(
            id=SUMMARY_ID, employee_id=EMPLOYEE_ID, work_date=TODAY,
            current_revision=1, roster_entry_id=ROSTER_ID, timezone_name="Asia/Kolkata",
            source_event_ids=[EVENT_IN_ID, EVENT_OUT_ID], first_punch_in_utc=start_utc,
            last_punch_out_utc=end_utc, elapsed_minutes=480, paired_break_minutes=0,
            classification="complete", exception_codes=[], input_fingerprint=fingerprint,
            calculated_by="admin", calculated_at=datetime.utcnow(),
        ))
        db.add(models.HRAttendanceSummaryRevision(
            id=REVISION_ID, employee_id=EMPLOYEE_ID, work_date=TODAY, revision=1,
            roster_entry_id=ROSTER_ID, timezone_name="Asia/Kolkata",
            source_event_ids=[EVENT_IN_ID, EVENT_OUT_ID], first_punch_in_utc=start_utc,
            last_punch_out_utc=end_utc, elapsed_minutes=480, paired_break_minutes=0,
            classification="complete", exception_codes=[], input_fingerprint=fingerprint,
            calculated_by="admin", calculated_at=datetime.utcnow(),
        ))
    if db.get(models.HRAttendanceCorrectionRequest, CORRECTION_ID) is None:
        db.add(models.HRAttendanceCorrectionRequest(
            id=CORRECTION_ID, employee_id=EMPLOYEE_ID, work_date=TODAY,
            correction_kind="add", target_event_id=None, proposed_event_type="punch_out",
            proposed_at_utc=end_utc, timezone_name="Asia/Kolkata", break_rule_id=None,
            reason="Live acceptance pending correction", evidence_reference="P0.1-11-E2E",
            status="submitted", requested_by="employee",
        ))

    grants = [
        ("employees", "read"), ("shifts", "read"), ("shifts", "write"),
        ("shift_assignments", "read"), ("shift_assignments", "write"),
        ("shift_rosters", "read"), ("shift_rosters", "write"),
        ("attendance", "view"), ("attendance", "event_create"),
        ("attendance_summaries", "view"), ("attendance_summaries", "calculate"),
        ("attendance_anomalies", "view"), ("attendance_anomalies", "resolve"),
        ("attendance_anomalies", "false_positive"),
        ("attendance_corrections", "view"), ("attendance_corrections", "create"),
        ("attendance_corrections", "review"), ("overtime", "view"),
    ]
    existing = {(g.feature, g.action) for g in db.query(models.RolePermissionGrant).filter_by(role="Admin", module="hr").all()}
    for feature, action in grants:
        if (feature, action) not in existing:
            db.add(models.RolePermissionGrant(
                role="Admin", module="hr", feature=feature, action=action,
                data_scope="tenant", allowed=True, updated_by="P0.1-11-live-acceptance",
            ))
    db.commit()
    db.close()


seed()


def tenant_db_for(_company):
    return TenantSession()


deps.get_tenant_db = tenant_db_for
auth_routes.get_tenant_db = tenant_db_for
session_module.get_tenant_db = tenant_db_for


def override_control_db():
    db = ControlSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_control_db] = override_control_db

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
