"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import DispatchStatus, InvoiceStatus, ItemKind, MovementType, PurchaseOrderStatus, QuotationStatus, Role, SalesOrderStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    full_name: str


class UserOut(ORMModel):
    id: str
    username: str
    full_name: str
    role: Role
    email: str = ""
    active: bool = True


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    full_name: str = Field(min_length=1, max_length=120)
    email: str = ""
    role: Role = Role.operator
    password: str = Field(min_length=6, max_length=128)
    active: bool = True


class UserUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: str = ""
    role: Role
    active: bool = True


class PasswordReset(BaseModel):
    """Admin reset — the target user's current password is NOT required."""

    new_password: str = Field(min_length=6, max_length=128)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=128)


# ---------- Masters ----------
class PartyIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    gst_number: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""


class PartyOut(PartyIn, ORMModel):
    id: str
    kind: str


class ProductIn(BaseModel):
    code: str
    name: str
    unit: str = "PCS"
    hsn: str = ""
    cost_price: float = 0
    selling_price: float = 0
    gst_rate: float = 18
    min_stock: float = 0


class ProductOut(ProductIn, ORMModel):
    id: str
    stock: float


class RawMaterialIn(BaseModel):
    name: str
    code: str
    unit: str = "KG"
    cost: float = 0
    min_stock: float = 0


class RawMaterialOut(RawMaterialIn, ORMModel):
    id: str
    stock: float


class ScrapReasonOut(BaseModel):
    reason: str
    quantity: float

class ScrapTypeIn(BaseModel):
    code: str
    name: str
    unit: str = "KG"
    selling_rate: float = 0
    min_stock: float = 0
    active: bool = True


class ScrapTypeOut(ScrapTypeIn, ORMModel):
    id: str
    code: str
    name: str
    unit: str
    stock: float
    min_stock: float
    selling_rate: float
    active: bool


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
class MovementIn(BaseModel):
    item_kind: ItemKind
    item_id: str
    movement_type: MovementType
    quantity: float = Field(ge=0)
    reference: str = ""
    reason: str = ""
    entry_date: date | None = None


class MovementOut(ORMModel):
    id: str
    entry_date: date
    item_kind: ItemKind
    item_id: str
    item_name: str
    movement_type: MovementType
    quantity: float
    unit: str
    balance: float
    reference: str
    reason: str


# ---------- Production ----------
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



# ---------- Dashboard ----------

class ProductionSeriesOut(BaseModel):
    date: date
    label: str
    produced: float
    scrap: float


class RecentProductionOut(BaseModel):
    id: str
    batch_no: str
    entry_date: date
    product_name: str
    quantity: float
    machine: str
    operator: str
    shift: str


class LowStockOut(BaseModel):
    id: str
    name: str
    stock: float
    min_stock: float
    unit: str
    kind: str


class DashboardOut(BaseModel):
    # KPI cards
    produced_today: float
    produced_month: float
    scrap_month: float
    scrap_rate: float
    inventory_value: float
    low_stock_count: int

    finished_goods_quantity: float
    finished_goods_sku_count: int
    finished_goods_value: float

    scrap_stock_quantity: float
    scrap_stock_value: float

    raw_material_value: float
    raw_material_count: int

    # Dashboard tables / charts
    production_series: list[ProductionSeriesOut]
    recent_production: list[RecentProductionOut]
    low_stock_items: list[LowStockOut]
    top_scrap_reasons: list[ScrapReasonOut]


class AuditOut(ORMModel):
    id: str
    at: datetime
    username: str
    action: str
    entity: str
    detail: str


class SettingsIn(BaseModel):
    name: str
    gst_number: str | None = None
    address: str | None = None
    invoice_prefix: str = "INV"
    financial_year: str = "2026-2027"


class SettingsOut(SettingsIn, ORMModel):
    id: int


# ---------- Sales invoices ----------
# ---------- Sales invoices ----------

class InvoiceLineIn(BaseModel):
    product_id: str

    quantity: float = Field(
        gt=0,
    )

    rate: float = Field(
        ge=0,
    )

    discount_percent: float = Field(
        default=0,
        ge=0,
        le=100,
    )

    # None = use product master GST.
    # A number = custom GST for this invoice line.
    gst_rate: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )


class InvoiceLineOut(ORMModel):
    product_id: str
    product_name: str
    hsn: str
    unit: str
    quantity: float
    rate: float
    discount_percent: float
    gst_rate: float
    taxable: float
    cgst: float
    sgst: float
    igst: float
    total: float


