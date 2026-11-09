"""Tests for salary composition, calendar rules and payroll calculations."""
from datetime import date, time as time_type
from io import BytesIO
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from openpyxl import Workbook, load_workbook
from pydantic import ValidationError

from app.api.routes.hr_payroll import (
    _missing_payroll_attendance,
    _attendance_template_workbook,
    _calculate_employee_monthly_payroll,
    _calendar_type,
    _parse_attendance_workbook,
    _salary_count_divisor,
)
from app.modules.hr.payroll_schemas import PayrollSettingsIn

from app import models



def _employee():
    return SimpleNamespace(
        id="emp-1", emp_code="EMP-001", name="Test Employee",
        department="Production", joining_date=date(2000, 1, 1), end_date=None,
    )


def _profile():
    return SimpleNamespace(
        annual_salary=600000, basic_pct=50, hra_pct=40, da_pct=0,
        conveyance_monthly=1000, medical_allowance_monthly=1000,
        pf_pct=12, professional_tax_monthly=200, tds_monthly=500,
    )


def test_salary_breakup_sums_to_monthly_gross_and_computes_deductions():
    from app.api.routes.hr_payroll import _salary_components

    result = _salary_components(_profile())
    assert result["annual_salary"] == 600000
    assert result["monthly_gross"] == 50000
    assert result["basic"] == 25000
    assert result["hra"] == 10000
    assert result["da"] == 0
    assert result["conveyance"] == 1000
    assert result["medical_allowance"] == 1000
    assert result["special_allowance"] == 13000
    assert sum(result[key] for key in ("basic", "hra", "da", "conveyance", "medical_allowance", "special_allowance")) == result["monthly_gross"]
    assert result["employee_pf"] == 3000
    assert result["professional_tax"] == 200
    assert result["tds"] == 500


def test_absence_half_day_leave_and_overtime_affect_net_pay():
    attendance = [
        SimpleNamespace(status="absent", work_date=date(2026, 10, 1), overtime_minutes=0),
        SimpleNamespace(status="half_day", work_date=date(2026, 10, 2), overtime_minutes=0),
        SimpleNamespace(status="unpaid_leave", work_date=date(2026, 10, 5), overtime_minutes=0),
        SimpleNamespace(status="paid_leave", work_date=date(2026, 10, 6), overtime_minutes=0),
        SimpleNamespace(status="present", work_date=date(2026, 10, 7), overtime_minutes=120),
    ]
    result = _calculate_employee_monthly_payroll(
        _employee(), _profile(), attendance, 2026, 10, "fixed_days", 30, [5, 6], {}
    )
    assert result["absent_days"] == 1
    assert result["half_days"] == 1
    assert result["paid_leave_days"] == 1
    assert result["unpaid_leave_days"] == 1
    assert result["overtime_minutes"] == 120
    assert float(result["absence_deduction"]) == 4166.67
    assert float(result["overtime_pay"]) == 416.67
    assert float(result["net_pay"]) == 42550.00


def test_calendar_overrides_take_precedence_over_week_off_defaults():
    overrides = {date(2026, 10, 3): "working_day", date(2026, 10, 5): "holiday"}
    assert _calendar_type(date(2026, 10, 3), [5, 6], overrides) == "working_day"
    assert _calendar_type(date(2026, 10, 4), [5, 6], overrides) == "week_off"
    assert _calendar_type(date(2026, 10, 5), [5, 6], overrides) == "holiday"


def test_salary_count_divisor_supports_fixed_calendar_and_working_days():
    overrides = {date(2026, 10, 3): "working_day", date(2026, 10, 5): "holiday"}
    assert _salary_count_divisor(2026, 10, "calendar_days", 26, [5, 6], overrides) == 31
    assert _salary_count_divisor(2026, 10, "fixed_days", 26, [5, 6], overrides) == 26
    assert _salary_count_divisor(2026, 10, "working_days", 26, [5, 6], overrides) == 22


def test_partial_month_employment_prorates_gross_and_statutory_deductions():
    employee = SimpleNamespace(
        id="emp-join", emp_code="EMP-JOIN", name="Mid-month Joiner",
        department="Production", joining_date=date(2026, 10, 16), end_date=None,
    )
    result = _calculate_employee_monthly_payroll(
        employee, _profile(), [], 2026, 10, "calendar_days", 26, [5, 6], {}
    )
    assert result["monthly_gross"] == Decimal("25806.45")
    assert result["employee_pf"] == Decimal("1548.39")
    assert result["professional_tax"] == Decimal("103.23")
    assert result["tds"] == Decimal("258.06")
    assert result["net_pay"] == Decimal("23896.77")


