"""Quotation routes: create, list, view, update status, and convert to invoice."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.services.gst import compute_line, is_inter_state, round_off
from app.services.inventory import log_audit

router = APIRouter(
    prefix="/quotations",
    tags=["quotations"],
)

guard = Depends(require_area("sales"))


def _settings(db: Session) -> models.CompanySettings:
    row = db.get(models.CompanySettings, 1)

    if row is None:
        row = models.CompanySettings(id=1)
        db.add(row)
        db.flush()

    return row


def next_quotation_no(
    db: Session,
    prefix: str = "QT",
) -> str:
    """Generate sequential quotation number."""

    numbers = [
        int(tail)
        for (no,) in db.query(
            models.Quotation.quotation_no
        )
        .filter(
            models.Quotation.quotation_no.like(
                f"{prefix}%"
            )
        )
        .all()
        if (
            tail := "".join(
                ch
                for ch in no[len(prefix):]
                if ch.isdigit()
            )
        )
    ]

    return f"{prefix}{(max(numbers) + 1 if numbers else 1):04d}"


# =========================================================
# List quotations
# =========================================================

@router.get(
    "",
    response_model=list[schemas.QuotationOut],
)
def list_quotations(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return (
        db.query(models.Quotation)
        .order_by(
            models.Quotation.quotation_date.desc(),
            models.Quotation.quotation_no.desc(),
        )
        .all()
    )


# =========================================================
# Next quotation number
# =========================================================

@router.get("/next-number")
def peek_next_quotation_number(
    db: Session = Depends(get_db),
    user: models.User = guard,
) -> dict[str, str]:

    settings = _settings(db)

    return {
        "quotation_no": next_quotation_no(
            db,
            "QT",
        )
    }


# =========================================================
# Get quotation
# =========================================================

@router.get(
    "/{quotation_id}",
    response_model=schemas.QuotationOut,
)
def get_quotation(
    quotation_id: str,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    quotation = db.get(
        models.Quotation,
        quotation_id,
    )

    if quotation is None:
        raise HTTPException(
            status_code=404,
            detail="Quotation not found",
        )

    return quotation


# =========================================================
# Create quotation
# =========================================================

@router.post(
    "",
    response_model=schemas.QuotationOut,
    status_code=201,
)
def create_quotation(
    payload: schemas.QuotationIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    # -----------------------------------------------------
    # Customer
    # -----------------------------------------------------

    customer = db.get(
        models.Party,
        payload.customer_id,
    )

    if customer is None or customer.kind != "customer":
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    if not payload.lines:
        raise HTTPException(
            status_code=400,
            detail="Quotation must contain at least one product",
        )

    # -----------------------------------------------------
    # Validity date
    # -----------------------------------------------------

    if (
        payload.valid_until is not None
        and payload.valid_until < payload.quotation_date
    ):
        raise HTTPException(
            status_code=400,
            detail="Valid until date cannot be before quotation date",
        )

    # -----------------------------------------------------
    # Duplicate products
    # -----------------------------------------------------

    product_ids = [
        line.product_id
        for line in payload.lines
    ]

    if len(set(product_ids)) != len(product_ids):
        raise HTTPException(
            status_code=400,
            detail=(
                "The same product is listed twice — "
                "merge those lines"
            ),
        )

    # -----------------------------------------------------
    # GST
    # -----------------------------------------------------

    settings = _settings(db)

    inter_state = is_inter_state(
        settings.gst_number,
        customer.gst_number,
    )

    # -----------------------------------------------------
    # Quotation
    # -----------------------------------------------------

    quotation = models.Quotation(
        quotation_no=next_quotation_no(
            db,
            "QT",
        ),
        quotation_date=payload.quotation_date,
        valid_until=payload.valid_until,
        customer_id=customer.id,
        customer_name=customer.name,
        po_reference=payload.po_reference,
        notes=payload.notes,
        inter_state=int(inter_state),
        status=payload.status,
        created_by=user.username,

        sub_total=0.0,
        discount_total=0.0,
        taxable_total=0.0,
        cgst=0.0,
        sgst=0.0,
        igst=0.0,
        round_off=0.0,
        grand_total=0.0,
    )

    sub_total = 0.0
    discount_total = 0.0

    # -----------------------------------------------------
    # Lines
    # -----------------------------------------------------

    for line in payload.lines:

        product = db.get(
            models.Product,
            line.product_id,
        )

        if product is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Product {line.product_id} not found"
                ),
            )

        # Custom GST if provided.
        # Otherwise use product GST.
        gst_rate = (
            line.gst_rate
            if line.gst_rate is not None
            else product.gst_rate
        )

        tax = compute_line(
            quantity=line.quantity,
            rate=line.rate,
            discount_percent=line.discount_percent,
            gst_rate=gst_rate,
            inter_state=inter_state,
        )

        gross = round(
            line.quantity * line.rate,
            2,
        )

        sub_total += gross

        discount_total += round(
            gross - tax.taxable,
            2,
        )

        quotation.lines.append(
            models.QuotationLine(
                product_id=product.id,
                product_name=product.name,
                hsn=product.hsn,
                unit=product.unit,
                quantity=line.quantity,
                rate=line.rate,
                discount_percent=line.discount_percent,
                gst_rate=gst_rate,
                taxable=tax.taxable,
                cgst=tax.cgst,
                sgst=tax.sgst,
                igst=tax.igst,
                total=tax.total,
            )
        )

        quotation.taxable_total += tax.taxable
        quotation.cgst += tax.cgst
        quotation.sgst += tax.sgst
        quotation.igst += tax.igst

    # -----------------------------------------------------
    # Final totals
    # -----------------------------------------------------

    quotation.sub_total = round(
        sub_total,
        2,
    )

    quotation.discount_total = round(
        discount_total,
        2,
    )

    quotation.taxable_total = round(
        quotation.taxable_total,
        2,
    )

    quotation.cgst = round(
        quotation.cgst,
        2,
    )

    quotation.sgst = round(
        quotation.sgst,
        2,
    )

    quotation.igst = round(
        quotation.igst,
        2,
    )

    pre_round = (
        quotation.taxable_total
        + quotation.cgst
        + quotation.sgst
        + quotation.igst
    )

    quotation.grand_total, quotation.round_off = (
        round_off(pre_round)
    )

    # -----------------------------------------------------
    # IMPORTANT:
    # No inventory movement here.
    # -----------------------------------------------------

    db.add(quotation)

    log_audit(
        db,
        user.username,
        "CREATE",
        "quotation",
        (
            f"{quotation.quotation_no} · "
            f"{customer.name}"
        ),
    )

    db.commit()
    db.refresh(quotation)

    return quotation


# =========================================================
# Update quotation status
# =========================================================

@router.patch(
    "/{quotation_id}/status",
    response_model=schemas.QuotationOut,
)
def set_quotation_status(
    quotation_id: str,
    payload: schemas.QuotationStatusIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    quotation = db.get(
        models.Quotation,
        quotation_id,
    )

    if quotation is None:
        raise HTTPException(
            status_code=404,
            detail="Quotation not found",
        )

    if quotation.status is models.QuotationStatus.converted:
        raise HTTPException(
            status_code=400,
            detail="Converted quotation cannot be changed",
        )

    quotation.status = payload.status

    log_audit(
        db,
        user.username,
        "UPDATE",
        "quotation",
        (
            f"{quotation.quotation_no} -> "
            f"{quotation.status.value}"
        ),
    )

    db.commit()
    db.refresh(quotation)

    return quotation
