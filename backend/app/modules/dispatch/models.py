"""Dispatch domain SQLAlchemy models."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
from app.modules._base import _uuid, Role, ItemKind, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseOrderStatus


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