def test_employment_end_date_is_inclusive_and_prorates_salary():
    employee = SimpleNamespace(
        id="emp-exit", emp_code="EMP-EXIT", name="Leaving Employee",
        department="Production", joining_date=date(2026, 10, 1), end_date=date(2026, 10, 15),
    )
    result = _calculate_employee_monthly_payroll(
        employee, _profile(), [], 2026, 10, "calendar_days", 26, [5, 6], {}
    )
    assert result["monthly_gross"] == Decimal("24193.55")
    assert result["employee_pf"] == Decimal("1451.61")
    assert result["professional_tax"] == Decimal("96.77")
    assert result["tds"] == Decimal("241.94")
    assert result["net_pay"] == Decimal("22403.23")


def test_employment_period_outside_payroll_month_has_zero_payable_gross():
    employee = SimpleNamespace(
        id="emp-ended", emp_code="EMP-ENDED", name="Former Employee",
        department="Production", joining_date=date(2026, 9, 1), end_date=date(2026, 9, 30),
    )
    result = _calculate_employee_monthly_payroll(
        employee, _profile(), [], 2026, 10, "calendar_days", 26, [5, 6], {}
    )
    assert result["monthly_gross"] == Decimal("0.00")
    assert result["net_pay"] == Decimal("0.00")


def test_attendance_counters_ignore_records_outside_employment_period():
    employee = SimpleNamespace(
        id="emp-lifecycle", emp_code="EMP-LIFE", name="Employment Window",
        department="Production", joining_date=date(2026, 10, 15), end_date=date(2026, 10, 20),
    )
    attendance = [
        SimpleNamespace(status="present", work_date=date(2026, 10, 1), overtime_minutes=100),
        SimpleNamespace(status="present", work_date=date(2026, 10, 16), overtime_minutes=30),
        SimpleNamespace(status="half_day", work_date=date(2026, 10, 17), overtime_minutes=60),
        SimpleNamespace(status="absent", work_date=date(2026, 10, 18), overtime_minutes=0),
        SimpleNamespace(status="paid_leave", work_date=date(2026, 10, 19), overtime_minutes=0),
        SimpleNamespace(status="unpaid_leave", work_date=date(2026, 10, 20), overtime_minutes=0),
        SimpleNamespace(status="paid_half_day", work_date=date(2026, 10, 21), overtime_minutes=0),
        SimpleNamespace(status="present", work_date=date(2026, 10, 25), overtime_minutes=200),
    ]

    result = _calculate_employee_monthly_payroll(
        employee, _profile(), attendance, 2026, 10, "fixed_days", 26, [5, 6], {}
    )

    assert result["present_days"] == Decimal("1.00")
    assert result["half_days"] == Decimal("1.00")
    assert result["absent_days"] == Decimal("1.00")
    assert result["paid_leave_days"] == Decimal("1.00")
    assert result["unpaid_leave_days"] == Decimal("1.00")
    assert result["overtime_minutes"] == 90


def test_unconfigured_employee_does_not_get_configured_salary():
    result = _calculate_employee_monthly_payroll(
        _employee(), None, [], 2026, 10, "fixed_days", 26, [5, 6], {}
    )
    assert result["configured"] is False
    assert result["annual_salary"] == 0
    assert result["net_pay"] == 0


def test_week_off_days_validate_and_normalize():
    assert PayrollSettingsIn(week_off_days=[6, 5]).week_off_days == [5, 6]
    with pytest.raises(ValidationError):
        PayrollSettingsIn(week_off_days=[7])
    with pytest.raises(ValidationError):
        PayrollSettingsIn(week_off_days=[6, 6])


def test_absences_on_holidays_and_week_offs_do_not_create_salary_deductions():
    from app.api.routes.hr_payroll import _calculate_employee_monthly_payroll

    attendance = [
        SimpleNamespace(status="absent", work_date=date(2026, 10, 3), overtime_minutes=0),
        SimpleNamespace(status="absent", work_date=date(2026, 10, 5), overtime_minutes=0),
        SimpleNamespace(status="absent", work_date=date(2026, 10, 6), overtime_minutes=0),
    ]
    result = _calculate_employee_monthly_payroll(
        _employee(),
        _profile(),
        attendance,
        2026,
        10,
        "fixed_days",
        26,
        [5, 6],
        {date(2026, 10, 5): "holiday"},
    )

    # The three absence records remain visible, but only the Tuesday workday
    # is deductible; October 3 is a default week-off and October 5 is a holiday.
    assert result["absent_days"] == 3
    assert result["absence_deduction"] == Decimal("1923.08")


