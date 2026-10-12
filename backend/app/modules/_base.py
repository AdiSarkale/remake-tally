"""Shared identifiers and enums used across domain models."""

from __future__ import annotations

import enum
import uuid

def _uuid() -> str:
    return str(uuid.uuid4())

class Role(str, enum.Enum):
    admin = "Admin"
    accountant = "Accountant"
    operator = "Operator"
    hr = "HR"

class ItemKind(str, enum.Enum):
    product = "product"
    material = "material"
    scrap = "scrap"

class EmployeeType(str, enum.Enum):
    shop_floor = "shop_floor"
    staff = "staff"

class MovementType(str, enum.Enum):
    IN = "IN"
    OUT = "OUT"
    ADJUST = "ADJUST"

class InvoiceStatus(str, enum.Enum):
    unpaid = "Unpaid"
    paid = "Paid"
    cancelled = "Cancelled"
    partial = 'Partial'

class QuotationStatus(str, enum.Enum):
    draft = 'Draft'
    sent = 'Sent'
    accepted = 'Accepted'
    rejected = 'Rejected'
    expired = 'Expired'
    converted = 'Converted'

class SalesOrderStatus(str, enum.Enum):
    open = "Open"
    partially_delivered = "Partially Delivered"
    delivered = "Delivered"
    invoiced = "Invoiced"
    cancelled = "Cancelled"

class DispatchStatus(str, enum.Enum):
    planned = "Planned"
    loading = "Loading"
    in_transit = "In Transit"
    delivered = "Delivered"
    delayed = "Delayed"

class PurchaseRequisitionStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"
    converted = "converted"

class PurchaseRequisitionSource(str, enum.Enum):
    manual = "manual"
    mrp = "mrp"

class PurchaseOrderStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    partially_received = "partially_received"
    received = "received"
