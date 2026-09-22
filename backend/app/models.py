"""ORM models for the MiniTally ERP domain."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func, UniqueConstraint
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
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    unit: Mapped[str] = mapped_column(String(16), default="KG")
    cost: Mapped[float] = mapped_column(Float, default=0)
    stock: Mapped[float] = mapped_column(Float, default=0)
    min_stock: Mapped[float] = mapped_column(Float, default=0)

class BillOfMaterials(Base):
    __tablename__ = "bill_of_materials"
    __table_args__ = (
        UniqueConstraint("product_id", "version", name="uq_bom_product_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean,default=True)
    expected_scrap_percent: Mapped[float] = mapped_column(Float, default=0)
    scrap_type_id: Mapped[str | None] = mapped_column(
        ForeignKey("scrap_types.id"),
        nullable=True
    )

    lines : Mapped[list['BomLine']] = relationship(
        back_populates='bom',
        cascade='all, delete-orphan')

class BomLine(Base):
    __tablename__ = 'bom_lines'
    id: Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=True)

    bom_id : Mapped[str] = mapped_column(ForeignKey('bill_of_materials.id', ondelete='CASCADE'),index=True)

    material_id: Mapped[str] = mapped_column(ForeignKey('raw_materials.id'), index=True)
    quantity: Mapped[float] = mapped_column(Float)

    bom: Mapped[BillOfMaterials] = relationship(back_populates='lines')

class ScrapType(Base):
    __tablename__ = "scrap_types"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    unit: Mapped[str] = mapped_column(String(16), default="KG")
    selling_rate: Mapped[float] = mapped_column(Float, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    stock: Mapped[float] = mapped_column(Float, default=0, nullable=True)
    min_stock: Mapped[float] = mapped_column(Float, default=0, nullable=True)


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
    actual_scrap: Mapped[float] = mapped_column(
    Float,
    default=0
    )

    scrap_type_id: Mapped[str | None] = mapped_column(
        ForeignKey("scrap_types.id"),
        nullable=True
    )

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
    gst_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_prefix: Mapped[str] = mapped_column(String(16), default="INV")
    financial_year: Mapped[str] = mapped_column(String(16), default="2026-2027")


class InvoiceStatus(str, enum.Enum):
    unpaid = "Unpaid"
    paid = "Paid"
    cancelled = "Cancelled"
    partial = 'Partial'


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

class QuotationStatus(str, enum.Enum):
    draft = 'Draft'
    sent = 'Sent'
    accepted = 'Accepted'
    rejected = 'Rejected'
    expired = 'Expired'
    converted = 'Converted'


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




class SalesOrderStatus(str, enum.Enum):
    open = "Open"
    partially_delivered = "Partially Delivered"
    delivered = "Delivered"
    invoiced = "Invoiced"
    cancelled = "Cancelled"


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

class DispatchStatus(str, enum.Enum):
    planned = "Planned"
    loading = "Loading"
    in_transit = "In Transit"
    delivered = "Delivered"
    delayed = "Delayed"


class Dispatch(Base):
    __table_args__ = (
    UniqueConstraint(
        "delivery_id",
        name="uq_dispatch_delivery",
    ),
)
    __tablename__ = "dispatches"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid,
    )

    dispatch_no: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
    )

    dispatch_date: Mapped[date] = mapped_column(
        Date,
        index=True,
    )

    delivery_id: Mapped[str | None] = mapped_column(
        ForeignKey("delivery_notes.id"),
        nullable=True,
    )

    delivery_no: Mapped[str] = mapped_column(
        String(32),
        default="",
    )

    customer_id: Mapped[str] = mapped_column(
        ForeignKey("parties.id"),
    )

    customer_name: Mapped[str] = mapped_column(
        String(160),
    )

    transporter: Mapped[str] = mapped_column(
        String(160),
        default="",
    )

    vehicle_no: Mapped[str] = mapped_column(
        String(32),
        default="",
    )

    driver_name: Mapped[str] = mapped_column(
        String(120),
        default="",
    )

    driver_phone: Mapped[str] = mapped_column(
        String(32),
        default="",
    )

    lr_number: Mapped[str] = mapped_column(
        String(64),
        default="",
    )

    status: Mapped[DispatchStatus] = mapped_column(
        Enum(DispatchStatus),
        default=DispatchStatus.planned,
    )

    delivered_on: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    pod_ref: Mapped[str] = mapped_column(
        String(160),
        default="",
    )

    created_by: Mapped[str] = mapped_column(
        String(64),
        default="",
    )


class PurchaseOrderStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    partially_received = "partially_received"
    received = "received"


class SupplierProduct(Base):
    __tablename__ = "supplier_products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("parties.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("raw_materials.id"))
    supplier_code: Mapped[str] = mapped_column(String(64))
    purchase_rate: Mapped[float] = mapped_column(Float)
    minimum_order_qty: Mapped[float] = mapped_column(Float)
    lead_time_days: Mapped[int] = mapped_column(Integer)


class Plant(Base):
    __tablename__ = "plants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    location: Mapped[str] = mapped_column(String(160))
    active: Mapped[bool] = mapped_column(Boolean)


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), index=True)
    active: Mapped[bool] = mapped_column(Boolean)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    po_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    po_date: Mapped[date] = mapped_column(Date, index=True)
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("parties.id"))
    supplier_name: Mapped[str] = mapped_column(String(160))
    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    notes: Mapped[str] = mapped_column(Text)
    status: Mapped[PurchaseOrderStatus] = mapped_column(Enum(PurchaseOrderStatus))
    sub_total: Mapped[float] = mapped_column(Float)
    gst_total: Mapped[float] = mapped_column(Float)
    grand_total: Mapped[float] = mapped_column(Float)
    created_by: Mapped[str] = mapped_column(String(64))
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(cascade="all, delete-orphan")


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purchase_order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"))
    material_id: Mapped[str | None] = mapped_column(ForeignKey("raw_materials.id"), nullable=True)
    material_name: Mapped[str] = mapped_column(String(160))
    quantity: Mapped[float] = mapped_column(Float)
    rate: Mapped[float] = mapped_column(Float)
    gst_rate: Mapped[float] = mapped_column(Float)
    received_quantity: Mapped[float] = mapped_column(Float)
    tax: Mapped[float] = mapped_column(Float)
    total: Mapped[float] = mapped_column(Float)


class GRN(Base):
    __tablename__ = "grns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    grn_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    grn_date: Mapped[date] = mapped_column(Date, index=True)
    purchase_order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id"))
    po_no: Mapped[str] = mapped_column(String(32))
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"))
    lines: Mapped[list["GRNLine"]] = relationship(cascade="all, delete-orphan")


class GRNLine(Base):
    __tablename__ = "grn_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grn_id: Mapped[str] = mapped_column(ForeignKey("grns.id", ondelete="CASCADE"))
    material_id: Mapped[str] = mapped_column(ForeignKey("raw_materials.id"))
    material_name: Mapped[str] = mapped_column(String(160))
    quantity: Mapped[float] = mapped_column(Float)
    batch_no: Mapped[str] = mapped_column(String(64))


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