class InvoiceIn(BaseModel):
    invoice_date: date
    customer_id: str
    po_reference: str = ""
    notes: str = ""

    # Backend can derive this from paid_percent,
    # but keeping it here makes the API explicit.
    status: InvoiceStatus = InvoiceStatus.unpaid

    paid_percent: float = Field(
        default=0,
        ge=0,
        le=100,
    )

    lines: list[InvoiceLineIn] = Field(
        min_length=1,
    )


class InvoiceOut(ORMModel):
    id: str
    invoice_no: str
    invoice_date: date

    customer_id: str
    customer_name: str

    po_reference: str
    notes: str

    inter_state: bool

    sub_total: float
    discount_total: float
    taxable_total: float

    cgst: float
    sgst: float
    igst: float

    round_off: float
    grand_total: float

    paid_amount: float
    balance_amount: float

    status: InvoiceStatus

    lines: list[InvoiceLineOut]


class InvoiceStatusIn(BaseModel):
    status: InvoiceStatus

    # Required when changing to Partial.
    # Optional for Paid/Unpaid; backend derives the amount.
    paid_percent: float = Field(
        default=0,
        ge=0,
        le=100,
    )

class QuotationIn(BaseModel):
    quotation_date : date
    valid_until : date | None = None
    customer_id : str
    po_reference: str = ''
    notes: str = ''
    status :QuotationStatus = QuotationStatus.draft
    lines: list["QuotationLineIn"]


class QuotationLineIn(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    rate: float = Field(ge=0)
    discount_percent: float = Field(
        ge=0,
        le=100,
        default=0,
    )

    # None = use product's GST
    # Number = custom GST for this quotation line
    gst_rate: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )


class QuotationLineOut(ORMModel):
    id: int
    product_id: str
    product_name: str
    hsn: str
    unit: str

    quantity: float
    rate: float
    discount_percent: float
    gst_rate: float

    taxable: float
    cgst: float
    sgst: float
    igst: float
    total: float


class QuotationOut(ORMModel):
    id: str
    quotation_no: str
    quotation_date: date
    valid_until: date | None

    customer_id: str
    customer_name: str

    po_reference: str
    notes: str

    inter_state: bool

    sub_total: float
    discount_total: float
    taxable_total: float

    cgst: float
    sgst: float
    igst: float

    round_off: float
    grand_total: float

    status: QuotationStatus
    created_by: str

    lines: list[QuotationLineOut]

class QuotationStatusIn(BaseModel):
    status: QuotationStatus


class SalesOrderLineOut(ORMModel):
    id: int
    product_id: str
    product_name: str
    hsn: str
    unit: str
    quantity: float
    rate: float
    discount_percent: float
    gst_rate: float
    taxable: float
    cgst: float
    sgst: float
    igst: float
    total: float
    delivered_quantity: float


class SalesOrderOut(ORMModel):
    id: str
    so_no: str
    order_date: date
    delivery_date: date | None
    customer_id: str
    customer_name: str
    notes: str
    status: SalesOrderStatus
    quote_id: str | None
    quote_no: str
    taxable_total: float
    cgst: float
    sgst: float
    igst: float
    grand_total: float
    created_by: str
    lines: list[SalesOrderLineOut]


class SalesOrderStatusIn(BaseModel):
    status: SalesOrderStatus


class DeliveryLineIn(BaseModel):
    product_id: str
    quantity: float


class DeliveryCreate(BaseModel):
    delivery_date: date
    sales_order_id: str
    vehicle_no: str = ""
    driver_name: str = ""
    lr_number: str = ""
    remarks: str = ""
    lines: list[DeliveryLineIn]


class DeliveryLineOut(BaseModel):
    id: int
    product_id: str
    product_name: str
    unit: str
    quantity: float

    model_config = ConfigDict(from_attributes=True)


class DeliveryOut(BaseModel):
    id: str
    delivery_no: str
    delivery_date: date
    sales_order_id: str | None
    so_no: str
    customer_id: str
    customer_name: str
    vehicle_no: str
    driver_name: str
    lr_number: str
    remarks: str
    created_by: str
    lines: list[DeliveryLineOut]

    model_config = ConfigDict(from_attributes=True)

