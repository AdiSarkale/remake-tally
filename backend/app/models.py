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
    kind: Mapped[str] = mapped_column(String(16), index=True)  # customer | supplier
    name: Mapped[str] = mapped_column(String(160), index=True)
    gst_number: Mapped[str] = mapped_column(String(32), default="")
    phone: Mapped[str] = mapped_column(String(32), default="")
    address: Mapped[str] = mapped_column(Text, default="")
class Product(Base):
    __tablename__ = "products"
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
    unit: Mapped[str] = mapped_column(String(16), default="KG")
    cost: Mapped[float] = mapped_column(Float, default=0)
class ScrapType(Base):
    __tablename__ = "scrap_types"
    selling_rate: Mapped[float] = mapped_column(Float, default=0)
class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
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
    batch_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
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
    entry: Mapped[ProductionEntry] = relationship(back_populates="consumption")
class ScrapEntry(Base):
    __tablename__ = "scrap_entries"
    batch_no: Mapped[str] = mapped_column(String(32), default="")
    scrap_type_id: Mapped[str] = mapped_column(ForeignKey("scrap_types.id"))
    reason: Mapped[str] = mapped_column(String(120), default="")
class AuditLog(Base):
    __tablename__ = "audit_logs"
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    username: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32))
    entity: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(Text, default="")
