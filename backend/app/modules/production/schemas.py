"""Production domain Pydantic schemas."""

from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.modules._base import Role, ItemKind, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseOrderStatus
from app.modules.core.schemas import ORMModel


class BomLineIn(BaseModel):
    material_id: str | None = None
    subassembly_product_id: str | None = None
    quantity: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_item_reference(self):
        if bool(self.material_id) == bool(self.subassembly_product_id):
            raise ValueError("Specify exactly one of material_id or subassembly_product_id")
        return self

class BomLineOut(BaseModel):
    id: int
    material_id: str | None = None
    subassembly_product_id: str | None = None
    line_type: str = "RM"
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
    job_card_id: str | None = None
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
    job_card_id: str | None = None
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
    source_warehouse_id: str | None = None
    wip_warehouse_id: str | None = None
    target_warehouse_id: str | None = None
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
    source_warehouse_id: str | None = None
    wip_warehouse_id: str | None = None
    target_warehouse_id: str | None = None
    remarks: str
    operations: list[ProductionOrderOperationOut] = Field(default_factory=list)

class ProductionOrderMaterialRequirementOut(BaseModel):
    material_id: str
    material_code: str
    material_name: str
    unit: str
    required_quantity: float
    consumed_quantity: float
    remaining_quantity: float
    available_quantity: float
    shortage_quantity: float
    status: str


class ProductionOrderMaterialPlanOut(BaseModel):
    order_id: str
    order_no: str
    product_id: str
    order_quantity: float
    materials_available: bool
    materials: list[ProductionOrderMaterialRequirementOut] = Field(default_factory=list)


class ManufacturingAssignmentOut(BaseModel):
    operation_id: str
    workcenter_id: str
    employee_id: str | None
    assignment_mode: str

class QualityCheckIn(BaseModel):
    test_name: str = Field(min_length=1, max_length=120)
    expected_value: str = ""
    actual_value: str = ""
    passed: bool = True
    remarks: str = ""

class QualityInspectionLineOut(ORMModel):
    id: int
    test_name: str
    expected_value: str
    actual_value: str
    passed: bool
    remarks: str

class QualityInspectionOut(ORMModel):
    id: str
    production_entry_id: str
    status: str
    inspected_quantity: float
    accepted_quantity: float
    rejected_quantity: float
    inspector_user_id: str | None
    inspected_at: datetime | None
    remarks: str
    lines: list[QualityInspectionLineOut] = Field(default_factory=list)

class ProductionQualityIn(BaseModel):
    status: str = Field(pattern="^(Accepted|Rejected|Accepted with Deviation)$")
    accepted_qty: float = Field(ge=0)
    rejected_qty: float = Field(ge=0)
    remarks: str = ""
    checks: list[QualityCheckIn] = Field(default_factory=list)

class ManufacturingReportOut(BaseModel):
    production_qty: float
    scrap_qty: float
    planned_material_qty: float
    actual_material_qty: float
    material_variance: float
    by_workcenter: list[dict]


class StockReservationOut(ORMModel):
    id: str
    production_order_id: str
    material_id: str
    quantity: float
    consumed_quantity: float
    status: str
    warehouse_id: str | None = None
    created_at: datetime
    released_at: datetime | None

class ProductionOrderReservationOut(BaseModel):
    order_id: str
    order_no: str
    reservations: list[StockReservationOut] = Field(default_factory=list)


class ProductionOrderTransitionIn(BaseModel):
    action: str = Field(pattern="^(release|start|complete|cancel)$")


class JobCardTimeLogIn(BaseModel):
    employee_id: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    completed_qty: float = Field(default=0, ge=0)
    remarks: str = ""

class JobCardTimeLogOut(ORMModel):
    id: str
    job_card_id: str
    employee_id: str
    start_time: datetime
    end_time: datetime | None
    duration_minutes: float
    completed_qty: float
    remarks: str

class JobCardOut(ORMModel):
    id: str
    production_order_id: str
    production_order_operation_id: str
    operation_id: str
    workcenter_id: str
    assigned_employee_id: str | None
    planned_qty: float
    completed_qty: float
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    remarks: str
    time_logs: list[JobCardTimeLogOut] = Field(default_factory=list)


class ProductionMaterialTransferOut(ORMModel):
    id: str
    production_order_id: str
    material_id: str
    source_warehouse_id: str
    target_warehouse_id: str
    quantity: float
    transferred_at: datetime


class BomExplosionLineOut(BaseModel):
    line_type: str
    item_id: str
    item_code: str
    item_name: str
    unit: str
    required_quantity: float
    level: int
    parent_product_id: str
    status: str

class BomExplosionOut(BaseModel):
    bom_id: str
    product_id: str
    quantity: float
    lines: list[BomExplosionLineOut] = Field(default_factory=list)
    raw_materials_available: bool