def test_absence_deduction_cannot_exceed_monthly_gross():
    attendance = [
        SimpleNamespace(
            status="absent",
            work_date=date(2026, 10, day),
            overtime_minutes=0,
        )
        for day in range(1, 32)
    ]
    result = _calculate_employee_monthly_payroll(
        _employee(), _profile(), attendance, 2026, 10, "fixed_days", 1, [5, 6], {}
    )

    assert result["absence_deduction"] == result["monthly_gross"] == 50000
    assert result["net_pay"] == 0


@pytest.mark.parametrize(("year", "month"), [(1999, 12), (2101, 1), (2026, 0), (2026, 13)])
def test_payroll_period_validation_rejects_out_of_range_values(year, month):
    from fastapi import HTTPException

    from app.api.routes.hr_payroll import _validate_period

    with pytest.raises(HTTPException) as exc:
        _validate_period(year, month)

    assert exc.value.status_code == 422


def _attendance_workbook(rows, headers=None):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Attendance"
    sheet.append(headers or [
        "Employee Code", "Work Date", "Status", "Overtime Minutes", "Punch In", "Punch Out", "Note",
    ])
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def test_attendance_excel_template_has_exact_import_sheet_and_separate_instructions():
    content = _attendance_template_workbook(2026, 10).getvalue()
    workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    try:
        assert workbook.sheetnames == ["Attendance", "Instructions"]
        assert list(next(workbook["Attendance"].iter_rows(min_row=1, max_row=1, values_only=True))) == [
            "Employee Code", "Work Date", "Status", "Overtime Minutes", "Punch In", "Punch Out", "Note",
        ]
        # Preformatted empty rows are provided for convenience; no example data is on the import sheet.
        assert not any(any(value is not None for value in row) for row in workbook["Attendance"].iter_rows(min_row=2, values_only=True))
        assert workbook["Instructions"].max_row >= 17
    finally:
        workbook.close()


def test_attendance_excel_parser_reads_valid_rows_and_excel_times():
    workbook = _attendance_workbook([
        [" emp-001 ", date(2026, 10, 5), "Present", 30, time_type(8, 30), time_type(17, 0), "Shift A"],
        ["EMP-002", "2026-10-06", "half day", 0, None, None, ""],
    ])
    employees = {
        "EMP-001": SimpleNamespace(id="emp-1", emp_code="EMP-001", active=True),
        "EMP-002": SimpleNamespace(id="emp-2", emp_code="EMP-002", active=True),
    }
    rows = _parse_attendance_workbook(workbook, 2026, 10, employees)

    assert len(rows) == 2
    assert rows[0]["employee_id"] == "emp-1"
    assert rows[0]["status"] == "present"
    assert rows[0]["overtime_minutes"] == 30
    assert rows[0]["punch_in"].date() == date(2026, 10, 5)
    assert rows[0]["punch_in"].hour == 3
    assert rows[0]["punch_out"].hour == 11
    assert rows[0]["punch_out"].minute == 30
    assert rows[1]["status"] == "half_day"
    assert rows[1]["work_date"] == date(2026, 10, 6)


def test_attendance_excel_parser_uses_the_timezone_selected_for_each_import():
    workbook = _attendance_workbook([
        ["EMP-001", date(2026, 10, 5), "present", 0, time_type(8, 30), time_type(17, 0), ""],
    ])
    employees = {
        "EMP-001": SimpleNamespace(id="emp-1", emp_code="EMP-001", active=True),
    }

    rows = _parse_attendance_workbook(
        workbook, 2026, 10, employees, ZoneInfo("America/New_York")
    )

    # 5 October 2026 is in daylight-saving time in New York (UTC-04:00).
    assert rows[0]["punch_in"].hour == 12
    assert rows[0]["punch_in"].minute == 30
    assert rows[0]["punch_out"].hour == 21
    assert rows[0]["punch_out"].minute == 0


