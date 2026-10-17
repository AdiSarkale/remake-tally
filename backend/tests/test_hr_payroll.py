"""Tests for salary composition, calendar rules and payroll calculations."""
from datetime import date
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.routes.hr_payroll import (
    _calculate_employee_monthly_payroll,
    _calendar_type,
    _salary_count_divisor,
)
from app.modules.hr.payroll_schemas import PayrollSettingsIn


def _employee():
    return SimpleNamespace(id="emp-1", emp_code="EMP-001", name="Test Employee", department="Production")


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
        SimpleNamespace(status="absent", overtime_minutes=0),
        SimpleNamespace(status="half_day", overtime_minutes=0),
        SimpleNamespace(status="unpaid_leave", overtime_minutes=0),
        SimpleNamespace(status="paid_leave", overtime_minutes=0),
        SimpleNamespace(status="present", overtime_minutes=120),
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
