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
    email: str = ""
    active: bool = True
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    full_name: str = Field(min_length=1, max_length=120)
    role: Role = Role.operator
    password: str = Field(min_length=6, max_length=128)
class UserUpdate(BaseModel):
class PasswordReset(BaseModel):
    """Admin reset — the target user's current password is NOT required."""
    new_password: str = Field(min_length=6, max_length=128)
class PasswordChange(BaseModel):
    current_password: str
# ---------- Masters ----------
class PartyIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    gst_number: str = ""
    phone: str = ""
    address: str = ""
class PartyOut(PartyIn, ORMModel):
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
    stock: float
class RawMaterialIn(BaseModel):
    unit: str = "KG"
    cost: float = 0
class RawMaterialOut(RawMaterialIn, ORMModel):
class ScrapReasonOut(BaseModel):
    reason: str
    quantity: float
class ScrapTypeIn(BaseModel):
    selling_rate: float = 0
class ScrapTypeOut(ScrapTypeIn, ORMModel):
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
    entry_date: date
    item_name: str
    unit: str
    balance: float
    reference: str
# ---------- Production ----------
class ConsumptionIn(BaseModel):
    material_id: str
    quantity: float = Field(gt=0)
class ProductionIn(BaseModel):
    product_id: str
    machine: str = ""
    operator: str = ""
    shift: str = "A"
    remarks: str = ""
    consumption: list[ConsumptionIn]
class ProductionOut(ORMModel):
    batch_no: str
    machine: str
    operator: str
    shift: str
    remarks: str
# ---------- Scrap ----------
class ScrapIn(BaseModel):
    batch_no: str = ""
    scrap_type_id: str
class ScrapOut(ScrapIn, ORMModel):
# ---------- Dashboard ----------
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
    at: datetime
    action: str
    entity: str
    detail: str
class SettingsIn(BaseModel):
    invoice_prefix: str = "INV"
    financial_year: str = "2026-2027"
class SettingsOut(SettingsIn, ORMModel):
    id: int
# ---------- Sales invoices ----------
class InvoiceLineIn(BaseModel):
    quantity: float = Field(
        gt=0,
    )
    rate: float = Field(
        ge=0,
    discount_percent: float = Field(
        default=0,
        le=100,
    # None = use product master GST.
    # A number = custom GST for this invoice line.
    gst_rate: float | None = Field(
        default=None,
class InvoiceLineOut(ORMModel):
    hsn: str
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
    lines: list[InvoiceLineIn] = Field(
        min_length=1,
class InvoiceOut(ORMModel):
    invoice_no: str
    customer_name: str
    po_reference: str
    notes: str
    inter_state: bool
    sub_total: float
    discount_total: float
    taxable_total: float
    round_off: float
    grand_total: float
    paid_amount: float
    balance_amount: float
    status: InvoiceStatus
    lines: list[InvoiceLineOut]
class InvoiceStatusIn(BaseModel):
    # Required when changing to Partial.
    # Optional for Paid/Unpaid; backend derives the amount.
class QuotationIn(BaseModel):
    quotation_date : date
    valid_until : date | None = None
    customer_id : str
    po_reference: str = ''
    notes: str = ''
    status :QuotationStatus = QuotationStatus.draft
    lines: list["QuotationLineIn"]
class QuotationLineIn(BaseModel):
    rate: float = Field(ge=0)
    # None = use product's GST
    # Number = custom GST for this quotation line
class QuotationLineOut(ORMModel):
class QuotationOut(ORMModel):
    quotation_no: str
    quotation_date: date
    valid_until: date | None
    status: QuotationStatus
    created_by: str
    lines: list[QuotationLineOut]
class QuotationStatusIn(BaseModel):
class SalesOrderLineOut(ORMModel):
    delivered_quantity: float
class SalesOrderOut(ORMModel):
    so_no: str
    order_date: date
    delivery_date: date | None
    status: SalesOrderStatus
    quote_id: str | None
    quote_no: str
    lines: list[SalesOrderLineOut]
class SalesOrderStatusIn(BaseModel):
class DeliveryLineIn(BaseModel):
class DeliveryCreate(BaseModel):
    delivery_date: date
    sales_order_id: str
    vehicle_no: str = ""
    driver_name: str = ""
    lr_number: str = ""
    lines: list[DeliveryLineIn]
class DeliveryLineOut(BaseModel):
class DeliveryOut(BaseModel):
    delivery_no: str
    sales_order_id: str | None
    vehicle_no: str
    driver_name: str
    lr_number: str
    lines: list[DeliveryLineOut]
class DispatchIn(BaseModel):
    dispatch_date: date
    delivery_id: str | None = None
    transporter: str = ""
    driver_phone: str = ""
    status: DispatchStatus = DispatchStatus.planned
    delivered_on: date | None = None
    pod_ref: str = ""
class DispatchStatusIn(BaseModel):
    status: DispatchStatus
class DispatchOut(ORMModel):
    dispatch_no: str
    delivery_id: str | None
    transporter: str
    driver_phone: str
    delivered_on: date | None
    pod_ref: str
"""Merge these schemas into app/schemas.py."""
# required imports if not already present in schemas.py
from datetime import date
from pydantic import BaseModel, Field
from app import models
class PlantOut(ORMModel):
    location: str
    active: bool
class WarehouseOut(ORMModel):
    plant_id: str
class SupplierProductOut(ORMModel):
    supplier_id: str
    supplier_code: str
    purchase_rate: float
    minimum_order_qty: float
    lead_time_days: int
class PurchaseOrderLineIn(BaseModel):
    gst_rate: float = Field(ge=0, le=100, default=18)
class PurchaseOrderIn(BaseModel):
    po_date: date
    expected_date: date | None = None
    warehouse_id: str | None = None
    lines: list[PurchaseOrderLineIn]
class PurchaseOrderStatusIn(BaseModel):
    status: models.PurchaseOrderStatus
class PurchaseOrderLineOut(ORMModel):
    material_name: str
    received_quantity: float
    tax: float
class PurchaseOrderOut(ORMModel):
    po_no: str
    expected_date: date | None
    supplier_name: str
    warehouse_id: str | None
    gst_total: float
    lines: list[PurchaseOrderLineOut]
class GRNLineIn(BaseModel):
class GRNIn(BaseModel):
    grn_date: date
    purchase_order_id: str
    warehouse_id: str
    lines: list[GRNLineIn]
class GRNLineOut(ORMModel):
class GRNOut(ORMModel):
    grn_no: str
    lines: list[GRNLineOut]
class CustomerPOLineOut(ORMModel):
    rate: float | None
class CustomerPOOut(ORMModel):
    lines: list[CustomerPOLineOut]
class DispatchUpdateIn(BaseModel):
    status: models.DispatchStatus
class DeliveryIn(BaseModel):
    sales_order_id: str | None = None
    customer_id: str | None = None
