"""Finance domain SQLAlchemy models."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func, UniqueConstraint
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
