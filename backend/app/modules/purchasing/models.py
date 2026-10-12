"""Purchasing domain SQLAlchemy models."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
from app.modules._base import _uuid, Role, ItemKind, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseOrderStatus


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
