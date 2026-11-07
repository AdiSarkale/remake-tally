"""Finance domain SQLAlchemy models."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
from app.modules._base import _uuid, Role, ItemKind, EmployeeType, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseRequisitionStatus, PurchaseRequisitionSource, PurchaseOrderStatus


class CustomerPayment(Base):
    """Actual money received from a customer."""

    __tablename__ = "customer_payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    payment_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    payment_date: Mapped[date] = mapped_column(Date, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("parties.id"), index=True)
    customer_name: Mapped[str] = mapped_column(String(160))
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("invoices.id"), nullable=True, index=True)
    invoice_no: Mapped[str] = mapped_column(String(32), default="")
    amount: Mapped[float] = mapped_column(Float)
    mode: Mapped[str] = mapped_column(String(32), default="Bank Transfer")
    reference: Mapped[str] = mapped_column(String(64), default="")
    remarks: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class SupplierPayment(Base):
    """Actual money paid to a supplier."""

    __tablename__ = "supplier_payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    payment_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    payment_date: Mapped[date] = mapped_column(Date, index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("parties.id"), index=True)
    supplier_name: Mapped[str] = mapped_column(String(160))
    purchase_order_id: Mapped[str | None] = mapped_column(ForeignKey("purchase_orders.id"), nullable=True, index=True)
    po_no: Mapped[str] = mapped_column(String(32), default="")
    amount: Mapped[float] = mapped_column(Float)
    mode: Mapped[str] = mapped_column(String(32), default="Bank Transfer")
    reference: Mapped[str] = mapped_column(String(64), default="")
    remarks: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinanceAccount(Base):
    """Tenant chart-of-accounts entry used by the finance journal."""

    __tablename__ = "finance_accounts"
    __table_args__ = (UniqueConstraint("code", name="uq_finance_account_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[str] = mapped_column(String(24), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    system_account: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FinanceJournalEntry(Base):
    """Immutable, balanced general-ledger journal header."""

    __tablename__ = "finance_journal_entries"
    __table_args__ = (
        UniqueConstraint("journal_no", name="uq_finance_journal_no"),
        UniqueConstraint("source_type", "source_id", name="uq_finance_journal_source"),
        UniqueConstraint("reversal_of_id", name="uq_finance_journal_reversal"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    journal_no: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    narration: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="posted")
    reversal_of_id: Mapped[str | None] = mapped_column(ForeignKey("finance_journal_entries.id"), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FinanceJournalLine(Base):
    """Immutable debit/credit line belonging to one journal entry."""

    __tablename__ = "finance_journal_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    journal_entry_id: Mapped[str] = mapped_column(ForeignKey("finance_journal_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("finance_accounts.id"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    debit: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    credit: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)


class FinancePayrollAccountMapping(Base):
    """Tenant mapping from payroll components to ledger accounts."""

    __tablename__ = "finance_payroll_account_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    salary_expense_account_id: Mapped[str] = mapped_column(ForeignKey("finance_accounts.id"), nullable=False)
    salary_payable_account_id: Mapped[str] = mapped_column(ForeignKey("finance_accounts.id"), nullable=False)
    employee_pf_payable_account_id: Mapped[str] = mapped_column(ForeignKey("finance_accounts.id"), nullable=False)
    professional_tax_payable_account_id: Mapped[str] = mapped_column(ForeignKey("finance_accounts.id"), nullable=False)
    tds_payable_account_id: Mapped[str] = mapped_column(ForeignKey("finance_accounts.id"), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
