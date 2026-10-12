"""Dispatch domain Pydantic schemas."""

from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.modules._base import Role, ItemKind, EmployeeType, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseRequisitionStatus, PurchaseRequisitionSource, PurchaseOrderStatus
from app.modules.core.schemas import ORMModel


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


# ---------- Purchase requisitions ----------