def test_attendance_excel_parser_rejects_entire_file_on_unknown_employee_or_bad_period():
    workbook = _attendance_workbook([
        ["EMP-001", date(2026, 10, 5), "present", 0, None, None, ""],
        ["UNKNOWN", date(2026, 10, 6), "present", 0, None, None, ""],
    ])
    employees = {"EMP-001": SimpleNamespace(id="emp-1", emp_code="EMP-001", active=True)}
    with pytest.raises(ValueError, match="not found or is inactive"):
        _parse_attendance_workbook(workbook, 2026, 10, employees)

    wrong_month = _attendance_workbook([
        ["EMP-001", date(2026, 9, 30), "present", 0, None, None, ""],
    ])
    with pytest.raises(ValueError, match="must be in 2026-10"):
        _parse_attendance_workbook(wrong_month, 2026, 10, employees)


def test_attendance_excel_parser_rejects_duplicate_employee_day_before_writing():
    workbook = _attendance_workbook([
        ["EMP-001", date(2026, 10, 5), "present", 0, None, None, ""],
        ["EMP-001", date(2026, 10, 5), "absent", 0, None, None, ""],
    ])
    employees = {"EMP-001": SimpleNamespace(id="emp-1", emp_code="EMP-001", active=True)}
    with pytest.raises(ValueError, match="duplicate Employee Code and Work Date"):
        _parse_attendance_workbook(workbook, 2026, 10, employees)


def test_attendance_excel_parser_rejects_header_changes():
    workbook = _attendance_workbook(
        [["EMP-001", date(2026, 10, 5), "present", 0, None, None, ""]],
        headers=["Employee", "Work Date", "Status", "Overtime Minutes", "Punch In", "Punch Out", "Note"],
    )
    with pytest.raises(ValueError, match="headers must match the template exactly"):
        _parse_attendance_workbook(
            workbook, 2026, 10,
            {"EMP-001": SimpleNamespace(id="emp-1", emp_code="EMP-001", active=True)},
        )




def test_payroll_readiness_requires_explicit_status_for_each_scheduled_workday():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app import models
    from app.api.routes.hr_payroll import _missing_payroll_attendance

    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    db = Session(engine)
    try:
        employee = models.Employee(
            id="salary-employee", emp_code="EMP-100", name="Salaried Employee",
            employee_type="staff", department="Accounts", designation="Executive",
            joining_date=date(2026, 11, 1),
            active=True,
        )
        db.add(employee)
        db.add(models.EmployeeSalaryProfile(employee_id=employee.id, annual_salary=600000))
        db.add(models.HRPayrollSettings(id=1, week_off_days="5,6"))
        # Monday 2 November is a holiday override; Sunday 1 November is a weekly off.
        db.add(models.HRCalendarDay(
            work_date=date(2026, 11, 2), day_type="holiday", description="Public holiday"
        ))
        db.add(models.EmployeeAttendance(
            id="attendance-1", employee_id=employee.id,
            work_date=date(2026, 11, 3), status="present",
        ))
        db.commit()

        missing, unknown_joining_dates = _missing_payroll_attendance(db, 2026, 11)

        expected = [
            date(2026, 11, day)
            for day in range(1, 31)
            if date(2026, 11, day).weekday() not in {5, 6}
            and date(2026, 11, day) != date(2026, 11, 2)
            and date(2026, 11, day) != date(2026, 11, 3)
        ]
        assert missing == [("EMP-100", work_date) for work_date in expected]
        assert unknown_joining_dates == []
        assert ("EMP-100", date(2026, 11, 1)) not in missing
        assert ("EMP-100", date(2026, 11, 2)) not in missing
    finally:
        db.close()
        engine.dispose()


def test_payroll_readiness_accepts_explicit_absence_and_leave_statuses():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app import models
    from app.api.routes.hr_payroll import _missing_payroll_attendance

    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    db = Session(engine)
    try:
        employee = models.Employee(
            id="salary-employee-2", emp_code="EMP-200", name="Salaried Employee",
            employee_type="staff", department="Accounts", designation="Executive",
            joining_date=date(2026, 11, 1), active=True,
        )
        db.add(employee)
        db.add(models.EmployeeSalaryProfile(employee_id=employee.id, annual_salary=600000))
        db.add(models.HRPayrollSettings(id=1, week_off_days="5,6"))
        for day in range(1, 31):
            work_date = date(2026, 11, day)
            if work_date.weekday() not in {5, 6}:
                db.add(models.EmployeeAttendance(
                    id=f"attendance-{day}", employee_id=employee.id,
                    work_date=work_date,
                    status="absent" if day == 4 else ("paid_leave" if day == 5 else "present"),
                ))
        db.commit()

        assert _missing_payroll_attendance(db, 2026, 11) == ([], [])
    finally:
        db.close()
        engine.dispose()



