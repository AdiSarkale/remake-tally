"""Production domain SQLAlchemy models."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
from app.modules._base import _uuid, Role, ItemKind, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseOrderStatus


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

class ProductionEntry(Base):
    __tablename__ = "production_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[float] = mapped_column(Float)
    machine: Mapped[str] = mapped_column(String(64), default="")
    workcenter_id: Mapped[str | None] = mapped_column(ForeignKey("workcenters.id"), nullable=True, index=True)
    routing_id: Mapped[str | None] = mapped_column(ForeignKey("routings.id"), nullable=True, index=True)
    operation_id: Mapped[str | None] = mapped_column(ForeignKey("routing_operations.id"), nullable=True, index=True)
    production_order_id: Mapped[str | None] = mapped_column(ForeignKey("production_orders.id"), nullable=True, index=True)
    job_card_id: Mapped[str | None] = mapped_column(ForeignKey("job_cards.id"), nullable=True, index=True)
    employee_id: Mapped[str | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    operator: Mapped[str] = mapped_column(String(120), default="")
    shift: Mapped[str] = mapped_column(String(4), default="A")
    remarks: Mapped[str] = mapped_column(Text, default="")
    actual_scrap: Mapped[float] = mapped_column(Float, default=0)
    quality_status: Mapped[str] = mapped_column(String(32), default="Pending")
    accepted_qty: Mapped[float] = mapped_column(Float, default=0)
    rejected_qty: Mapped[float] = mapped_column(Float, default=0)
    quality_remarks: Mapped[str] = mapped_column(Text, default="")

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
    planned_quantity: Mapped[float] = mapped_column(Float, default=0)
    quantity: Mapped[float] = mapped_column(Float)

    entry: Mapped[ProductionEntry] = relationship(back_populates="consumption")

    @property
    def variance(self) -> float:
        """Actual material usage minus the BOM-planned quantity."""
        return round(float(self.quantity) - float(self.planned_quantity), 3)


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

class Workcenter(Base):
    __tablename__ = "workcenters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    department: Mapped[str] = mapped_column(String(120), default="")
    capacity_per_hour: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(32), default="Available")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    location: Mapped[str] = mapped_column(String(160), default="")

class WorkcenterMaterial(Base):
    __tablename__ = "workcenter_materials"
    __table_args__ = (UniqueConstraint("workcenter_id", "item_kind", "item_id", name="uq_workcenter_item"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workcenter_id: Mapped[str] = mapped_column(ForeignKey("workcenters.id", ondelete="CASCADE"), index=True)
    item_kind: Mapped[str] = mapped_column(String(8))
    item_id: Mapped[str] = mapped_column(String(36), index=True)
    operation_id: Mapped[str | None] = mapped_column(ForeignKey("routing_operations.id"), nullable=True, index=True)

class Routing(Base):
    __tablename__ = "routings"
    __table_args__ = (UniqueConstraint("product_id", "version", name="uq_routing_product_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    operations: Mapped[list["RoutingOperation"]] = relationship(
        back_populates="routing", cascade="all, delete-orphan", order_by="RoutingOperation.sequence"
    )

class RoutingOperation(Base):
    __tablename__ = "routing_operations"
    __table_args__ = (UniqueConstraint("routing_id", "sequence", name="uq_routing_operation_sequence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    routing_id: Mapped[str] = mapped_column(ForeignKey("routings.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(String(32), default="")
    name: Mapped[str] = mapped_column(String(120))
    workcenter_id: Mapped[str] = mapped_column(ForeignKey("workcenters.id"), index=True)
    required_skill: Mapped[str] = mapped_column(String(120), default="")
    setup_minutes: Mapped[float] = mapped_column(Float, default=0)
    run_minutes_per_unit: Mapped[float] = mapped_column(Float, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    routing: Mapped[Routing] = relationship(back_populates="operations")

class ProductionOrder(Base):
    __tablename__ = "production_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    order_date: Mapped[date] = mapped_column(Date, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    routing_id: Mapped[str | None] = mapped_column(ForeignKey("routings.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="Planned")
    source_warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    wip_warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    target_warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    remarks: Mapped[str] = mapped_column(Text, default="")

class ProductionOrderOperation(Base):
    __tablename__ = "production_order_operations"
    __table_args__ = (UniqueConstraint("production_order_id", "sequence", name="uq_order_operation_sequence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    production_order_id: Mapped[str] = mapped_column(ForeignKey("production_orders.id", ondelete="CASCADE"), index=True)
    operation_id: Mapped[str] = mapped_column(ForeignKey("routing_operations.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    workcenter_id: Mapped[str] = mapped_column(ForeignKey("workcenters.id"), index=True)
    assigned_employee_id: Mapped[str | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="Pending")
    planned_qty: Mapped[float] = mapped_column(Float)
    completed_qty: Mapped[float] = mapped_column(Float, default=0)


class StockReservation(Base):
    """Raw-material quantity reserved for a production order."""
    __tablename__ = "stock_reservations"
    __table_args__ = (UniqueConstraint("production_order_id", "material_id", name="uq_stock_reservation_order_material"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    production_order_id: Mapped[str] = mapped_column(ForeignKey("production_orders.id", ondelete="CASCADE"), index=True)
    material_id: Mapped[str] = mapped_column(ForeignKey("raw_materials.id"), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    consumed_quantity: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(16), default="Reserved", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True, index=True)

    @property
    def remaining_quantity(self) -> float:
        return round(max(float(self.quantity) - float(self.consumed_quantity), 0.0), 3)


class JobCard(Base):
    """Shop-floor execution card for one production-order operation."""
    __tablename__ = "job_cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    production_order_id: Mapped[str] = mapped_column(ForeignKey("production_orders.id", ondelete="CASCADE"), index=True)
    production_order_operation_id: Mapped[str] = mapped_column(ForeignKey("production_order_operations.id", ondelete="CASCADE"), index=True)
    operation_id: Mapped[str] = mapped_column(ForeignKey("routing_operations.id"), index=True)
    workcenter_id: Mapped[str] = mapped_column(ForeignKey("workcenters.id"), index=True)
    assigned_employee_id: Mapped[str | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    planned_qty: Mapped[float] = mapped_column(Float)
    completed_qty: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(24), default="Pending", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remarks: Mapped[str] = mapped_column(Text, default="")

class JobCardTimeLog(Base):
    __tablename__ = "job_card_time_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_card_id: Mapped[str] = mapped_column(ForeignKey("job_cards.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[float] = mapped_column(Float, default=0)
    completed_qty: Mapped[float] = mapped_column(Float, default=0)
    remarks: Mapped[str] = mapped_column(Text, default="")


class ProductionMaterialTransfer(Base):
    __tablename__ = "production_material_transfers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    production_order_id: Mapped[str] = mapped_column(ForeignKey("production_orders.id", ondelete="CASCADE"), index=True)
    material_id: Mapped[str] = mapped_column(ForeignKey("raw_materials.id"), index=True)
    source_warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"))
    target_warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"))
    quantity: Mapped[float] = mapped_column(Float)
    transferred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QualityInspection(Base):
    __tablename__ = "quality_inspections"
    __table_args__ = (UniqueConstraint("production_entry_id", name="uq_quality_inspection_production_entry"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    production_entry_id: Mapped[str] = mapped_column(ForeignKey("production_entries.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="Pending", index=True)
    inspected_quantity: Mapped[float] = mapped_column(Float)
    accepted_quantity: Mapped[float] = mapped_column(Float, default=0)
    rejected_quantity: Mapped[float] = mapped_column(Float, default=0)
    inspector_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    inspected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remarks: Mapped[str] = mapped_column(Text, default="")

class QualityInspectionLine(Base):
    __tablename__ = "quality_inspection_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inspection_id: Mapped[str] = mapped_column(ForeignKey("quality_inspections.id", ondelete="CASCADE"), index=True)
    test_name: Mapped[str] = mapped_column(String(120))
    expected_value: Mapped[str] = mapped_column(String(160), default="")
    actual_value: Mapped[str] = mapped_column(String(160), default="")
    passed: Mapped[bool] = mapped_column(Boolean, default=True)
    remarks: Mapped[str] = mapped_column(Text, default="")
