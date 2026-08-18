"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import InvoiceStatus, ItemKind, MovementType, Role, QuotationStatus, QuotationLine, SalesOrderStatus, DispatchStatus


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
    name: str
    unit: str = "KG"
    selling_rate: float = 0


class ScrapTypeOut(ScrapTypeIn, ORMModel):
    id: str
    stock: float


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
    quantity: float = Field(gt=0)


class ProductionIn(BaseModel):
    entry_date: date
    product_id: str
    quantity: float = Field(gt=0)
    machine: str = ""
    operator: str = ""
    shift: str = "A"
    remarks: str = ""
    consumption: list[ConsumptionIn]


class ProductionOut(ORMModel):
    id: str
    batch_no: str
    entry_date: date
    product_id: str
    quantity: float
    machine: str
    operator: str
    shift: str
    remarks: str


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
    gst_number: str = ""
    address: str = ""
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
