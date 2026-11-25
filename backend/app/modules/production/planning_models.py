"""Additional planning and advanced manufacturing persistence models."""
from __future__ import annotations
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
from app.modules._base import _uuid

class MaterialReservation(Base):
    __tablename__ = "production_material_reservations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    production_order_id: Mapped[str] = mapped_column(ForeignKey("production_orders.id", ondelete="CASCADE"), index=True)
    material_id: Mapped[str] = mapped_column(ForeignKey("raw_materials.id"), index=True)
    required_quantity: Mapped[float] = mapped_column(Float)
    reserved_quantity: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class OperationSchedule(Base):
    __tablename__ = "production_operation_schedules"
    __table_args__ = (UniqueConstraint("operation_row_id", name="uq_production_schedule_operation"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    operation_row_id: Mapped[str] = mapped_column(ForeignKey("production_order_operations.id", ondelete="CASCADE"), index=True)
    workcenter_id: Mapped[str] = mapped_column(ForeignKey("workcenters.id"), index=True)
    machine_id: Mapped[str | None] = mapped_column(ForeignKey("machine_resources.id"), nullable=True, index=True)
    employee_id: Mapped[str | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    planned_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_minutes: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(24), default="scheduled", index=True)
    reschedule_reason: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class MachineResource(Base):
    __tablename__ = "machine_resources"
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120))
    workcenter_id: Mapped[str] = mapped_column(ForeignKey("workcenters.id"), index=True)
    capacity_per_hour: Mapped[float] = mapped_column(Float, default=0)
    hourly_rate: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(24), default="available", index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    maintenance_due: Mapped[date | None] = mapped_column(Date, nullable=True)

class MachineDowntime(Base):
    __tablename__ = "machine_downtime"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machine_resources.id", ondelete="CASCADE"), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    reason_code: Mapped[str] = mapped_column(String(40), default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    maintenance: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(64), default="")

class ProductionCost(Base):
    __tablename__ = "production_costs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    production_entry_id: Mapped[str] = mapped_column(ForeignKey("production_entries.id", ondelete="CASCADE"), unique=True, index=True)
    material_cost: Mapped[float] = mapped_column(Float, default=0)
    labor_cost: Mapped[float] = mapped_column(Float, default=0)
    machine_cost: Mapped[float] = mapped_column(Float, default=0)
    overhead_cost: Mapped[float] = mapped_column(Float, default=0)
    total_cost: Mapped[float] = mapped_column(Float, default=0)
    accepted_quantity: Mapped[float] = mapped_column(Float, default=0)
    unit_cost: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    notes: Mapped[str] = mapped_column(Text, default="")

class WIPStock(Base):
    __tablename__ = "production_wip_stock"
    __table_args__ = (UniqueConstraint("product_id", "production_order_id", name="uq_wip_product_order"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    production_order_id: Mapped[str | None] = mapped_column(ForeignKey("production_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    unit_cost: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(24), default="available", index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
