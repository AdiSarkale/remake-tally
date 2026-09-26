"""Sales order routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.services.inventory import log_audit


router = APIRouter(
    prefix="/sales-orders",
    tags=["sales-orders"],
)

guard = Depends(require_area("sales"))


def next_sales_order_no(
    db: Session,
    prefix: str = "SO",
) -> str:
    numbers = [
        int(tail)
        for (no,) in (
            db.query(models.SalesOrder.so_no)
            .filter(
                models.SalesOrder.so_no.like(
                    f"{prefix}%"
                )
            )
            .all()
        )
        if (
            tail := "".join(
                ch
                for ch in no[len(prefix):]
                if ch.isdigit()
            )
        )
    ]

    return f"{prefix}{(max(numbers) + 1 if numbers else 1):04d}"


@router.get(
    "",
    response_model=list[schemas.SalesOrderOut],
)
def list_sales_orders(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return (
        db.query(models.SalesOrder)
        .order_by(
            models.SalesOrder.order_date.desc(),
            models.SalesOrder.so_no.desc(),
        )
        .all()
    )


@router.get(
    "/next-number",
)
def peek_next_sales_order_number(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return {
        "so_no": next_sales_order_no(
            db,
            "SO",
        )
    }


@router.get(
    "/{sales_order_id}",
    response_model=schemas.SalesOrderOut,
)
def get_sales_order(
    sales_order_id: str,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    sales_order = db.get(
        models.SalesOrder,
        sales_order_id,
    )

    if sales_order is None:
        raise HTTPException(
            status_code=404,
            detail="Sales order not found",
        )

    return sales_order


@router.patch(
    "/{sales_order_id}/status",
    response_model=schemas.SalesOrderOut,
)
def set_sales_order_status(
    sales_order_id: str,
    payload: schemas.SalesOrderStatusIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    sales_order = db.get(
        models.SalesOrder,
        sales_order_id,
    )

    if sales_order is None:
        raise HTTPException(
            status_code=404,
            detail="Sales order not found",
        )

    sales_order.status = payload.status

    log_audit(
        db,
        user.username,
        "UPDATE",
        "sales_order",
        (
            f"{sales_order.so_no} -> "
            f"{sales_order.status.value}"
        ),
    )

    db.commit()
    db.refresh(sales_order)

    return sales_order

@router.post(
    "/from-quotation/{quotation_id}",
    response_model=schemas.SalesOrderOut,
    status_code=201,
)
def create_sales_order_from_quotation(
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

    existing = (
        db.query(models.SalesOrder)
        .filter(
            models.SalesOrder.quote_id
            == quotation.id
        )
        .first()
    )

    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Quotation already converted "
                f"to {existing.so_no}"
            ),
        )

    if quotation.status is not models.QuotationStatus.accepted:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only Accepted quotations "
                "can be converted to a Sales Order"
            ),
        )
    sales_order = models.SalesOrder(
        so_no=next_sales_order_no(
            db,
            "SO",
        ),
        order_date=quotation.quotation_date,
        delivery_date=quotation.valid_until,
        customer_id=quotation.customer_id,
        customer_name=quotation.customer_name,
        notes=quotation.notes,
        status=models.SalesOrderStatus.open,
        quote_id=quotation.id,
        quote_no=quotation.quotation_no,
        taxable_total=quotation.taxable_total,
        cgst=quotation.cgst,
        sgst=quotation.sgst,
        igst=quotation.igst,
        grand_total=quotation.grand_total,
        created_by=user.username,
    )

    for quote_line in quotation.lines:
        sales_order.lines.append(
            models.SalesOrderLine(
                product_id=quote_line.product_id,
                product_name=quote_line.product_name,
                hsn=quote_line.hsn,
                unit=quote_line.unit,
                quantity=quote_line.quantity,
                rate=quote_line.rate,
                discount_percent=quote_line.discount_percent,
                gst_rate=quote_line.gst_rate,
                taxable=quote_line.taxable,
                cgst=quote_line.cgst,
                sgst=quote_line.sgst,
                igst=quote_line.igst,
                total=quote_line.total,
                delivered_quantity=0,
            )
        )

    quotation.status = (
        models.QuotationStatus.converted
    )

    db.add(sales_order)

    log_audit(
        db,
        user.username,
        "CREATE",
        "sales_order",
        (
            f"{sales_order.so_no} from "
            f"{quotation.quotation_no}"
        ),
    )

    db.commit()
    db.refresh(sales_order)

    return sales_order
