"""Balanced, idempotent Finance journal posting for approved HR payroll."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session

from app import models


CENT = Decimal("0.01")


def _amount(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def post_payroll_journal(db: Session, run: models.HRPayrollRun, username: str) -> models.FinanceJournalEntry:
    existing = db.query(models.FinanceJournalEntry).filter_by(
        source_type="hr_payroll", source_id=run.id,
    ).first()
    if existing is not None:
        return existing

    mapping = db.get(models.FinancePayrollAccountMapping, 1)
    if mapping is None:
        raise ValueError("Configure Finance payroll account mapping before finalizing payroll")
    account_ids = [
        mapping.salary_expense_account_id, mapping.salary_payable_account_id,
        mapping.employee_pf_payable_account_id, mapping.professional_tax_payable_account_id,
        mapping.tds_payable_account_id,
    ]
    accounts = {row.id: row for row in db.query(models.FinanceAccount).filter(
        models.FinanceAccount.id.in_(account_ids), models.FinanceAccount.active.is_(True)
    ).all()}
    if len(accounts) != len(set(account_ids)):
        raise ValueError("One or more mapped Finance payroll accounts are missing or inactive")
    if accounts[mapping.salary_expense_account_id].account_type != "expense":
        raise ValueError("Salary expense mapping must point to an expense account")
    for account_id in account_ids[1:]:
        if accounts[account_id].account_type != "liability":
            raise ValueError("Payroll payable mappings must point to liability accounts")

    items = db.query(models.HRPayrollItem).filter_by(payroll_run_id=run.id).all()
    if not items:
        raise ValueError("Cannot post a payroll journal without payroll items")
    gross = sum((_amount(row.monthly_gross) - _amount(row.absence_deduction) + _amount(row.overtime_pay) for row in items), Decimal("0.00"))
    net = sum((_amount(row.net_pay) for row in items), Decimal("0.00"))
    pf = sum((_amount(row.employee_pf) for row in items), Decimal("0.00"))
    pt = sum((_amount(row.professional_tax) for row in items), Decimal("0.00"))
    tds = sum((_amount(row.tds) for row in items), Decimal("0.00"))
    if min(gross, net, pf, pt, tds) < 0:
        raise ValueError("Payroll journal contains a negative component; correct payroll before finalization")
    if abs(gross - net - pf - pt - tds) > CENT:
        raise ValueError(
            f"Payroll does not reconcile: gross {gross} != net {net} + PF {pf} + PT {pt} + TDS {tds}"
        )

    journal = models.FinanceJournalEntry(
        journal_no=f"PAY-{run.year}{run.month:02d}-R{run.revision}",
        entry_date=date(run.year, run.month, __import__("calendar").monthrange(run.year, run.month)[1]),
        narration=f"Payroll expense and employee deductions for {run.year}-{run.month:02d}, revision {run.revision}",
        source_type="hr_payroll", source_id=run.id, status="posted", created_by=username,
    )
    db.add(journal)
    db.flush()
    lines = [
        (mapping.salary_expense_account_id, "Gross salary expense", gross, Decimal("0.00")),
        (mapping.salary_payable_account_id, "Net salaries payable", Decimal("0.00"), net),
        (mapping.employee_pf_payable_account_id, "Employee PF payable", Decimal("0.00"), pf),
        (mapping.professional_tax_payable_account_id, "Professional tax payable", Decimal("0.00"), pt),
        (mapping.tds_payable_account_id, "Salary TDS payable", Decimal("0.00"), tds),
    ]
    for account_id, description, debit, credit in lines:
        if debit == 0 and credit == 0:
            continue
        db.add(models.FinanceJournalLine(
            journal_entry_id=journal.id, account_id=account_id,
            description=description, debit=debit, credit=credit,
        ))
    return journal


def reverse_payroll_journal(
    db: Session, run: models.HRPayrollRun, username: str, reason: str,
) -> models.FinanceJournalEntry:
    existing = db.query(models.FinanceJournalEntry).filter_by(
        source_type="hr_payroll_reversal", source_id=run.id,
    ).first()
    if existing is not None:
        return existing
    original = db.query(models.FinanceJournalEntry).filter_by(
        source_type="hr_payroll", source_id=run.id,
    ).with_for_update().first()
    if original is None:
        raise ValueError("Original payroll Finance journal is missing; payroll cannot be reversed in isolation")
    if original.status != "posted":
        raise ValueError("Original payroll Finance journal is not posted")
    original_lines = db.query(models.FinanceJournalLine).filter_by(journal_entry_id=original.id).all()
    if not original_lines:
        raise ValueError("Original payroll Finance journal has no lines")
    journal = models.FinanceJournalEntry(
        journal_no=f"{original.journal_no}-REV",
        entry_date=date.today(),
        narration=f"Reversal of {original.journal_no}: {reason}",
        source_type="hr_payroll_reversal", source_id=run.id,
        status="posted", reversal_of_id=original.id, created_by=username,
    )
    db.add(journal)
    db.flush()
    for line in original_lines:
        db.add(models.FinanceJournalLine(
            journal_entry_id=journal.id, account_id=line.account_id,
            description=f"Reversal: {line.description}",
            debit=line.credit, credit=line.debit,
        ))
    return journal
