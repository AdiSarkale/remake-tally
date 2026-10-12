"""Sales domain SQLAlchemy models."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
from app.modules._base import _uuid, Role, ItemKind, EmployeeType, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseRequisitionStatus, PurchaseRequisitionSource, PurchaseOrderStatus


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid,
    )

    invoice_no: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
    )

    invoice_date: Mapped[date] = mapped_column(
        Date,
        index=True,
    )

    customer_id: Mapped[str] = mapped_column(
        ForeignKey("parties.id")
    )

    customer_name: Mapped[str] = mapped_column(
        String(160)
    )

    po_reference: Mapped[str] = mapped_column(
        String(64),
        default="",
    )

    notes: Mapped[str] = mapped_column(
        Text,
        default="",
    )

    inter_state: Mapped[bool] = mapped_column(
        Integer,
        default=0,
    )

    sub_total: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    discount_total: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    taxable_total: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    cgst: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    sgst: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    igst: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    round_off: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    grand_total: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    paid_amount: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    balance_amount: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus),
        default=InvoiceStatus.unpaid,
    )

    signature: Mapped[str] = mapped_column(
        String(64),
        index=True,
        default="",
    )

    created_by: Mapped[str] = mapped_column(
        String(64),
        default="",
    )

    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
    )

class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    product_name: Mapped[str] = mapped_column(String(160))
    hsn: Mapped[str] = mapped_column(String(16), default="")
    unit: Mapped[str] = mapped_column(String(16), default="PCS")
    quantity: Mapped[float] = mapped_column(Float)
    rate: Mapped[float] = mapped_column(Float)
    discount_percent: Mapped[float] = mapped_column(Float, default=0)
    gst_rate: Mapped[float] = mapped_column(Float, default=18)
    taxable: Mapped[float] = mapped_column(Float, default=0)
    cgst: Mapped[float] = mapped_column(Float, default=0)
    sgst: Mapped[float] = mapped_column(Float, default=0)
    igst: Mapped[float] = mapped_column(Float, default=0)
    total: Mapped[float] = mapped_column(Float, default=0)

    invoice: Mapped[Invoice] = relationship(back_populates="lines")

class Quotation(Base):
    __tablename__ = "quotations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid,
    )

    quotation_no: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
    )

    quotation_date: Mapped[date] = mapped_column(
        Date,
        index=True,
    )

    valid_until: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    customer_id: Mapped[str] = mapped_column(
        ForeignKey("parties.id"),
    )

    customer_name: Mapped[str] = mapped_column(
        String(160),
    )

    po_reference: Mapped[str] = mapped_column(
        String(64),
        default="",
    )

    notes: Mapped[str] = mapped_column(
        Text,
        default="",
    )

    inter_state: Mapped[bool] = mapped_column(
        Integer,
        default=0,
    )

    sub_total: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    discount_total: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    taxable_total: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    cgst: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    sgst: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    igst: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    round_off: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    grand_total: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    status: Mapped[QuotationStatus] = mapped_column(
        Enum(QuotationStatus),
        default=QuotationStatus.draft,
    )

    created_by: Mapped[str] = mapped_column(
        String(64),
        default="",
    )

    lines: Mapped[list["QuotationLine"]] = relationship(
        back_populates="quotation",
        cascade="all, delete-orphan",
    )

class QuotationLine(Base):
    __tablename__ = "quotation_lines"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    quotation_id: Mapped[str] = mapped_column(
        ForeignKey(
            "quotations.id",
            ondelete="CASCADE",
        )
    )

    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id"),
    )

    product_name: Mapped[str] = mapped_column(
        String(160),
    )

    hsn: Mapped[str] = mapped_column(
        String(16),
        default="",
    )

    unit: Mapped[str] = mapped_column(
        String(16),
        default="PCS",
    )

    quantity: Mapped[float] = mapped_column(
        Float,
    )

    rate: Mapped[float] = mapped_column(
        Float,
    )

    discount_percent: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    gst_rate: Mapped[float] = mapped_column(
        Float,
        default=18,
    )

    taxable: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    cgst: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    sgst: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    igst: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    total: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    quotation: Mapped[Quotation] = relationship(
        back_populates="lines",
    )

class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid,
    )

    so_no: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
    )

    order_date: Mapped[date] = mapped_column(
        Date,
        index=True,
    )

    delivery_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    customer_id: Mapped[str] = mapped_column(
        ForeignKey("parties.id"),
    )

    customer_name: Mapped[str] = mapped_column(
        String(160),
    )

    notes: Mapped[str] = mapped_column(
        Text,
        default="",
    )

    status: Mapped[SalesOrderStatus] = mapped_column(
        Enum(SalesOrderStatus),
        default=SalesOrderStatus.open,
    )

    quote_id: Mapped[str | None] = mapped_column(
        ForeignKey("quotations.id"),
        nullable=True,
        index=True,
    )

    quote_no: Mapped[str] = mapped_column(
        String(32),
        default="",
    )

    taxable_total: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    cgst: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    sgst: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    igst: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    grand_total: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    created_by: Mapped[str] = mapped_column(
        String(64),
        default="",
    )

    lines: Mapped[list["SalesOrderLine"]] = relationship(
        back_populates="sales_order",
        cascade="all, delete-orphan",
    )

class SalesOrderLine(Base):
    __tablename__ = "sales_order_lines"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    sales_order_id: Mapped[str] = mapped_column(
        ForeignKey(
            "sales_orders.id",
            ondelete="CASCADE",
        ),
    )

    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id"),
    )

    product_name: Mapped[str] = mapped_column(
        String(160),
    )

    hsn: Mapped[str] = mapped_column(
        String(16),
        default="",
    )

    unit: Mapped[str] = mapped_column(
        String(16),
        default="PCS",
    )

    quantity: Mapped[float] = mapped_column(
        Float,
    )

    rate: Mapped[float] = mapped_column(
        Float,
    )

    discount_percent: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    gst_rate: Mapped[float] = mapped_column(
        Float,
        default=18,
    )

    taxable: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    cgst: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    sgst: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    igst: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    total: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    delivered_quantity: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    sales_order: Mapped[SalesOrder] = relationship(
        back_populates="lines",
    )

class DeliveryNote(Base):
    __tablename__ = "delivery_notes"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid,
    )

    delivery_no: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
    )

    delivery_date: Mapped[date] = mapped_column(
        Date,
        index=True,
    )

    sales_order_id: Mapped[str | None] = mapped_column(
        ForeignKey("sales_orders.id"),
        nullable=True,
        index=True,
    )

    so_no: Mapped[str] = mapped_column(
        String(32),
        default="",
    )

    customer_id: Mapped[str] = mapped_column(
        ForeignKey("parties.id"),
    )

    customer_name: Mapped[str] = mapped_column(
        String(160),
    )

    vehicle_no: Mapped[str] = mapped_column(
        String(32),
        default="",
    )

    driver_name: Mapped[str] = mapped_column(
        String(120),
        default="",
    )

    lr_number: Mapped[str] = mapped_column(
        String(64),
        default="",
    )

    remarks: Mapped[str] = mapped_column(
        Text,
        default="",
    )

    created_by: Mapped[str] = mapped_column(
        String(64),
        default="",
    )

    lines: Mapped[list["DeliveryLine"]] = relationship(
        back_populates="delivery",
        cascade="all, delete-orphan",
    )

class DeliveryLine(Base):
    __tablename__ = "delivery_lines"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    delivery_id: Mapped[str] = mapped_column(
        ForeignKey(
            "delivery_notes.id",
            ondelete="CASCADE",
        ),
    )

    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id"),
    )

    product_name: Mapped[str] = mapped_column(
        String(160),
    )

    unit: Mapped[str] = mapped_column(
        String(16),
        default="PCS",
    )

    quantity: Mapped[float] = mapped_column(
        Float,
    )

    delivery: Mapped[DeliveryNote] = relationship(
        back_populates="lines",
    )

class CustomerPO(Base):
    __tablename__ = "customer_pos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    po_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    po_date: Mapped[date] = mapped_column(Date)
    customer_id: Mapped[str] = mapped_column(ForeignKey("parties.id"), index=True)
    customer_name: Mapped[str] = mapped_column(String(160))
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    lines: Mapped[list["CustomerPOLine"]] = relationship(cascade="all, delete-orphan")

class CustomerPOLine(Base):
    __tablename__ = "customer_po_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_po_id: Mapped[str] = mapped_column(ForeignKey("customer_pos.id", ondelete="CASCADE"))
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(160))
    quantity: Mapped[float] = mapped_column(Float)
    rate: Mapped[float | None] = mapped_column(Float, nullable=True)
