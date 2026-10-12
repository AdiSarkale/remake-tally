"""Production domain Pydantic schemas."""

from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.modules._base import Role, ItemKind, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseOrderStatus
from app.modules.core.schemas import ORMModel


class BomLineIn(BaseModel):
    material_id: str
    quantity: float = Field(gt=0)

class BomLineOut(BaseModel):
    id: int
    material_id: str
    quantity: float

class BomIn(BaseModel):
    product_id: str

    version: int = Field(default=1, ge=1)

    active: bool = True

    expected_scrap_percent: float = Field(
        default=0,
        ge=0,
        le=100
    )

    scrap_type_id: str | None = None

    lines: list[BomLineIn]

class BOMOut(ORMModel):
    id: str
    product_id: str
    version: int
    active: bool

    expected_scrap_percent: float

    scrap_type_id: str | None

    lines: list[BomLineOut]

# ---------- Inventory ----------

class ConsumptionIn(BaseModel):
    material_id: str
    quantity: float = Field(ge=0)

class ConsumptionOut(ORMModel):
    material_id: str
    planned_quantity: float
    quantity: float
    variance: float

class ProductionIn(BaseModel):
    entry_date: date
    product_id: str
    quantity: float = Field(gt=0)

    machine: str = ""
    workcenter_id: str | None = None
    routing_id: str | None = None
    operation_id: str | None = None
    production_order_id: str | None = None
    employee_id: str | None = None
    operator: str = ""
    shift: str = "A"
    remarks: str = ""

    # Phase 0: the active BOM is the source of planned consumption.
    # Actual-consumption variance is introduced in Phase 1.
    consumption: list[ConsumptionIn] = Field(default_factory=list)

    scrap_type_id: str | None = None

class ProductionOut(ORMModel):
    id: str
    batch_no: str
    entry_date: date
    product_id: str
    quantity: float
    machine: str
    workcenter_id: str | None = None
    routing_id: str | None = None
    operation_id: str | None = None
    production_order_id: str | None = None
    employee_id: str | None = None
    operator: str
    shift: str
    remarks: str

    actual_scrap: float | None = None
    quality_status: str = "Pending"
    accepted_qty: float = 0
    rejected_qty: float = 0
    quality_remarks: str = ""
    consumption: list[ConsumptionOut] = Field(default_factory=list)


# ---------- Scrap ----------

class ScrapIn(BaseModel):
    entry_date: date
    product_id: str
    batch_no: str = ""
    scrap_type_id: str
    quantity: float = Field(gt=0)
    reason: str = ""
    remarks: str = ""

class ScrapOut(ScrapIn, ORMModel):
    id: str




# ---------- Payments / Receivables / Payables ----------

class WorkcenterMaterialIn(BaseModel):
    item_kind: str = Field(pattern="^(RM|SF|FG)$")
    item_id: str
    operation_id: str | None = None

class WorkcenterMaterialOut(ORMModel):
    id: str
    workcenter_id: str
    item_kind: str
    item_id: str
    operation_id: str | None

class WorkcenterIn(BaseModel):
    code: str
    name: str
    department: str = ""
    capacity_per_hour: float = Field(default=0, ge=0)
    status: str = "Available"
    active: bool = True
    location: str = ""
    materials: list[WorkcenterMaterialIn] = Field(default_factory=list)

class WorkcenterOut(ORMModel):
    id: str
    code: str
    name: str
    department: str
    capacity_per_hour: float
    status: str
    active: bool
    location: str
    materials: list[WorkcenterMaterialOut] = Field(default_factory=list)

class RoutingOperationIn(BaseModel):
    sequence: int = Field(ge=1)
    code: str = ""
    name: str
    workcenter_id: str
    required_skill: str = ""
    setup_minutes: float = Field(default=0, ge=0)
    run_minutes_per_unit: float = Field(default=0, ge=0)
    active: bool = True

class RoutingIn(BaseModel):
    product_id: str
    version: int = Field(default=1, ge=1)
    name: str = ""
    active: bool = True
    operations: list[RoutingOperationIn] = Field(min_length=1)

class RoutingOperationOut(ORMModel):
    id: str
    sequence: int
    code: str
    name: str
    workcenter_id: str
    required_skill: str
    setup_minutes: float
    run_minutes_per_unit: float
    active: bool

class RoutingOut(ORMModel):
    id: str
    product_id: str
    version: int
    name: str
    active: bool
    operations: list[RoutingOperationOut]

class ProductionOrderIn(BaseModel):
    order_date: date
    product_id: str
    quantity: float = Field(gt=0)
    due_date: date | None = None
    routing_id: str | None = None
    remarks: str = ""

class ProductionOrderOperationOut(ORMModel):
    id: str
    operation_id: str
    sequence: int
    workcenter_id: str
    assigned_employee_id: str | None
    status: str
    planned_qty: float
    completed_qty: float

class ProductionOrderOut(ORMModel):
    id: str
    order_no: str
    order_date: date
    product_id: str
    quantity: float
    due_date: date | None
    routing_id: str | None
    status: str
    remarks: str
    operations: list[ProductionOrderOperationOut] = Field(default_factory=list)

class ManufacturingAssignmentOut(BaseModel):
    operation_id: str
    workcenter_id: str
    employee_id: str | None
    assignment_mode: str

class ProductionQualityIn(BaseModel):
    status: str = Field(pattern="^(Pending|Accepted|Rejected|Accepted with Deviation)$")
    accepted_qty: float = Field(ge=0)
    rejected_qty: float = Field(ge=0)
    remarks: str = ""

class ManufacturingReportOut(BaseModel):
    production_qty: float
    scrap_qty: float
    planned_material_qty: float
    actual_material_qty: float
    material_variance: float
    by_workcenter: list[dict]
