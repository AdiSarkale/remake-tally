"""Pydantic request/response schemas."""
from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models import InvoiceStatus, ItemKind, MovementType, Role, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseOrderStatus

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    email: str = ""
    active: bool = True

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    full_name: str = Field(min_length=1, max_length=120)
    role: Role = Role.operator
    password: str = Field(min_length=6, max_length=128)

class UserUpdate(BaseModel):
    full_name: str | None = None
    role: Role | None = None
    email: str | None = None
    active: bool | None = None

class PasswordReset(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=128)

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
    code: str
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
    code: str
    name: str
    unit: str = "KG"
    selling_rate: float = 0
    active: bool = True

class ScrapTypeOut(ScrapTypeIn, ORMModel):
    id: str

class MovementIn(BaseModel):
    item_kind: ItemKind
    item_id: str
    movement_type: MovementType
    quantity: float = Field(ge=0)
    reference: str = ""
    reason: str = ""
    entry_date: date | None = None

class MovementOut(ORMModel):
    id: int
    entry_date: date
    item_name: str
    unit: str
    balance: float
    reference: str
    reason: str
    movement_type: MovementType
    quantity: float

class ConsumptionIn(BaseModel):
    material_id: str
    quantity: float = Field(gt=0)

class ProductionIn(BaseModel):
    product_id: str
    machine: str = ""
    operator: str = ""
    shift: str = "A"
    remarks: str = ""
    consumption: list[ConsumptionIn] = []

class ProductionOut(ORMModel):
    id: str
    batch_no: str
    product_id: str
    machine: str
    operator: str
    shift: str
    remarks: str

class ScrapIn(BaseModel):
    batch_no: str = ""
    scrap_type_id: str
    quantity: float = Field(gt=0)
    reason: str = ""

class ScrapOut(ScrapIn, ORMModel):
    id: str

class ProductionSeriesOut(BaseModel):
    date: date
    label: str
    produced: float
    scrap: float

class RecentProductionOut(BaseModel):
    product_name: str

class LowStockOut(BaseModel):
    min_stock: float

class DashboardOut(BaseModel):
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
    production_series: list[ProductionSeriesOut]
    recent_production: list[RecentProductionOut]
    low_stock_items: list[LowStockOut]
    top_scrap_reasons: list[ScrapReasonOut]

class AuditOut(ORMModel):
    id: int
    at: datetime
    username: str
    action: str
    entity: str
    detail: str

class SettingsIn(BaseModel):
    invoice_prefix: str = "INV"
    financial_year: str = "2026-2027"

class SettingsOut(SettingsIn, ORMModel):
    id: int

class InvoiceLineIn(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    rate: float = Field(ge=0)
    discount_percent: float = Field(default=0, ge=0, le=100)
    gst_rate: float | None = Field(default=None, ge=0, le=100)

class InvoiceLineOut(ORMModel):
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

class InvoiceIn(BaseModel):
    invoice_date: date
    customer_id: str
    po_reference: str = ""
    notes: str = ""
    status: InvoiceStatus = InvoiceStatus.unpaid
    paid_percent: float = Field(default=0, ge=0, le=100)
    lines: list[InvoiceLineIn] = Field(min_length=1)

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
    paid_percent: float | None = Field(default=None, ge=0, le=100)

class QuotationLineIn(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    rate: float = Field(ge=0)
    discount_percent: float = Field(default=0, ge=0, le=100)
    gst_rate: float | None = Field(default=None, ge=0, le=100)

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

class QuotationIn(BaseModel):
    quotation_date: date
    valid_until: date | None = None
    customer_id: str
    po_reference: str = ""
    notes: str = ""
    status: QuotationStatus = QuotationStatus.draft
    lines: list[QuotationLineIn] = Field(min_length=1)

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
    quantity: float
    delivered_quantity: float
    rate: float
    gst_rate: float
    taxable: float
    cgst: float
    sgst: float
    igst: float
    total: float

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
    lines: list[SalesOrderLineOut]

class SalesOrderStatusIn(BaseModel):
    status: SalesOrderStatus

class DeliveryLineIn(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)

class DeliveryCreate(BaseModel):
    delivery_date: date
    sales_order_id: str | None = None
    customer_id: str | None = None
    vehicle_no: str = ""
    driver_name: str = ""
    lr_number: str = ""
    lines: list[DeliveryLineIn] = Field(min_length=1)

class DeliveryLineOut(ORMModel):
    id: int
    product_id: str
    product_name: str
    quantity: float

class DeliveryOut(ORMModel):
    id: str
    delivery_no: str
    delivery_date: date
    sales_order_id: str | None
    customer_id: str
    customer_name: str
    vehicle_no: str
    driver_name: str
    lr_number: str
    remarks: str
    lines: list[DeliveryLineOut]

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
    status: DispatchStatus
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

class PlantOut(ORMModel):
    id: str
    code: str
    name: str
    location: str
    active: bool

class WarehouseOut(ORMModel):
    id: str
    code: str
    name: str
    plant_id: str
    active: bool

class SupplierProductOut(ORMModel):
    id: str
    supplier_id: str
    product_id: str
    supplier_code: str
    purchase_rate: float
    minimum_order_qty: float
    lead_time_days: int

class PurchaseOrderLineIn(BaseModel):
    material_id: str | None = None
    material_name: str
    quantity: float = Field(gt=0)
    rate: float = Field(ge=0)
    gst_rate: float = Field(ge=0, le=100, default=18)

class PurchaseOrderIn(BaseModel):
    po_date: date
    supplier_id: str
    expected_date: date | None = None
    warehouse_id: str | None = None
    notes: str = ""
    lines: list[PurchaseOrderLineIn] = Field(min_length=1)

class PurchaseOrderStatusIn(BaseModel):
    status: PurchaseOrderStatus

class PurchaseOrderLineOut(ORMModel):
    id: int
    material_id: str | None
    material_name: str
    quantity: float
    rate: float
    gst_rate: float
    received_quantity: float
    tax: float
    total: float

class PurchaseOrderOut(ORMModel):
    id: str
    po_no: str
    po_date: date
    expected_date: date | None
    supplier_id: str
    supplier_name: str
    warehouse_id: str | None
    notes: str
    status: PurchaseOrderStatus
    sub_total: float
    gst_total: float
    grand_total: float
    lines: list[PurchaseOrderLineOut]

class GRNLineIn(BaseModel):
    material_id: str
    quantity: float = Field(gt=0)
    batch_no: str = ""

class GRNIn(BaseModel):
    grn_date: date
    purchase_order_id: str
    warehouse_id: str
    lines: list[GRNLineIn] = Field(min_length=1)

class GRNLineOut(ORMModel):
    id: int
    material_id: str
    material_name: str
    quantity: float
    batch_no: str

class GRNOut(ORMModel):
    id: str
    grn_no: str
    grn_date: date
    purchase_order_id: str
    po_no: str
    warehouse_id: str
    lines: list[GRNLineOut]

class CustomerPOLineOut(ORMModel):
    id: int
    product_id: str | None
    product_name: str
    quantity: float
    rate: float | None

class CustomerPOOut(ORMModel):
    id: str
    po_no: str
    po_date: date
    customer_id: str
    customer_name: str
    delivery_date: date | None
    lines: list[CustomerPOLineOut]

class DeliveryIn(BaseModel):
    sales_order_id: str | None = None
    customer_id: str | None = None
    delivery_date: date
    vehicle_no: str = ""
    driver_name: str = ""
    lr_number: str = ""
    lines: list[DeliveryLineIn] = Field(min_length=1)
