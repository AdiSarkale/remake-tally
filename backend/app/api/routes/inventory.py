"""Inventory routes: stock list, movement ledger and manual movements."""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.services.inventory import apply_movement, log_audit

router = APIRouter(prefix="/inventory", tags=["inventory"])
guard = Depends(require_area("inventory"))


@router.get("/movements", response_model=list[schemas.MovementOut])
def list_movements(limit: int = 200, db: Session = Depends(get_db), user: models.User = guard):
    return (
        db.query(models.InventoryMovement)
        .order_by(models.InventoryMovement.entry_date.desc(), models.InventoryMovement.id.desc())
        .limit(limit)
        .all()
    )


@router.post("/movements", response_model=schemas.MovementOut, status_code=201)
def create_movement(payload: schemas.MovementIn, db: Session = Depends(get_db), user: models.User = guard):
    movement = apply_movement(
        db,
        kind=payload.item_kind,
        item_id=payload.item_id,
        movement_type=payload.movement_type,
        quantity=payload.quantity,
        reference=payload.reference or "Manual entry",
        reason=payload.reason or "Manual stock movement",
        entry_date=payload.entry_date or date.today(),
        user_id=user.id,
    )
    log_audit(
        db,
        user.username,
        payload.movement_type.value,
        "inventory",
        f"{movement.item_name} {movement.movement_type.value} {movement.quantity} {movement.unit}",
    )
    db.commit()
    db.refresh(movement)
    return movement


@router.get("/valuation")
def valuation(db: Session = Depends(get_db), user: models.User = guard) -> dict[str, float]:
    fg = sum(p.stock * p.cost_price for p in db.query(models.Product).all())
    rm = sum(m.stock * m.cost for m in db.query(models.RawMaterial).all())
    sc = sum(s.stock * s.selling_rate for s in db.query(models.ScrapType).all())
    return {"finished_goods": fg, "raw_materials": rm, "scrap": sc, "total": fg + rm + sc}
