"""Dashboard domain Pydantic schemas."""

from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.modules._base import Role, ItemKind, EmployeeType, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseRequisitionStatus, PurchaseRequisitionSource, PurchaseOrderStatus
from app.modules.core.schemas import ORMModel


class ScrapReasonOut(BaseModel):
    reason: str
    quantity: float

class ProductionSeriesOut(BaseModel):
    date: date
    label: str
    produced: float
    scrap: float

class RecentProductionOut(BaseModel):
    id: str
    batch_no: str
    entry_date: date
    product_name: str
    quantity: float
    machine: str
    operator: str
    shift: str

class LowStockOut(BaseModel):
    id: str
    name: str
    stock: float
    min_stock: float
    unit: str
    kind: str

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
