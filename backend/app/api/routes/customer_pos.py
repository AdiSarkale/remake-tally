"""Customer PO lookup for quotation creation."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db

router = APIRouter(prefix="/sales/customer-pos", tags=["customer-pos"])
guard = Depends(require_area("sales"))


@router.get("/lookup/{po_reference}", response_model=schemas.CustomerPOOut)
def lookup_customer_po(
    po_reference: str,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    po = db.query(models.CustomerPO).filter(models.CustomerPO.po_no == po_reference.strip()).first()
    if po is None:
        raise HTTPException(404, "Customer PO not found")
    return po
