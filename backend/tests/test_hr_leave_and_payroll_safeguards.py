"""Regression tests for HR leave workflows and payroll state safeguards."""
import ast
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from app.api.routes.hr_payroll import _calculate_employee_monthly_payroll
from app.modules.hr.payroll_schemas import AttendanceStatus


def _employee():
    return SimpleNamespace(
        id="emp-p0", emp_code="EMP-P0", name="P0 Employee",
        department="Operations", joining_date=date(2000, 1, 1), end_date=None,
    )


def _profile():
    return SimpleNamespace(
        annual_salary=312000, basic_pct=50, hra_pct=0, da_pct=0,
        conveyance_monthly=0, medical_allowance_monthly=0,
        pf_pct=0, professional_tax_monthly=0, tds_monthly=0,
    )


def test_paid_and_unpaid_half_day_statuses_are_supported():
    assert AttendanceStatus("paid_half_day") == "paid_half_day"
    assert AttendanceStatus("unpaid_half_day") == "unpaid_half_day"


def test_paid_half_day_does_not_create_absence_deduction():
    result = _calculate_employee_monthly_payroll(
        _employee(),
        _profile(),
        [SimpleNamespace(status="paid_half_day", work_date=date(2026, 10, 1), overtime_minutes=0)],
        2026, 10, "calendar_days", 26, [5, 6], {},
    )
    assert result["paid_leave_days"] == 0.5
    assert result["unpaid_leave_days"] == 0
    assert result["absence_deduction"] == 0


def test_unpaid_half_day_deducts_half_a_day():
    result = _calculate_employee_monthly_payroll(
        _employee(),
        _profile(),
        [SimpleNamespace(status="unpaid_half_day", work_date=date(2026, 10, 1), overtime_minutes=0)],
        2026, 10, "calendar_days", 26, [5, 6], {},
    )
    assert result["unpaid_leave_days"] == 0.5
    assert float(result["absence_deduction"]) == 500


def test_payroll_api_exposes_separate_approval_lock_and_reversal_transitions():
    path = Path(__file__).resolve().parents[1] / "app" / "api" / "routes" / "hr_payroll.py"
    module = ast.parse(path.read_text(encoding="utf-8"))
    functions = {
        node.name for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "prepare_monthly_payroll" in functions
    assert "approve_monthly_payroll" in functions
    assert "finalize_monthly_payroll" in functions
    assert "lock_monthly_payroll" in functions
    assert "reverse_monthly_payroll" in functions


def test_leave_decision_does_not_allow_requestor_selected_approver():
    path = Path(__file__).resolve().parents[1] / "app" / "api" / "routes" / "hr_leave.py"
    source = path.read_text(encoding="utf-8")
    module = ast.parse(source)
    request_schema = next(
        node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "LeaveRequestIn"
    )
    fields = {
        node.target.id for node in request_schema.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert "approver_username" not in fields
    assert "approver_username=department.hod_username" in source