def test_unknown_joining_date_is_reported_and_full_month_attendance_is_required():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app import models

    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    db = Session(engine)
    try:
        employee = models.Employee(
            id="legacy-employee", emp_code="EMP-LEGACY", name="Legacy Employee",
            employee_type="staff", department="Accounts", designation="Analyst",
            joining_date=None, end_date=None, active=True,
        )
        db.add(employee)
        db.add(models.EmployeeSalaryProfile(employee_id=employee.id, annual_salary=600000))
        db.add(models.HRPayrollSettings(id=1, week_off_days="5,6"))
        db.commit()

        missing, unknown_joining_dates = _missing_payroll_attendance(db, 2026, 11)
        assert unknown_joining_dates == ["EMP-LEGACY"]
        assert missing
        assert all(code == "EMP-LEGACY" for code, _ in missing)
    finally:
        db.close()
        engine.dispose()


def test_monthly_attendance_is_filtered_by_historical_employee_scope():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app import models
    from app.api.routes.hr_payroll import get_monthly_attendance

    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    db = Session(engine)
    try:
        branch_a = models.HRBranch(code="A", name="Branch A", timezone="Asia/Kolkata")
        branch_b = models.HRBranch(code="B", name="Branch B", timezone="Asia/Kolkata")
        manager = models.Employee(
            id="monthly-manager", emp_code="M001", name="Manager",
            joining_date=date(2026, 1, 1), active=True,
        )
        target = models.Employee(
            id="monthly-target", emp_code="M002", name="Transferred employee",
            joining_date=date(2026, 1, 1), active=True,
        )
        user = models.User(
            id="monthly-user", username="monthly-manager", full_name="Manager",
            password_hash="test", role=models.Role.hr, active=True,
            must_change_password=False,
        )
        db.add_all([branch_a, branch_b, manager, target, user])
        db.flush()
        db.add_all([
            models.EmployeeUserLink(user_id=user.id, employee_id=manager.id, created_by="admin"),
            models.RolePermissionGrant(
                role="HR", module="hr", feature="employees", action="read",
                data_scope="branch", allowed=True, updated_by="test",
            ),
            models.RolePermissionGrant(
                role="HR", module="hr", feature="employees", action="update",
                data_scope="branch", allowed=True, updated_by="test",
            ),
            models.EmployeeOrgAssignment(
                employee_id=manager.id, branch_id=branch_a.id, department="Ops",
                valid_from=date(2026, 1, 1), created_by="admin",
            ),
            models.EmployeeOrgAssignment(
                employee_id=target.id, branch_id=branch_a.id, department="Ops",
                valid_from=date(2026, 1, 1), valid_to=date(2026, 1, 15), created_by="admin",
            ),
            models.EmployeeOrgAssignment(
                employee_id=target.id, branch_id=branch_b.id, department="Ops",
                valid_from=date(2026, 1, 16), created_by="admin",
            ),
            models.HRPayrollSettings(id=1, week_off_days="5,6", timezone="Asia/Kolkata"),
            models.EmployeeAttendance(
                employee_id=target.id, work_date=date(2026, 1, 10), status="present",
            ),
            models.EmployeeAttendance(
                employee_id=target.id, work_date=date(2026, 1, 20), status="present",
            ),
        ])
        db.commit()

        result = get_monthly_attendance(target.id, 2026, 1, db, user)

        from fastapi import HTTPException
        from app.api.routes.hr_payroll import _ensure_attendance_employee_scope

        _ensure_attendance_employee_scope(db, user, target.id, date(2026, 1, 10), "update")
        with pytest.raises(HTTPException) as outside_scope:
            _ensure_attendance_employee_scope(db, user, target.id, date(2026, 1, 20), "update")
        assert outside_scope.value.status_code == 403

        assert len(result) == 15
        assert result[0]["work_date"] == date(2026, 1, 1)
        assert result[-1]["work_date"] == date(2026, 1, 15)
    finally:
        db.close()
        engine.dispose()


def _branch_attendance_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app import models

    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    db = Session(engine)
    settings = models.HRPayrollSettings(id=1, timezone="Asia/Kolkata")
    branch_a = models.HRBranch(code="PUN", name="Pune", timezone="Asia/Kolkata", active=True)
    branch_b = models.HRBranch(code="NYC", name="New York", timezone="America/New_York", active=True)
    emp_a = models.Employee(id="tz-emp-a", emp_code="TZA", name="TZ A", joining_date=date(2026, 1, 1), active=True)
    emp_b = models.Employee(id="tz-emp-b", emp_code="TZB", name="TZ B", joining_date=date(2026, 1, 1), active=True)
    db.add_all([settings, branch_a, branch_b, emp_a, emp_b])
    db.flush()
    db.add_all([
        models.EmployeeOrgAssignment(employee_id=emp_a.id, branch_id=branch_a.id, department="Ops", valid_from=date(2026, 1, 1), created_by="test"),
        models.EmployeeOrgAssignment(employee_id=emp_b.id, branch_id=branch_b.id, department="Ops", valid_from=date(2026, 1, 1), created_by="test"),
    ])
    db.commit()
    return engine, db, branch_a, branch_b, emp_a, emp_b


