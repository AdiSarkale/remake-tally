"""Add a minimal immutable finance journal and payroll account mapping.

Revision ID: p0_finance_journal_014
Revises: p0_leave_accrual_013
"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = "p0_finance_journal_014"
down_revision = "p0_leave_accrual_013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finance_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("account_type", sa.String(24), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("system_account", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_finance_account_code"),
    )
    op.create_index("ix_finance_accounts_code", "finance_accounts", ["code"])
    op.create_table(
        "finance_journal_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("journal_no", sa.String(64), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("narration", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="posted"),
        sa.Column("reversal_of_id", sa.String(36), sa.ForeignKey("finance_journal_entries.id"), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("journal_no", name="uq_finance_journal_no"),
        sa.UniqueConstraint("source_type", "source_id", name="uq_finance_journal_source"),
        sa.UniqueConstraint("reversal_of_id", name="uq_finance_journal_reversal"),
    )
    for col in ("journal_no", "entry_date"):
        op.create_index(f"ix_finance_journal_entries_{col}", "finance_journal_entries", [col])
    op.create_table(
        "finance_journal_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("journal_entry_id", sa.String(36), sa.ForeignKey("finance_journal_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("finance_accounts.id"), nullable=False),
        sa.Column("description", sa.String(240), nullable=False, server_default=""),
        sa.Column("debit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_finance_journal_lines_journal_entry_id", "finance_journal_lines", ["journal_entry_id"])
    op.create_index("ix_finance_journal_lines_account_id", "finance_journal_lines", ["account_id"])
    op.create_table(
        "finance_payroll_account_mapping",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("salary_expense_account_id", sa.String(36), sa.ForeignKey("finance_accounts.id"), nullable=False),
        sa.Column("salary_payable_account_id", sa.String(36), sa.ForeignKey("finance_accounts.id"), nullable=False),
        sa.Column("employee_pf_payable_account_id", sa.String(36), sa.ForeignKey("finance_accounts.id"), nullable=False),
        sa.Column("professional_tax_payable_account_id", sa.String(36), sa.ForeignKey("finance_accounts.id"), nullable=False),
        sa.Column("tds_payable_account_id", sa.String(36), sa.ForeignKey("finance_accounts.id"), nullable=False),
        sa.Column("updated_by", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    accounts = [
        ("5100", "Salaries and Wages Expense", "expense"),
        ("2100", "Net Salaries Payable", "liability"),
        ("2110", "Employee Provident Fund Payable", "liability"),
        ("2120", "Professional Tax Payable", "liability"),
        ("2130", "Salary TDS Payable", "liability"),
    ]
    ids = {code: str(uuid.uuid4()) for code, _, _ in accounts}
    account_table = sa.table(
        "finance_accounts",
        sa.column("id", sa.String(36)), sa.column("code", sa.String(32)),
        sa.column("name", sa.String(120)), sa.column("account_type", sa.String(24)),
        sa.column("active", sa.Boolean()), sa.column("system_account", sa.Boolean()),
        sa.column("created_by", sa.String(64)),
    )
    op.bulk_insert(account_table, [
        {"id": ids[code], "code": code, "name": name, "account_type": kind,
         "active": True, "system_account": True, "created_by": "system"}
        for code, name, kind in accounts
    ])
    mapping_table = sa.table(
        "finance_payroll_account_mapping",
        sa.column("id", sa.Integer()),
        sa.column("salary_expense_account_id", sa.String(36)),
        sa.column("salary_payable_account_id", sa.String(36)),
        sa.column("employee_pf_payable_account_id", sa.String(36)),
        sa.column("professional_tax_payable_account_id", sa.String(36)),
        sa.column("tds_payable_account_id", sa.String(36)),
        sa.column("updated_by", sa.String(64)),
    )
    op.bulk_insert(mapping_table, [{
        "id": 1,
        "salary_expense_account_id": ids["5100"],
        "salary_payable_account_id": ids["2100"],
        "employee_pf_payable_account_id": ids["2110"],
        "professional_tax_payable_account_id": ids["2120"],
        "tds_payable_account_id": ids["2130"],
        "updated_by": "system",
    }])


def downgrade() -> None:
    op.drop_table("finance_payroll_account_mapping")
    op.drop_index("ix_finance_journal_lines_account_id", table_name="finance_journal_lines")
    op.drop_index("ix_finance_journal_lines_journal_entry_id", table_name="finance_journal_lines")
    op.drop_table("finance_journal_lines")
    op.drop_index("ix_finance_journal_entries_entry_date", table_name="finance_journal_entries")
    op.drop_index("ix_finance_journal_entries_journal_no", table_name="finance_journal_entries")
    op.drop_table("finance_journal_entries")
    op.drop_index("ix_finance_accounts_code", table_name="finance_accounts")
    op.drop_table("finance_accounts")
