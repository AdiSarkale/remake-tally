"""Inventory domain SQLAlchemy models."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
from app.modules._base import _uuid, Role, ItemKind, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseOrderStatus


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
