"""Delivery note routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.models import ItemKind, MovementType
from app.services.inventory import apply_movement, log_audit


router = APIRouter(
    prefix="/deliveries",
    tags=["deliveries"],
)

guard = Depends(require_area("sales"))


def next_delivery_no(
    db: Session,
    prefix: str = "DN",
) -> str:
    numbers = [
        int(tail)
        for (no,) in (
            db.query(
                models.DeliveryNote.delivery_no
            )
            .filter(
                models.DeliveryNote.delivery_no.like(
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

    return (
        f"{prefix}"
        f"{(max(numbers) + 1 if numbers else 1):04d}"
    )


@router.get(
    "",
    response_model=list[schemas.DeliveryOut],
)
def list_deliveries(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return (
        db.query(models.DeliveryNote)
        .order_by(
            models.DeliveryNote.delivery_date.desc(),
            models.DeliveryNote.delivery_no.desc(),
        )
        .all()
    )


@router.get("/next-number")
def peek_next_delivery_number(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return {
        "delivery_no": next_delivery_no(
            db
        )
    }


@router.get(
    "/{delivery_id}",
    response_model=schemas.DeliveryOut,
)
def get_delivery(
    delivery_id: str,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    delivery = db.get(
        models.DeliveryNote,
        delivery_id,
    )

    if delivery is None:
        raise HTTPException(
            status_code=404,
            detail="Delivery note not found",
        )

    return delivery


@router.post(
    "",
    response_model=schemas.DeliveryOut,
    status_code=201,
)
def create_delivery(
    payload: schemas.DeliveryCreate,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    # -------------------------------------------------
    # Validate Sales Order
    # -------------------------------------------------

    sales_order = db.get(
        models.SalesOrder,
        payload.sales_order_id,
    )

    if sales_order is None:
        raise HTTPException(
            status_code=404,
            detail="Sales order not found",
        )

    if sales_order.status in (
        models.SalesOrderStatus.delivered,
        models.SalesOrderStatus.invoiced,
        models.SalesOrderStatus.cancelled,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Sales order {sales_order.so_no} "
                f"cannot receive another delivery "
                f"while status is "
                f"{sales_order.status.value}"
            ),
        )

    if not payload.lines:
        raise HTTPException(
            status_code=400,
            detail="At least one delivery line is required",
        )

    # -------------------------------------------------
    # Prevent duplicate product lines
    # -------------------------------------------------

    product_ids = [
        line.product_id
        for line in payload.lines
    ]

    if len(product_ids) != len(set(product_ids)):
        raise HTTPException(
            status_code=400,
            detail=(
                "The same product cannot appear "
                "twice in one delivery"
            ),
        )

    # -------------------------------------------------
    # Validate every line
    # -------------------------------------------------

    validated_lines = []

    for payload_line in payload.lines:

        so_line = next(
            (
                line
                for line in sales_order.lines
                if line.product_id
                == payload_line.product_id
            ),
            None,
        )

        if so_line is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Product "
                    f"{payload_line.product_id} "
                    f"is not part of "
                    f"{sales_order.so_no}"
                ),
            )

        if payload_line.quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Delivery quantity must "
                    "be greater than 0"
                ),
            )

        remaining = round(
            so_line.quantity
            - so_line.delivered_quantity,
            3,
        )

        if payload_line.quantity > remaining:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{so_line.product_name}: "
                    f"only {remaining} "
                    f"remaining to deliver"
                ),
            )

        product = db.get(
            models.Product,
            so_line.product_id,
        )

        if product is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Product "
                    f"{so_line.product_id} "
                    "not found"
                ),
            )

        if product.stock < payload_line.quantity:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient stock for "
                    f"{product.name}. "
                    f"Available {product.stock}"
                ),
            )

        validated_lines.append(
            (
                so_line,
                product,
                payload_line.quantity,
            )
        )

    # -------------------------------------------------
    # Create Delivery Note
    # -------------------------------------------------

    delivery = models.DeliveryNote(
        delivery_no=next_delivery_no(db),
        delivery_date=payload.delivery_date,
        sales_order_id=sales_order.id,
        so_no=sales_order.so_no,
        customer_id=sales_order.customer_id,
        customer_name=sales_order.customer_name,
        vehicle_no=payload.vehicle_no,
        driver_name=payload.driver_name,
        lr_number=payload.lr_number,
        remarks=payload.remarks,
        created_by=user.username,
    )

    db.add(delivery)
    db.flush()

    # -------------------------------------------------
    # Process delivery lines
    # -------------------------------------------------

    for so_line, product, quantity in validated_lines:

        delivery.lines.append(
            models.DeliveryLine(
                product_id=product.id,
                product_name=product.name,
                unit=product.unit,
                quantity=quantity,
            )
        )

        so_line.delivered_quantity = round(
            so_line.delivered_quantity
            + quantity,
            3,
        )

        # Finished goods leave stock.
        apply_movement(
            db,
            kind=ItemKind.product,
            item_id=product.id,
            movement_type=MovementType.OUT,
            quantity=quantity,
            reference=delivery.delivery_no,
            reason=(
                f"Delivery {delivery.delivery_no} "
                f"— {sales_order.so_no}"
            ),
            entry_date=payload.delivery_date,
            user_id=user.id,
        )

    # -------------------------------------------------
    # Update Sales Order status
    # -------------------------------------------------

    all_delivered = all(
        round(line.delivered_quantity, 3)
        >= round(line.quantity, 3)
        for line in sales_order.lines
    )

    any_delivered = any(
        line.delivered_quantity > 0
        for line in sales_order.lines
    )

    if all_delivered:
        sales_order.status = (
            models.SalesOrderStatus.delivered
        )
    elif any_delivered:
        sales_order.status = (
            models.SalesOrderStatus.partially_delivered
        )
    else:
        sales_order.status = (
            models.SalesOrderStatus.open
        )

    # -------------------------------------------------
    # Audit
    # -------------------------------------------------

    log_audit(
        db,
        user.username,
        "CREATE",
        "delivery",
        (
            f"{delivery.delivery_no} · "
            f"{sales_order.so_no} · "
            f"{sales_order.customer_name}"
        ),
    )

    db.commit()
    db.refresh(delivery)

    return delivery
