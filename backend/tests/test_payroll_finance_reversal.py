"""Regression tests for payroll-to-Finance journal reversal."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.modules.finance.payroll_posting import post_payroll_journal, reverse_payroll_journal


def _database():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    return engine


def _seed_payroll(db: Session):
    run = models.HRPayrollRun(
        id="payroll-run-1", year=2026, month=10, revision=1,
        status="finalized", created_by="hr-preparer",
    )
    db.add(run)
    accounts = [
        models.FinanceAccount(id="salary-expense", code="6000", name="Salary expense", account_type="expense", created_by="test"),
        models.FinanceAccount(id="salary-payable", code="2100", name="Salary payable", account_type="liability", created_by="test"),
        models.FinanceAccount(id="pf-payable", code="2110", name="Employee PF payable", account_type="liability", created_by="test"),
        models.FinanceAccount(id="pt-payable", code="2120", name="Professional tax payable", account_type="liability", created_by="test"),
        models.FinanceAccount(id="tds-payable", code="2130", name="TDS payable", account_type="liability", created_by="test"),
    ]
    db.add_all(accounts)
    db.add(models.FinancePayrollAccountMapping(
        id=1, salary_expense_account_id="salary-expense",
        salary_payable_account_id="salary-payable",
        employee_pf_payable_account_id="pf-payable",
        professional_tax_payable_account_id="pt-payable",
        tds_payable_account_id="tds-payable", updated_by="test",
    ))
    db.add(models.HRPayrollItem(
        id="payroll-item-1", payroll_run_id=run.id, employee_id="employee-1",
        employee_code="EMP-001", employee_name="Test Employee", department="Operations",
        annual_salary=12000, monthly_gross=1000, basic=500, hra=200, da=0,
        conveyance=0, medical_allowance=0, special_allowance=300,
        employee_pf=120, professional_tax=20, tds=60, absence_deduction=0,
        overtime_pay=0, net_pay=800, present_days=22, half_days=0,
        absent_days=0, paid_leave_days=0, unpaid_leave_days=0, overtime_minutes=0,
    ))
    db.flush()
    return run


def test_payroll_reversal_posts_balanced_linked_opposite_journal_idempotently():
    engine = _database()
    try:
        with Session(engine) as db:
            run = _seed_payroll(db)
            original = post_payroll_journal(db, run, "hr-finalizer")
            db.commit()
            original_lines = db.query(models.FinanceJournalLine).filter_by(journal_entry_id=original.id).all()
            reversal = reverse_payroll_journal(db, run, "hr-reverser", "Correction to approved payroll")
            db.commit()
            db.refresh(reversal)
            reversal_lines = db.query(models.FinanceJournalLine).filter_by(journal_entry_id=reversal.id).all()

            assert reversal.source_type == "hr_payroll_reversal"
            assert reversal.source_id == run.id
            assert reversal.reversal_of_id == original.id
            assert reversal.status == "posted"
            assert sum(Decimal(str(line.debit)) for line in reversal_lines) == sum(Decimal(str(line.credit)) for line in original_lines)
            assert sum(Decimal(str(line.credit)) for line in reversal_lines) == sum(Decimal(str(line.debit)) for line in original_lines)
            assert {
                (line.account_id, Decimal(str(line.debit)), Decimal(str(line.credit)))
                for line in reversal_lines
            } == {
                (line.account_id, Decimal(str(line.credit)), Decimal(str(line.debit)))
                for line in original_lines
            }

            duplicate = reverse_payroll_journal(db, run, "hr-reverser", "Repeated call")
            assert duplicate.id == reversal.id
    finally:
        engine.dispose()


def test_payroll_reversal_fails_closed_when_original_journal_is_missing():
    engine = _database()
    try:
        with Session(engine) as db:
            run = models.HRPayrollRun(
                id="missing-journal-run", year=2026, month=10, revision=1,
                status="finalized", created_by="hr-preparer",
            )
            db.add(run)
            db.commit()
            with pytest.raises(ValueError, match="Original payroll Finance journal is missing"):
                reverse_payroll_journal(db, run, "hr-reverser", "Correction to approved payroll")
    finally:
        engine.dispose()
