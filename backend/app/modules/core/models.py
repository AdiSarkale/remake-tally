"""Core domain SQLAlchemy models."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
from app.modules._base import _uuid, Role, ItemKind, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseOrderStatus


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