def test_branch_context_resolves_effective_branch_timezone_and_tenant_fallback():
    from app.modules.hr.shift_assignment import resolve_employee_work_context

    engine, db, branch_a, branch_b, emp_a, emp_b = _branch_attendance_db()
    try:
        pune = resolve_employee_work_context(db, emp_a.id, date(2026, 4, 1))
        new_york = resolve_employee_work_context(db, emp_b.id, date(2026, 4, 1))
        assert pune.branch_id == branch_a.id
        assert pune.timezone_name == "Asia/Kolkata"
        assert new_york.branch_id == branch_b.id
        assert new_york.timezone_name == "America/New_York"

        unassigned = models.Employee(id="tz-legacy", emp_code="TZL", name="Legacy", joining_date=date(2026, 1, 1), active=True)
        db.add(unassigned)
        db.commit()
        fallback = resolve_employee_work_context(db, unassigned.id, date(2026, 4, 1))
        assert fallback.branch_id is None
        assert fallback.timezone_name == "Asia/Kolkata"
    finally:
        db.close()
        engine.dispose()


def test_branch_context_uses_effective_branch_after_employee_transfer():
    from app.modules.hr.shift_assignment import resolve_employee_work_context

    engine, db, branch_a, branch_b, emp_a, _ = _branch_attendance_db()
    try:
        first = db.query(models.EmployeeOrgAssignment).filter_by(employee_id=emp_a.id).one()
        first.valid_to = date(2026, 5, 31)
        db.add(models.EmployeeOrgAssignment(
            employee_id=emp_a.id, branch_id=branch_b.id, department="Ops",
            valid_from=date(2026, 6, 1), created_by="test",
        ))
        db.commit()

        may = resolve_employee_work_context(db, emp_a.id, date(2026, 5, 31))
        june = resolve_employee_work_context(db, emp_a.id, date(2026, 6, 1))
        assert may.branch_id == branch_a.id
        assert may.timezone_name == "Asia/Kolkata"
        assert june.branch_id == branch_b.id
        assert june.timezone_name == "America/New_York"
    finally:
        db.close()
        engine.dispose()


def test_attendance_work_date_resolves_branch_timezone_on_transfer_midnight():
    from datetime import datetime, timezone
    from app.modules.hr.shift_assignment import resolve_attendance_work_date

    engine, db, branch_a, branch_b, emp_a, _ = _branch_attendance_db()
    try:
        first = db.query(models.EmployeeOrgAssignment).filter_by(employee_id=emp_a.id).one()
        first.valid_to = date(2026, 5, 31)
        db.add(models.EmployeeOrgAssignment(
            employee_id=emp_a.id, branch_id=branch_b.id, department="Ops",
            valid_from=date(2026, 6, 1), created_by="test",
        ))
        db.commit()

        # 00:30 in New York on transfer day; UTC date/time is still early June 1.
        context, work_date = resolve_attendance_work_date(
            db, emp_a.id, datetime(2026, 6, 1, 4, 30, tzinfo=timezone.utc),
        )
        assert work_date == date(2026, 6, 1)
        assert context.branch_id == branch_b.id
        assert context.timezone_name == "America/New_York"
    finally:
        db.close()
        engine.dispose()


def test_attendance_localization_rejects_dst_gaps_and_folds():
    from datetime import datetime
    from app.modules.hr.shift_assignment import (
        ShiftAssignmentConfigurationError,
        localize_attendance_datetime,
    )

    with pytest.raises(ShiftAssignmentConfigurationError, match="does not exist"):
        localize_attendance_datetime(datetime(2026, 3, 8, 2, 30), "America/New_York")
    with pytest.raises(ShiftAssignmentConfigurationError, match="ambiguous"):
        localize_attendance_datetime(datetime(2026, 11, 1, 1, 30), "America/New_York")


