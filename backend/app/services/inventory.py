"""Inventory engine — the single place stock changes are applied.

Mirrors the frontend rules:
  Production  -> finished goods IN, raw materials OUT
  Scrap       -> scrap stock IN
  Purchase    -> raw materials IN
  Sales       -> finished goods OUT
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.models import ItemKind, MovementType


def _bucket(db: Session, kind: ItemKind, item_id: str):
    model = {
        ItemKind.product: models.Product,
        ItemKind.material: models.RawMaterial,
        ItemKind.scrap: models.ScrapType,
    }[kind]
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"{kind.value} {item_id} not found")
    return item


def apply_movement(
    db: Session,
    *,
    kind: ItemKind,
    item_id: str,
    movement_type: MovementType,
    quantity: float,
    reference: str,
    reason: str,
    entry_date: date,
    user_id: str,
    reservation_order_id: str | None = None,
    warehouse_id: str | None = None,
) -> models.InventoryMovement:
    item = _bucket(db, kind, item_id)
    warehouse_row = None
    warehouse_balance = None
    if warehouse_id:
        warehouse = db.get(models.Warehouse, warehouse_id)
        if warehouse is None or not warehouse.active:
            raise HTTPException(status_code=400, detail="Warehouse not found or inactive")
        warehouse_row = db.query(models.WarehouseStock).filter_by(warehouse_id=warehouse_id, item_kind=kind, item_id=item.id).with_for_update().first()
        warehouse_balance = float(warehouse_row.quantity) if warehouse_row else 0.0

    if movement_type is MovementType.IN:
        delta = quantity
    elif movement_type is MovementType.OUT:
        delta = -quantity
    else:  # ADJUST -> quantity is the counted physical stock
        delta = quantity - (warehouse_balance if warehouse_id else item.stock)

    if movement_type is MovementType.OUT and kind is ItemKind.material:
        reserved_query = db.query(func.coalesce(func.sum(models.StockReservation.quantity - models.StockReservation.consumed_quantity), 0.0)).filter(
            models.StockReservation.material_id == item.id,
            models.StockReservation.status == "Reserved",
        )
        if reservation_order_id:
            reserved_query = reserved_query.filter(models.StockReservation.production_order_id != reservation_order_id)
        reserved_for_others = float(reserved_query.scalar() or 0.0)
        available_to_consume = round(float(item.stock) - reserved_for_others, 3)
        if quantity > available_to_consume:
            raise HTTPException(status_code=400, detail=f"Insufficient unreserved stock for {item.name} (required {quantity}, available {max(available_to_consume, 0.0)})")

    if warehouse_id:
        new_wh_balance = round((warehouse_balance or 0.0) + delta, 3)
        if new_wh_balance < 0:
            raise HTTPException(status_code=400, detail=f"Insufficient stock in warehouse for {item.name} (available {warehouse_balance or 0.0})")
        if warehouse_row is None:
            warehouse_row = models.WarehouseStock(warehouse_id=warehouse_id, item_kind=kind, item_id=item.id, item_name=item.name, quantity=new_wh_balance, unit=item.unit)
            db.add(warehouse_row)
        else:
            warehouse_row.quantity = new_wh_balance
    new_balance = round(item.stock + delta, 3)
    if new_balance < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient stock for {item.name} (available {item.stock})",
        )
    item.stock = new_balance

    movement = models.InventoryMovement(
        entry_date=entry_date,
        item_kind=kind,
        item_id=item.id,
        item_name=item.name,
        movement_type=movement_type,
        quantity=abs(delta) if movement_type is MovementType.ADJUST else quantity,
        unit=item.unit,
        balance=new_balance,
        reference=reference,
        reason=reason,
        user_id=user_id,
        warehouse_id=warehouse_id,
    )
    db.add(movement)
    db.flush()
    return movement


def log_audit(db: Session, username: str, action: str, entity: str, detail: str) -> None:
    db.add(models.AuditLog(username=username, action=action, entity=entity, detail=detail))


def next_batch_no(db: Session) -> str:
    count = db.query(models.ProductionEntry).count()
    return f"BATCH-{count + 1:04d}"
