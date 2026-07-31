"""Scrap routes: record scrap (scrap stock IN) and list entries."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.models import ItemKind, MovementType
from app.services.inventory import apply_movement, log_audit

router = APIRouter(prefix="/scrap", tags=["scrap"])
guard = Depends(require_area("scrap"))


@router.get("", response_model=list[schemas.ScrapOut])
def list_scrap(db: Session = Depends(get_db), user: models.User = guard):
    return db.query(models.ScrapEntry).order_by(models.ScrapEntry.entry_date.desc()).all()


@router.post("", response_model=schemas.ScrapOut, status_code=201)
def create_scrap(payload: schemas.ScrapIn, db: Session = Depends(get_db), user: models.User = guard):
    entry = models.ScrapEntry(**payload.model_dump())
    db.add(entry)
    apply_movement(
        db,
        kind=ItemKind.scrap,
        item_id=payload.scrap_type_id,
        movement_type=MovementType.IN,
        quantity=payload.quantity,
        reference=payload.batch_no or "-",
        reason=f"Scrap: {payload.reason}",
        entry_date=payload.entry_date,
        user_id=user.id,
    )
    log_audit(db, user.username, "CREATE", "scrap", f"{payload.quantity} units — {payload.reason}")
    db.commit()
    db.refresh(entry)
    return entry
