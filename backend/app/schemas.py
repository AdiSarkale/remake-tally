"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import InvoiceStatus, ItemKind, MovementType, Role


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


# ---------- Dashboard / settings ----------
class DashboardOut(BaseModel):
    produced_today: float
    produced_month: float
    scrap_month: float
    scrap_rate: float
    inventory_value: float
    low_stock_count: int


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
class InvoiceLineIn(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    rate: float = Field(ge=0)
    discount_percent: float = Field(default=0, ge=0, le=100)


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
    status: InvoiceStatus = InvoiceStatus.unpaid
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
    status: InvoiceStatus
    lines: list[InvoiceLineOut]


class InvoiceStatusIn(BaseModel):
    status: InvoiceStatus
