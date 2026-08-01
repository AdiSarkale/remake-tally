"""ORM models for the MiniTally ERP domain."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Role(str, enum.Enum):
    admin = "Admin"
    accountant = "Accountant"
    operator = "Operator"


class ItemKind(str, enum.Enum):
    product = "product"
    material = "material"
    scrap = "scrap"


class MovementType(str, enum.Enum):
    IN = "IN"
    OUT = "OUT"
    ADJUST = "ADJUST"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.operator)
    email: Mapped[str] = mapped_column(String(160), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Party(Base):
    """Customers and suppliers share one table, split by `kind`."""

    __tablename__ = "parties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(16), index=True)  # customer | supplier
    name: Mapped[str] = mapped_column(String(160), index=True)
    gst_number: Mapped[str] = mapped_column(String(32), default="")
    phone: Mapped[str] = mapped_column(String(32), default="")
    email: Mapped[str] = mapped_column(String(160), default="")
    address: Mapped[str] = mapped_column(Text, default="")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    unit: Mapped[str] = mapped_column(String(16), default="PCS")
    hsn: Mapped[str] = mapped_column(String(16), default="")
    cost_price: Mapped[float] = mapped_column(Float, default=0)
    selling_price: Mapped[float] = mapped_column(Float, default=0)
    gst_rate: Mapped[float] = mapped_column(Float, default=18)
    stock: Mapped[float] = mapped_column(Float, default=0)
    min_stock: Mapped[float] = mapped_column(Float, default=0)


class RawMaterial(Base):
    __tablename__ = "raw_materials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(160), index=True)
    unit: Mapped[str] = mapped_column(String(16), default="KG")
    cost: Mapped[float] = mapped_column(Float, default=0)
    stock: Mapped[float] = mapped_column(Float, default=0)
    min_stock: Mapped[float] = mapped_column(Float, default=0)


class ScrapType(Base):
    __tablename__ = "scrap_types"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(160), index=True)
    unit: Mapped[str] = mapped_column(String(16), default="KG")
    selling_rate: Mapped[float] = mapped_column(Float, default=0)
    stock: Mapped[float] = mapped_column(Float, default=0)


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    item_kind: Mapped[ItemKind] = mapped_column(Enum(ItemKind), index=True)
    item_id: Mapped[str] = mapped_column(String(36), index=True)
    item_name: Mapped[str] = mapped_column(String(160))
    movement_type: Mapped[MovementType] = mapped_column(Enum(MovementType))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    balance: Mapped[float] = mapped_column(Float)
    reference: Mapped[str] = mapped_column(String(64), default="")
    reason: Mapped[str] = mapped_column(String(255), default="")
    user_id: Mapped[str] = mapped_column(String(36), default="")


class ProductionEntry(Base):
    __tablename__ = "production_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[float] = mapped_column(Float)
    machine: Mapped[str] = mapped_column(String(64), default="")
    operator: Mapped[str] = mapped_column(String(120), default="")
    shift: Mapped[str] = mapped_column(String(4), default="A")
    remarks: Mapped[str] = mapped_column(Text, default="")

    consumption: Mapped[list["ProductionConsumption"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )


class ProductionConsumption(Base):
    __tablename__ = "production_consumption"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    production_id: Mapped[str] = mapped_column(ForeignKey("production_entries.id", ondelete="CASCADE"))
    material_id: Mapped[str] = mapped_column(ForeignKey("raw_materials.id"))
    quantity: Mapped[float] = mapped_column(Float)

    entry: Mapped[ProductionEntry] = relationship(back_populates="consumption")


class ScrapEntry(Base):
    __tablename__ = "scrap_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    batch_no: Mapped[str] = mapped_column(String(32), default="")
    scrap_type_id: Mapped[str] = mapped_column(ForeignKey("scrap_types.id"))
    quantity: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(120), default="")
    remarks: Mapped[str] = mapped_column(Text, default="")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    username: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32))
    entity: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(Text, default="")


class CompanySettings(Base):
    __tablename__ = "company_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    name: Mapped[str] = mapped_column(String(160), default="MiniTally Manufacturing")
    gst_number: Mapped[str] = mapped_column(String(32), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    invoice_prefix: Mapped[str] = mapped_column(String(16), default="INV")
    financial_year: Mapped[str] = mapped_column(String(16), default="2026-2027")


class InvoiceStatus(str, enum.Enum):
    unpaid = "Unpaid"
    paid = "Paid"
    cancelled = "Cancelled"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    invoice_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    invoice_date: Mapped[date] = mapped_column(Date, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("parties.id"))
    customer_name: Mapped[str] = mapped_column(String(160))
    po_reference: Mapped[str] = mapped_column(String(64), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    inter_state: Mapped[bool] = mapped_column(Integer, default=0)
    sub_total: Mapped[float] = mapped_column(Float, default=0)
    discount_total: Mapped[float] = mapped_column(Float, default=0)
    taxable_total: Mapped[float] = mapped_column(Float, default=0)
    cgst: Mapped[float] = mapped_column(Float, default=0)
    sgst: Mapped[float] = mapped_column(Float, default=0)
    igst: Mapped[float] = mapped_column(Float, default=0)
    round_off: Mapped[float] = mapped_column(Float, default=0)
    grand_total: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.unpaid)
    signature: Mapped[str] = mapped_column(String(64), index=True, default="")
    created_by: Mapped[str] = mapped_column(String(64), default="")

    lines: Mapped[list["InvoiceLine"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


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
