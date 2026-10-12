"""Inventory domain Pydantic schemas."""

from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.modules._base import Role, ItemKind, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseOrderStatus
from app.modules.core.schemas import ORMModel


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
