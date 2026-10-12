"""Purchasing domain Pydantic schemas."""

from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.modules._base import Role, ItemKind, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseOrderStatus
from app.modules.core.schemas import ORMModel


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
