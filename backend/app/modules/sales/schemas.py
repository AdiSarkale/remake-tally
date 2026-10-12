"""Sales domain Pydantic schemas."""

from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.modules._base import Role, ItemKind, EmployeeType, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseRequisitionStatus, PurchaseRequisitionSource, PurchaseOrderStatus
from app.modules.core.schemas import ORMModel


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