class CompanySettings(Base):
    __tablename__ = "company_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    name: Mapped[str] = mapped_column(String(160), default="MiniTally Manufacturing")
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
    invoice_no: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
    invoice_date: Mapped[date] = mapped_column(
        Date,
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("parties.id")
    customer_name: Mapped[str] = mapped_column(
        String(160)
    po_reference: Mapped[str] = mapped_column(
        String(64),
        default="",
    notes: Mapped[str] = mapped_column(
        Text,
    inter_state: Mapped[bool] = mapped_column(
        Integer,
        default=0,
    sub_total: Mapped[float] = mapped_column(
        Float,
    discount_total: Mapped[float] = mapped_column(
    taxable_total: Mapped[float] = mapped_column(
    cgst: Mapped[float] = mapped_column(
    sgst: Mapped[float] = mapped_column(
    igst: Mapped[float] = mapped_column(
    round_off: Mapped[float] = mapped_column(
    grand_total: Mapped[float] = mapped_column(
    paid_amount: Mapped[float] = mapped_column(
    balance_amount: Mapped[float] = mapped_column(
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus),
        default=InvoiceStatus.unpaid,
    signature: Mapped[str] = mapped_column(
    created_by: Mapped[str] = mapped_column(
    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"))
    product_name: Mapped[str] = mapped_column(String(160))
    rate: Mapped[float] = mapped_column(Float)
    discount_percent: Mapped[float] = mapped_column(Float, default=0)
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
    quotation_no: Mapped[str] = mapped_column(
    quotation_date: Mapped[date] = mapped_column(
    valid_until: Mapped[date | None] = mapped_column(
        nullable=True,
        ForeignKey("parties.id"),
        String(160),
    status: Mapped[QuotationStatus] = mapped_column(
        Enum(QuotationStatus),
        default=QuotationStatus.draft,
    lines: Mapped[list["QuotationLine"]] = relationship(
        back_populates="quotation",
class QuotationLine(Base):
    __tablename__ = "quotation_lines"
    id: Mapped[int] = mapped_column(
        autoincrement=True,
    quotation_id: Mapped[str] = mapped_column(
        ForeignKey(
            "quotations.id",
            ondelete="CASCADE",
        )
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id"),
    product_name: Mapped[str] = mapped_column(
    hsn: Mapped[str] = mapped_column(
        String(16),
    unit: Mapped[str] = mapped_column(
        default="PCS",
    quantity: Mapped[float] = mapped_column(
    rate: Mapped[float] = mapped_column(
    discount_percent: Mapped[float] = mapped_column(
    gst_rate: Mapped[float] = mapped_column(
        default=18,
    taxable: Mapped[float] = mapped_column(
    total: Mapped[float] = mapped_column(
    quotation: Mapped[Quotation] = relationship(
        back_populates="lines",
class SalesOrderStatus(str, enum.Enum):
    open = "Open"
    partially_delivered = "Partially Delivered"
    delivered = "Delivered"
    invoiced = "Invoiced"
class SalesOrder(Base):
    __tablename__ = "sales_orders"
    so_no: Mapped[str] = mapped_column(
    order_date: Mapped[date] = mapped_column(
    delivery_date: Mapped[date | None] = mapped_column(
    status: Mapped[SalesOrderStatus] = mapped_column(
        Enum(SalesOrderStatus),
        default=SalesOrderStatus.open,
    quote_id: Mapped[str | None] = mapped_column(
        ForeignKey("quotations.id"),
    quote_no: Mapped[str] = mapped_column(
    lines: Mapped[list["SalesOrderLine"]] = relationship(
        back_populates="sales_order",
class SalesOrderLine(Base):
    __tablename__ = "sales_order_lines"
    sales_order_id: Mapped[str] = mapped_column(
            "sales_orders.id",
        ),
    delivered_quantity: Mapped[float] = mapped_column(
    sales_order: Mapped[SalesOrder] = relationship(
class DeliveryNote(Base):
    __tablename__ = "delivery_notes"
    delivery_no: Mapped[str] = mapped_column(
    delivery_date: Mapped[date] = mapped_column(
    sales_order_id: Mapped[str | None] = mapped_column(
        ForeignKey("sales_orders.id"),
    vehicle_no: Mapped[str] = mapped_column(
    driver_name: Mapped[str] = mapped_column(
        String(120),
    lr_number: Mapped[str] = mapped_column(
    remarks: Mapped[str] = mapped_column(
    lines: Mapped[list["DeliveryLine"]] = relationship(
        back_populates="delivery",
class DeliveryLine(Base):
    __tablename__ = "delivery_lines"
    delivery_id: Mapped[str] = mapped_column(
            "delivery_notes.id",
    delivery: Mapped[DeliveryNote] = relationship(
class DispatchStatus(str, enum.Enum):
    planned = "Planned"
    loading = "Loading"
    in_transit = "In Transit"
    delayed = "Delayed"
class Dispatch(Base):
    __table_args__ = (
    UniqueConstraint(
        "delivery_id",
        name="uq_dispatch_delivery",
    ),
)
    __tablename__ = "dispatches"
    dispatch_no: Mapped[str] = mapped_column(
    dispatch_date: Mapped[date] = mapped_column(
    delivery_id: Mapped[str | None] = mapped_column(
        ForeignKey("delivery_notes.id"),
    transporter: Mapped[str] = mapped_column(
    driver_phone: Mapped[str] = mapped_column(
    status: Mapped[DispatchStatus] = mapped_column(
        Enum(DispatchStatus),
        default=DispatchStatus.planned,
    delivered_on: Mapped[date | None] = mapped_column(
    pod_ref: Mapped[str] = mapped_column(
"""Merge these model classes into app/models.py."""
class Plant(Base):
    __tablename__ = "plants"
    location: Mapped[str] = mapped_column(String(255), default="")
class Warehouse(Base):
    __tablename__ = "warehouses"
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), index=True)
class SupplierProduct(Base):
    __tablename__ = "supplier_products"
    supplier_id: Mapped[str] = mapped_column(ForeignKey("parties.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("raw_materials.id"), index=True)
    supplier_code: Mapped[str] = mapped_column(String(64), default="")
    purchase_rate: Mapped[float] = mapped_column(Float, default=0)
    minimum_order_qty: Mapped[float] = mapped_column(Float, default=0)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=0)
class PurchaseOrderStatus(str, enum.Enum):
    draft = "Draft"
    sent = "Sent"
    partially_received = "Partially Received"
    received = "Received"
class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    po_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    po_date: Mapped[date] = mapped_column(Date, index=True)
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("parties.id"))
    supplier_name: Mapped[str] = mapped_column(String(160))
    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[PurchaseOrderStatus] = mapped_column(Enum(PurchaseOrderStatus), default=PurchaseOrderStatus.draft)
    sub_total: Mapped[float] = mapped_column(Float, default=0)
    gst_total: Mapped[float] = mapped_column(Float, default=0)
    grand_total: Mapped[float] = mapped_column(Float, default=0)
    created_by: Mapped[str] = mapped_column(String(64), default="")
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates="purchase_order", cascade="all, delete-orphan")
class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"
    purchase_order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"))
    material_name: Mapped[str] = mapped_column(String(160))
    received_quantity: Mapped[float] = mapped_column(Float, default=0)
    tax: Mapped[float] = mapped_column(Float, default=0)
    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="lines")
class GRN(Base):
    __tablename__ = "grns"
    grn_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    grn_date: Mapped[date] = mapped_column(Date, index=True)
    purchase_order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id"))
    po_no: Mapped[str] = mapped_column(String(32))
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"))
    lines: Mapped[list["GRNLine"]] = relationship(back_populates="grn", cascade="all, delete-orphan")
class GRNLine(Base):
    __tablename__ = "grn_lines"
    grn_id: Mapped[str] = mapped_column(ForeignKey("grns.id", ondelete="CASCADE"))
    batch_no: Mapped[str] = mapped_column(String(64), default="")
    grn: Mapped[GRN] = relationship(back_populates="lines")
class CustomerPO(Base):
    __tablename__ = "customer_pos"
    po_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    po_date: Mapped[date] = mapped_column(Date)
    customer_id: Mapped[str] = mapped_column(ForeignKey("parties.id"), index=True)
    customer_name: Mapped[str] = mapped_column(String(160))
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    lines: Mapped[list["CustomerPOLine"]] = relationship(back_populates="customer_po", cascade="all, delete-orphan")
class CustomerPOLine(Base):
    __tablename__ = "customer_po_lines"
    customer_po_id: Mapped[str] = mapped_column(ForeignKey("customer_pos.id", ondelete="CASCADE"))
    rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    customer_po: Mapped[CustomerPO] = relationship(back_populates="lines")
