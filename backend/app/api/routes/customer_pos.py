"""Database-backed customer purchase order CRUD and lookup."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.services.inventory import log_audit


router = APIRouter(
    prefix="/customer-pos",
    tags=["customer-pos"],
)

guard = Depends(require_area("sales"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_customer_po(db: Session, po_id: str) -> models.CustomerPO:
    row = (
        db.query(models.CustomerPO)
        .options(selectinload(models.CustomerPO.lines))
        .filter(models.CustomerPO.id == po_id)
        .first()
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer PO not found",
        )

    return row


# ---------------------------------------------------------------------------
# Customer Purchase Orders
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=list[schemas.CustomerPOOut],
)
def list_customer_pos(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return (
        db.query(models.CustomerPO)
        .options(selectinload(models.CustomerPO.lines))
        .order_by(models.CustomerPO.po_date.desc())
        .all()
    )


@router.get(
    "/lookup/{po_reference}",
    response_model=schemas.CustomerPOOut,
)
def lookup_customer_po(
    po_reference: str,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    po = (
        db.query(models.CustomerPO)
        .options(selectinload(models.CustomerPO.lines))
        .filter(
            models.CustomerPO.po_no == po_reference.strip()
        )
        .first()
    )

    if po is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer PO not found",
        )

    return po


@router.get(
    "/{po_id}",
    response_model=schemas.CustomerPOOut,
)
def get_customer_po(
    po_id: str,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return _get_customer_po(db, po_id)


@router.post(
    "",
    response_model=schemas.CustomerPOOut,
    status_code=status.HTTP_201_CREATED,
)
def create_customer_po(
    payload: schemas.CustomerPOIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    existing = (
        db.query(models.CustomerPO)
        .filter(models.CustomerPO.po_no == payload.po_no)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer PO number already exists",
        )

    row = models.CustomerPO(
        **payload.model_dump(exclude={"lines"}),
    )

    row.lines = [
        models.CustomerPOLine(**line.model_dump())
        for line in payload.lines
    ]

    db.add(row)

    log_audit(
        db,
        user.username,
        "CREATE",
        "customer_po",
        row.po_no,
    )

    db.commit()
    db.refresh(row)

    return row


@router.put(
    "/{po_id}",
    response_model=schemas.CustomerPOOut,
)
def update_customer_po(
    po_id: str,
    payload: schemas.CustomerPOIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    row = _get_customer_po(db, po_id)

    duplicate = (
        db.query(models.CustomerPO)
        .filter(
            models.CustomerPO.po_no == payload.po_no,
            models.CustomerPO.id != po_id,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer PO number already exists",
        )

    for key, value in payload.model_dump(exclude={"lines"}).items():
        setattr(row, key, value)

    row.lines.clear()

    for line in payload.lines:
        row.lines.append(
            models.CustomerPOLine(**line.model_dump())
        )

    log_audit(
        db,
        user.username,
        "UPDATE",
        "customer_po",
        row.po_no,
    )

    db.commit()
    db.refresh(row)

    return row


@router.delete(
    "/{po_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_customer_po(
    po_id: str,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    row = _get_customer_po(db, po_id)

    identifier = row.po_no

    db.delete(row)

    log_audit(
        db,
        user.username,
        "DELETE",
        "customer_po",
        identifier,
    )

    db.commit()
