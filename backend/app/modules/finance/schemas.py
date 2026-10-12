"""Finance domain Pydantic schemas."""

from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.modules._base import Role, ItemKind, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseOrderStatus
from app.modules.core.schemas import ORMModel


class CustomerPaymentIn(BaseModel):
    payment_date: date
    customer_id: str
    invoice_id: str | None = None
    amount: float = Field(gt=0)
    mode: str = Field(default="Bank Transfer", min_length=1, max_length=32)
    reference: str = ""
    remarks: str = ""

class CustomerPaymentOut(CustomerPaymentIn, ORMModel):
    id: str
    payment_no: str
    customer_name: str
    invoice_no: str
    created_by: str
    created_at: datetime

class SupplierPaymentIn(BaseModel):
    payment_date: date
    supplier_id: str
    purchase_order_id: str | None = None
    amount: float = Field(gt=0)
    mode: str = Field(default="Bank Transfer", min_length=1, max_length=32)
    reference: str = ""
    remarks: str = ""

class SupplierPaymentOut(SupplierPaymentIn, ORMModel):
    id: str
    payment_no: str
    supplier_name: str
    po_no: str
    created_by: str
    created_at: datetime

class ReceivableOut(BaseModel):
    invoice_id: str
    invoice_no: str
    invoice_date: date
    customer_id: str
    customer_name: str
    grand_total: float
    paid_amount: float
    balance_amount: float
    status: InvoiceStatus

class PayableOut(BaseModel):
    purchase_order_id: str
    po_no: str
    po_date: date
    supplier_id: str
    supplier_name: str
    grand_total: float
    paid_amount: float
    balance_amount: float
    status: PurchaseOrderStatus


# ---------- Dashboard ----------
