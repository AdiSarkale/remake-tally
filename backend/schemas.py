"""Merge these schemas into app/schemas.py."""

# required imports if not already present in schemas.py
from datetime import date
from pydantic import BaseModel, Field
from app import models

class PlantOut(ORMModel):
    id: str
    code: str
    name: str
    location: str
    active: bool


class WarehouseOut(ORMModel):
    id: str
    plant_id: str
    code: str
    name: str
    location: str
    active: bool


class SupplierProductOut(ORMModel):
    id: int
    supplier_id: str
    product_id: str
    supplier_code: str
    purchase_rate: float
    minimum_order_qty: float
    lead_time_days: int
    active: bool


class PurchaseOrderLineIn(BaseModel):
    material_id: str
    quantity: float = Field(gt=0)
    rate: float = Field(ge=0)
    gst_rate: float = Field(ge=0, le=100, default=18)


class PurchaseOrderIn(BaseModel):
    po_date: date
    expected_date: date | None = None
    supplier_id: str
    warehouse_id: str | None = None
    notes: str = ""
    lines: list[PurchaseOrderLineIn]


class PurchaseOrderStatusIn(BaseModel):
    status: models.PurchaseOrderStatus


class PurchaseOrderLineOut(ORMModel):
    id: int
    material_id: str
    material_name: str
    unit: str
    quantity: float
    received_quantity: float
    rate: float
    gst_rate: float
    taxable: float
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
    status: models.PurchaseOrderStatus
    sub_total: float
    gst_total: float
    grand_total: float
    created_by: str
    lines: list[PurchaseOrderLineOut]


class GRNLineIn(BaseModel):
    material_id: str
    quantity: float = Field(gt=0)
    batch_no: str = ""


class GRNIn(BaseModel):
    grn_date: date
    purchase_order_id: str
    warehouse_id: str
    remarks: str = ""
    lines: list[GRNLineIn]


class GRNLineOut(ORMModel):
    id: int
    material_id: str
    material_name: str
    unit: str
    quantity: float
    batch_no: str


class GRNOut(ORMModel):
    id: str
    grn_no: str
    grn_date: date
    purchase_order_id: str
    po_no: str
    supplier_id: str
    supplier_name: str
    warehouse_id: str
    remarks: str
    created_by: str
    lines: list[GRNLineOut]


class CustomerPOLineOut(ORMModel):
    id: int
    product_id: str
    product_name: str
    quantity: float
    rate: float | None
    notes: str


class CustomerPOOut(ORMModel):
    id: str
    po_no: str
    po_date: date
    customer_id: str
    customer_name: str
    delivery_date: date | None
    notes: str
    lines: list[CustomerPOLineOut]


class DispatchUpdateIn(BaseModel):
    transporter: str = ""
    vehicle_no: str = ""
    driver_name: str = ""
    driver_phone: str = ""
    lr_number: str = ""
    status: models.DispatchStatus
    delivered_on: date | None = None
    pod_ref: str = ""


class DeliveryLineIn(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)


class DeliveryIn(BaseModel):
    delivery_date: date
    sales_order_id: str | None = None
    customer_id: str | None = None
    warehouse_id: str | None = None
    vehicle_no: str = ""
    driver_name: str = ""
    lr_number: str = ""
    remarks: str = ""
    lines: list[DeliveryLineIn]
