"""Regression tests for append-only HR attendance events and v2 imports."""
from datetime import date, datetime, timezone
from io import BytesIO

import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.api.routes.hr_attendance_events import EmployeeSelfPunchCreate
from pydantic import ValidationError
from app.modules.hr.attendance_events import (
    AttendanceEventError,
    append_attendance_event,
    parse_event_workbook,
)


def _db():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    return engine, Session(engine)


def _employee(db):
    employee = models.Employee(
        id="attendance-employee",
        emp_code="EMP-ATT-001",
        name="Attendance Employee",
        joining_date=date(2026, 1, 1),
        active=True,
    )
    db.add(employee)
    db.add(models.HRPayrollSettings(id=1, timezone="Asia/Kolkata"))
    db.commit()
    return employee


def test_raw_event_append_is_idempotent_for_same_source_reference():
    engine, db = _db()
    try:
        employee = _employee(db)
        event, created = append_attendance_event(
            db,
            employee_id=employee.id,
            work_date=date(2026, 11, 10),
            event_type="punch_in",
            occurred_at_utc=datetime(2026, 11, 10, 3, 30),
            timezone_name="Asia/Kolkata",
            source_type="manual_hr",
            source_reference="manual-request-001",
            recorded_by="hr-user",
        )
        db.commit()
        event_id = event.id
        assert created is True

        retried, retry_created = append_attendance_event(
            db,
            employee_id=employee.id,
            work_date=date(2026, 11, 10),
            event_type="punch_in",
            occurred_at_utc=datetime(2026, 11, 10, 3, 30),
            timezone_name="Asia/Kolkata",
            source_type="manual_hr",
            source_reference="manual-request-001",
            recorded_by="hr-user",
        )
        assert retried.id == event_id
        assert retry_created is False
        assert db.query(models.HRAttendanceEvent).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_raw_event_source_reference_cannot_be_reused_for_different_fact():
    engine, db = _db()
    try:
        employee = _employee(db)
        append_attendance_event(
            db,
            employee_id=employee.id,
            work_date=date(2026, 11, 10),
            event_type="punch_in",
            occurred_at_utc=datetime(2026, 11, 10, 3, 30),
            timezone_name="Asia/Kolkata",
            source_type="manual_hr",
            source_reference="manual-request-002",
            recorded_by="hr-user",
        )
        db.commit()

        with pytest.raises(AttendanceEventError, match="different attendance event"):
            append_attendance_event(
                db,
                employee_id=employee.id,
                work_date=date(2026, 11, 10),
                event_type="punch_out",
                occurred_at_utc=datetime(2026, 11, 10, 12, 30),
                timezone_name="Asia/Kolkata",
                source_type="manual_hr",
                source_reference="manual-request-002",
                recorded_by="hr-user",
            )
        assert db.query(models.HRAttendanceEvent).count() == 1
    finally:
        db.close()
        engine.dispose()


def _event_workbook(rows, headers=None):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Attendance"
    sheet.append(headers or [
        "Employee Code", "Work Date", "Event Type", "Event DateTime (Local)",
        "Source Reference", "Break Code", "Note",
    ])
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def test_event_workbook_v2_parses_local_datetime_using_batch_timezone():
    engine, db = _db()
    try:
        employee = _employee(db)
        content = _event_workbook([[
            "EMP-ATT-001", date(2026, 11, 10), "punch_in",
            datetime(2026, 11, 10, 9, 0), "source-001", None, "Gate 1",
        ]])
        rows = parse_event_workbook(
            content,
            db=db,
            employees_by_code={employee.emp_code: employee},
            import_timezone="Asia/Kolkata",
            branch_id=None,
            file_hash="a" * 64,
        )
        assert len(rows) == 1
        assert rows[0]["event_type"] == "punch_in"
        assert rows[0]["work_date"] == date(2026, 11, 10)
        assert rows[0]["occurred_at_utc"] == datetime(2026, 11, 10, 3, 30, tzinfo=timezone.utc)
        assert rows[0]["timezone_name"] == "Asia/Kolkata"
        assert rows[0]["source_reference"] == "source-001"
        assert rows[0]["note"] == "Gate 1"
    finally:
        db.close()
        engine.dispose()


def test_event_workbook_v2_accepts_only_required_columns():
    engine, db = _db()
    try:
        employee = _employee(db)
        content = _event_workbook(
            [[
                "EMP-ATT-001", date(2026, 11, 10), "punch_in",
                datetime(2026, 11, 10, 9, 0),
            ]],
            headers=[
                "Employee Code", "Work Date", "Event Type", "Event DateTime (Local)",
            ],
        )
        rows = parse_event_workbook(
            content,
            db=db,
            employees_by_code={employee.emp_code: employee},
            import_timezone="Asia/Kolkata",
            branch_id=None,
            file_hash="d" * 64,
        )
        assert len(rows) == 1
        assert rows[0]["source_reference"]
        assert rows[0]["break_rule_id"] is None
        assert rows[0]["note"] == ""
    finally:
        db.close()
        engine.dispose()


def test_event_workbook_v2_rejects_timezone_aware_cells_and_bad_rows_atomically():
    engine, db = _db()
    try:
        employee = _employee(db)
        content = _event_workbook([
            [
                "EMP-ATT-001", date(2026, 11, 10), "punch_in",
                "2026-11-10T09:00:00+05:30", "source-aware", None, "",
            ],
            [
                "EMP-ATT-001", date(2026, 11, 10), "unknown",
                datetime(2026, 11, 10, 9, 5), "source-invalid", None, "",
            ],
        ])
        with pytest.raises(AttendanceEventError, match="validation failed"):
            parse_event_workbook(
                content,
                db=db,
                employees_by_code={employee.emp_code: employee},
                import_timezone="Asia/Kolkata",
                branch_id=None,
                file_hash="b" * 64,
            )
        assert db.query(models.HRAttendanceEvent).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_employee_self_punch_payload_rejects_client_supplied_employee_id():
    with pytest.raises(ValidationError):
        EmployeeSelfPunchCreate(
            work_date=date(2026, 11, 10),
            event_type="punch_in",
            occurred_at=datetime(2026, 11, 10, 9, 0),
            source_reference="self-punch-001",
            employee_id="some-other-employee",
        )


def test_import_batch_model_preserves_rejected_attempt_metadata():
    engine, db = _db()
    try:
        _employee(db)
        batch = models.HRAttendanceImportBatch(
            branch_id=None,
            import_timezone="Asia/Kolkata",
            template_version="event_v2",
            file_name="attendance-events.xlsx",
            file_hash="c" * 64,
            uploaded_by="hr-user",
            status="rejected",
            rows_total=2,
            rows_imported=0,
            rows_rejected=2,
            error_summary="Two invalid rows",
        )
        db.add(batch)
        db.commit()
        stored = db.get(models.HRAttendanceImportBatch, batch.id)
        assert stored.status == "rejected"
        assert stored.rows_total == 2
        assert stored.rows_imported == 0
        assert stored.rows_rejected == 2
        assert stored.file_hash == "c" * 64
    finally:
        db.close()
        engine.dispose()