class DispatchIn(BaseModel):
    dispatch_date: date
    delivery_id: str | None = None
    transporter: str = ""
    vehicle_no: str = ""
    driver_name: str = ""
    driver_phone: str = ""
    lr_number: str = ""
    status: DispatchStatus = DispatchStatus.planned
    delivered_on: date | None = None
    pod_ref: str = ""

class DispatchUpdateIn(BaseModel):
    transporter: str = ""
    vehicle_no: str = ""
    driver_name: str = ""
    driver_phone: str = ""
    lr_number: str = ""
    status: DispatchStatus = DispatchStatus.planned
    delivered_on: date | None = None
    pod_ref: str = ""

class DispatchStatusIn(BaseModel):
    status: DispatchStatus


class DispatchOut(ORMModel):
    id: str
    dispatch_no: str
    dispatch_date: date
    delivery_id: str | None
    delivery_no: str
    customer_id: str
    customer_name: str
    transporter: str
    vehicle_no: str
    driver_name: str
    driver_phone: str
    lr_number: str
    status: DispatchStatus
    delivered_on: date | None
    pod_ref: str
    created_by: str


# ---------- Purchasing, locations, and customer POs ----------
class SupplierProductIn(BaseModel):
    supplier_id: str
    product_id: str
    supplier_code: str
    purchase_rate: float
    minimum_order_qty: float
    lead_time_days: int


class SupplierProductOut(SupplierProductIn, ORMModel):
    id: str


class PlantIn(BaseModel):
    code: str
    name: str
    location: str
    active: bool


class PlantOut(PlantIn, ORMModel):
    id: str


class WarehouseIn(BaseModel):
    code: str
    name: str
    plant_id: str
    active: bool


class WarehouseOut(WarehouseIn, ORMModel):
    id: str


class PurchaseOrderLineIn(BaseModel):
    material_id: str | None = None
    material_name: str
    quantity: float
    rate: float
    gst_rate: float
    received_quantity: float = 0
    tax: float
    total: float


class PurchaseOrderLineOut(PurchaseOrderLineIn, ORMModel):
    id: int


class PurchaseOrderIn(BaseModel):
    po_no: str
    po_date: date
    expected_date: date | None = None
    supplier_id: str
    supplier_name: str
    warehouse_id: str | None = None
    notes: str
    status: PurchaseOrderStatus
    sub_total: float
    gst_total: float
    grand_total: float
    lines: list[PurchaseOrderLineIn] = Field(default_factory=list)


class PurchaseOrderOut(PurchaseOrderIn, ORMModel):
    id: str
    created_by: str
    lines: list[PurchaseOrderLineOut]


class GRNLineIn(BaseModel):
    material_id: str
    material_name: str
    quantity: float
    batch_no: str


class GRNLineOut(GRNLineIn, ORMModel):
    id: int


class GRNIn(BaseModel):
    grn_no: str
    grn_date: date
    purchase_order_id: str
    po_no: str
    warehouse_id: str
    lines: list[GRNLineIn] = Field(default_factory=list)


class GRNOut(GRNIn, ORMModel):
    id: str
    lines: list[GRNLineOut]


class CustomerPOLineIn(BaseModel):
    product_id: str | None = None
    product_name: str
    quantity: float
    rate: float | None = None


class CustomerPOLineOut(CustomerPOLineIn, ORMModel):
    id: int


class CustomerPOIn(BaseModel):
    po_no: str
    po_date: date
    customer_id: str
    customer_name: str
    delivery_date: date | None = None
    lines: list[CustomerPOLineIn] = Field(default_factory=list)


class CustomerPOOut(CustomerPOIn, ORMModel):
    id: str
    lines: list[CustomerPOLineOut]


# ---------- Manufacturing execution ----------
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

class EmployeeIn(BaseModel):
    emp_code: str
    name: str
    department: str = ""
    designation: str = ""
    active: bool = True

class EmployeeSkillIn(BaseModel):
    skill: str
    level: int = Field(default=1, ge=1, le=5)
    certified: bool = False
    active: bool = True

class EmployeeOut(ORMModel):
    id: str
    emp_code: str
    name: str
    department: str
    designation: str
    active: bool

class EmployeeSkillOut(ORMModel):
    id: str
    employee_id: str
    skill: str
    level: int
    certified: bool
    active: bool

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

class AssignEmployeeIn(BaseModel):
    employee_id: str | None = None

class ManufacturingAssignmentOut(BaseModel):
    operation_id: str
    workcenter_id: str
    employee_id: str | None
    assignment_mode: str