def test_attendance_import_parser_rejects_multiple_branches_atomically():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app import models

    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    db = Session(engine)
    try:
        branch_a = models.HRBranch(code="A", name="A", timezone="Asia/Kolkata", active=True)
        branch_b = models.HRBranch(code="B", name="B", timezone="America/New_York", active=True)
        emp_a = models.Employee(id="multi-a", emp_code="MULTIA", name="A", joining_date=date(2026, 1, 1), active=True)
        emp_b = models.Employee(id="multi-b", emp_code="MULTIB", name="B", joining_date=date(2026, 1, 1), active=True)
        db.add_all([branch_a, branch_b, emp_a, emp_b])
        db.flush()
        db.add_all([
            models.EmployeeOrgAssignment(employee_id=emp_a.id, branch_id=branch_a.id, department="Ops", valid_from=date(2026, 1, 1), created_by="test"),
            models.EmployeeOrgAssignment(employee_id=emp_b.id, branch_id=branch_b.id, department="Ops", valid_from=date(2026, 1, 1), created_by="test"),
        ])
        db.commit()
        workbook = _attendance_workbook([
            ["MULTIA", date(2026, 10, 5), "present", 0, time_type(8, 30), time_type(17, 0), ""],
            ["MULTIB", date(2026, 10, 5), "present", 0, time_type(8, 30), time_type(17, 0), ""],
        ])
        with pytest.raises(ValueError, match="multiple branches"):
            _parse_attendance_workbook(
                workbook, 2026, 10,
                {"MULTIA": emp_a, "MULTIB": emp_b},
                ZoneInfo("Asia/Kolkata"), db=db, branch_id=None,
            )
    finally:
        db.close()
        engine.dispose()


def test_manual_attendance_work_date_uses_previous_overnight_roster_day():
    from datetime import datetime, timezone
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app import models
    from app.modules.hr.shift_assignment import resolve_attendance_work_date

    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    db = Session(engine)
    try:
        branch = models.HRBranch(code="NIGHT2", name="Night Branch", timezone="Asia/Kolkata", active=True)
        employee = models.Employee(id="night-transfer-employee", emp_code="NT001", name="Night", joining_date=date(2040, 1, 1), active=True)
        db.add_all([branch, employee])
        db.flush()
        db.add(models.EmployeeOrgAssignment(
            employee_id=employee.id, branch_id=branch.id, department="Ops",
            valid_from=date(2040, 1, 1), created_by="test",
        ))
        shift = models.HRShiftType(
            code="NIGHT", name="Night", start_time=time_type(22, 0),
            end_time=time_type(6, 0), end_day_offset=1, active=True, created_by="test",
        )
        db.add(shift)
        db.flush()
        assignment = models.HRShiftAssignment(
            scope_type="employee", employee_id=employee.id, branch_id=branch.id,
            shift_type_id=shift.id, weekdays=[0, 1, 2, 3, 4, 5, 6],
            valid_from=date(2040, 1, 1), created_by="test",
        )
        db.add(assignment)
        db.commit()
        from app.modules.hr.shift_roster_generation import generate_shift_roster
        generate_shift_roster(
            db, start_date=date(2040, 1, 2), end_date=date(2040, 1, 2),
            employee_ids=[employee.id], created_by="test",
        )
        # 06:00 IST on 3 January is 00:30 UTC and remains in the 2 January shift.
        context, work_date = resolve_attendance_work_date(
            db, employee.id, datetime(2040, 1, 3, 0, 30, tzinfo=timezone.utc),
        )
        assert work_date == date(2040, 1, 2)
        assert context.branch_id == branch.id
        assert context.timezone_name == "Asia/Kolkata"
    finally:
        db.close()
        engine.dispose()


def test_overnight_legacy_import_requires_scheduled_overnight_shift():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app import models

    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    db = Session(engine)
    try:
        branch = models.HRBranch(code="NIGHT", name="Night", timezone="Asia/Kolkata", active=True)
        employee = models.Employee(id="night-employee", emp_code="NIGHT001", name="Night", joining_date=date(2026, 1, 1), active=True)
        db.add_all([branch, employee])
        db.flush()
        db.add(models.EmployeeOrgAssignment(employee_id=employee.id, branch_id=branch.id, department="Ops", valid_from=date(2026, 1, 1), created_by="test"))
        db.commit()
        workbook = _attendance_workbook([
            ["NIGHT001", date(2026, 10, 5), "present", 0, time_type(22, 0), time_type(6, 0), ""],
        ])
        with pytest.raises(ValueError, match="scheduled overnight shift"):
            _parse_attendance_workbook(
                workbook, 2026, 10, {"NIGHT001": employee},
                ZoneInfo("Asia/Kolkata"), db=db, branch_id=branch.id, allow_overnight=True,
            )
    finally:
        db.close()
        engine.dispose()

