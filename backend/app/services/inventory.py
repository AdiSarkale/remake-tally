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
) -> models.InventoryMovement:
    item = _bucket(db, kind, item_id)

    if movement_type is MovementType.IN:
        delta = quantity
    elif movement_type is MovementType.OUT:
        delta = -quantity
    else:  # ADJUST -> quantity is the counted physical stock
        delta = quantity - item.stock

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
    )
    db.add(movement)
    db.flush()
    return movement


def log_audit(db: Session, username: str, action: str, entity: str, detail: str) -> None:
    db.add(models.AuditLog(username=username, action=action, entity=entity, detail=detail))


def next_batch_no(db: Session) -> str:
    count = db.query(models.ProductionEntry).count()
    return f"BATCH-{count + 1:04d}"
