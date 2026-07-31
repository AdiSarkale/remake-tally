"""Production routes: create batches (FG in, RM out) and list history."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.models import ItemKind, MovementType
from app.services.inventory import apply_movement, log_audit, next_batch_no

router = APIRouter(prefix="/production", tags=["production"])
guard = Depends(require_area("production"))


@router.get("", response_model=list[schemas.ProductionOut])
def list_production(db: Session = Depends(get_db), user: models.User = guard):
    return db.query(models.ProductionEntry).order_by(models.ProductionEntry.entry_date.desc()).all()


@router.post("", response_model=schemas.ProductionOut, status_code=201)
def create_production(payload: schemas.ProductionIn, db: Session = Depends(get_db), user: models.User = guard):
    batch_no = next_batch_no(db)
    entry = models.ProductionEntry(
        batch_no=batch_no,
        entry_date=payload.entry_date,
        product_id=payload.product_id,
        quantity=payload.quantity,
        machine=payload.machine,
        operator=payload.operator,
        shift=payload.shift,
        remarks=payload.remarks,
        consumption=[
            models.ProductionConsumption(material_id=c.material_id, quantity=c.quantity) for c in payload.consumption
        ],
    )
    db.add(entry)

    # Raw materials out first so a shortage aborts the whole batch.
    for line in payload.consumption:
        apply_movement(
            db,
            kind=ItemKind.material,
            item_id=line.material_id,
            movement_type=MovementType.OUT,
            quantity=line.quantity,
            reference=batch_no,
            reason="Production consumption",
            entry_date=payload.entry_date,
            user_id=user.id,
        )

    apply_movement(
        db,
        kind=ItemKind.product,
        item_id=payload.product_id,
        movement_type=MovementType.IN,
        quantity=payload.quantity,
        reference=batch_no,
        reason="Production output",
        entry_date=payload.entry_date,
        user_id=user.id,
    )

    log_audit(db, user.username, "CREATE", "production", f"{batch_no}: {payload.quantity} units")
    db.commit()
    db.refresh(entry)
    return entry