def test_overnight_event_uses_shift_start_work_date_across_midnight():
    from datetime import datetime, timezone
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app import models
    from app.modules.hr.shift_assignment import resolve_attendance_work_date

    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    db = Session(engine)
    try:
        branch = models.HRBranch(code="NGT", name="Night", timezone="Asia/Kolkata", active=True)
        employee = models.Employee(
            id="ngt-employee", emp_code="NGT001", name="Night Worker",
            joining_date=date(2040, 1, 1), active=True,
        )
        shift = models.HRShiftType(
            id="ngt-shift", code="NGT", name="Night Shift",
            start_time=time_type(22, 0), end_time=time_type(6, 0),
            end_day_offset=1, active=True, created_by="test",
        )
        db.add_all([branch, employee, shift, models.HRPayrollSettings(id=1, timezone="Asia/Kolkata")])
        db.flush()
        db.add_all([
            models.EmployeeOrgAssignment(
                employee_id=employee.id, branch_id=branch.id, department="Ops",
                valid_from=date(2040, 1, 1), created_by="test",
            ),
            models.HRShiftAssignment(
                id="ngt-assignment", scope_type="employee", employee_id=employee.id,
                branch_id=branch.id, department=None, shift_type_id=shift.id,
                weekdays=[0, 1, 2, 3, 4, 5, 6], valid_from=date(2040, 1, 1),
                valid_to=None, created_by="test",
            ),
        ])
        db.commit()
        from app.modules.hr.shift_assignment import resolve_shift_window
        start_utc, end_utc = resolve_shift_window(date(2040, 1, 2), shift, "Asia/Kolkata")
        db.add(models.HRShiftRosterEntry(
            employee_id=employee.id, work_date=date(2040, 1, 2), status="scheduled",
            shift_type_id=shift.id, source_assignment_id="ngt-assignment",
            is_override=False, override_reason="", branch_id=branch.id,
            department_snapshot="Ops", timezone_name="Asia/Kolkata",
            scheduled_start_at_utc=start_utc, scheduled_end_at_utc=end_utc,
            shift_code_snapshot="NGT", shift_name_snapshot="Night Shift",
            break_rules_snapshot=[], created_by="test",
        ))
        db.commit()
        # 03:00 IST on 3 January remains attached to 2 January's shift.
        context, work_date = resolve_attendance_work_date(
            db, employee.id, datetime(2040, 1, 2, 21, 30, tzinfo=timezone.utc),
        )
        assert work_date == date(2040, 1, 2)
        assert context.branch_id == branch.id
        assert context.timezone_name == "Asia/Kolkata"
    finally:
        db.close()
        engine.dispose()

def test_branch_timezone_import_normalizes_local_times_and_snapshots_context():
    engine, db, branch_a, _, emp_a, _ = _branch_attendance_db()
    try:
        workbook = _attendance_workbook([
            ["TZA", date(2026, 10, 5), "present", 0, time_type(8, 30), time_type(17, 0), ""],
        ])
        rows = _parse_attendance_workbook(
            workbook, 2026, 10, {"TZA": emp_a},
            ZoneInfo("Asia/Kolkata"), db=db, branch_id=branch_a.id,
        )
        assert len(rows) == 1
        assert rows[0]["branch_id"] == branch_a.id
        assert rows[0]["timezone_name"] == "Asia/Kolkata"
        assert rows[0]["punch_in"].hour == 3
        assert rows[0]["punch_in"].minute == 0
        assert rows[0]["punch_out"].hour == 11
        assert rows[0]["punch_out"].minute == 30
    finally:
        db.close()
        engine.dispose()


def test_import_rejects_wrong_selected_branch_for_employee_work_date():
    engine, db, branch_a, branch_b, emp_a, _ = _branch_attendance_db()
    try:
        workbook = _attendance_workbook([
            ["TZA", date(2026, 10, 5), "present", 0, time_type(8, 30), time_type(17, 0), ""],
        ])
        with pytest.raises(ValueError, match="not assigned to the selected branch"):
            _parse_attendance_workbook(
                workbook, 2026, 10, {"TZA": emp_a},
                ZoneInfo("Asia/Kolkata"), db=db, branch_id=branch_b.id,
            )
    finally:
        db.close()
        engine.dispose()

