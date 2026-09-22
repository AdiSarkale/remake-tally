"""Delivery note routes: SO deliveries and direct dispatch."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.models import ItemKind, MovementType
from app.services.inventory import apply_movement, log_audit

router = APIRouter(prefix="/deliveries", tags=["deliveries"])
guard = Depends(require_area("sales"))


def next_delivery_no(db: Session) -> str:
    values = db.query(models.DeliveryNote.delivery_no).filter(models.DeliveryNote.delivery_no.like("DN%")).all()
    nums = []
    for (no,) in values:
        tail = "".join(ch for ch in no[2:] if ch.isdigit())
        if tail:
            nums.append(int(tail))
    return f"DN{(max(nums) + 1 if nums else 1):04d}"


@router.get("", response_model=list[schemas.DeliveryOut])
def list_deliveries(db: Session = Depends(get_db), user: models.User = guard):
    return db.query(models.DeliveryNote).order_by(models.DeliveryNote.delivery_date.desc(), models.DeliveryNote.delivery_no.desc()).all()


@router.get("/next-number")
def next_number(db: Session = Depends(get_db), user: models.User = guard):
    return {"delivery_no": next_delivery_no(db)}


@router.get("/{delivery_id}", response_model=schemas.DeliveryOut)
def get_delivery(delivery_id: str, db: Session = Depends(get_db), user: models.User = guard):
    delivery = db.get(models.DeliveryNote, delivery_id)
    if delivery is None:
        raise HTTPException(404, "Delivery note not found")
    return delivery


@router.post("", response_model=schemas.DeliveryOut, status_code=201)
def create_delivery(
    payload: schemas.DeliveryIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    if not payload.lines:
        raise HTTPException(400, "At least one delivery line is required")
    if len({line.product_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(400, "The same product cannot appear twice in one delivery")

    sales_order = None
    if payload.sales_order_id:
        sales_order = db.get(models.SalesOrder, payload.sales_order_id)
        if sales_order is None:
            raise HTTPException(404, "Sales order not found")
        if sales_order.status in (
            models.SalesOrderStatus.delivered,
            models.SalesOrderStatus.invoiced,
            models.SalesOrderStatus.cancelled,
        ):
            raise HTTPException(400, f"Sales order {sales_order.so_no} cannot receive another delivery")

    if sales_order is None:
        if not payload.customer_id:
            raise HTTPException(400, "customer_id is required for direct dispatch")
        customer = db.get(models.Party, payload.customer_id)
        if customer is None or customer.kind != "customer":
            raise HTTPException(404, "Customer not found")
        customer_id = customer.id
        customer_name = customer.name
        so_no = ""
    else:
        customer_id = sales_order.customer_id
        customer_name = sales_order.customer_name
        so_no = sales_order.so_no

    delivery = models.DeliveryNote(
        delivery_no=next_delivery_no(db),
        delivery_date=payload.delivery_date,
        sales_order_id=sales_order.id if sales_order else None,
        so_no=so_no,
        customer_id=customer_id,
        customer_name=customer_name,
        vehicle_no=payload.vehicle_no,
        driver_name=payload.driver_name,
        lr_number=payload.lr_number,
        remarks=payload.remarks,
        created_by=user.username,
    )
    db.add(delivery)
    db.flush()

    for req in payload.lines:
        product = db.get(models.Product, req.product_id)
        if product is None:
            raise HTTPException(404, f"Product {req.product_id} not found")
        if req.quantity <= 0:
            raise HTTPException(400, "Delivery quantity must be greater than 0")
        if product.stock < req.quantity:
            raise HTTPException(400, f"Insufficient stock for {product.name} (available {product.stock})")

        if sales_order:
            so_line = next((line for line in sales_order.lines if line.product_id == product.id), None)
            if so_line is None:
                raise HTTPException(400, f"{product.name} is not on {sales_order.so_no}")
            remaining = round(so_line.quantity - so_line.delivered_quantity, 3)
            if req.quantity > remaining:
                raise HTTPException(400, f"Only {remaining} {product.unit} of {product.name} remains on {sales_order.so_no}")
            so_line.delivered_quantity = round(so_line.delivered_quantity + req.quantity, 3)

        delivery.lines.append(models.DeliveryLine(
            product_id=product.id,
            product_name=product.name,
            unit=product.unit,
            quantity=req.quantity,
        ))

        apply_movement(
            db,
            kind=ItemKind.product,
            item_id=product.id,
            movement_type=MovementType.OUT,
            quantity=req.quantity,
            reference=delivery.delivery_no,
            reason=f"Delivery — {customer_name}",
            entry_date=payload.delivery_date,
            user_id=user.id,
        )

    if sales_order:
        all_delivered = all(
            round(line.delivered_quantity, 3) >= round(line.quantity, 3)
            for line in sales_order.lines
        )
        any_delivered = any(line.delivered_quantity > 0 for line in sales_order.lines)
        sales_order.status = (
            models.SalesOrderStatus.delivered if all_delivered
            else models.SalesOrderStatus.partially_delivered if any_delivered
            else models.SalesOrderStatus.open
        )

    log_audit(db, user.username, "CREATE", "delivery", f"{delivery.delivery_no} · {customer_name}")
    db.commit()
    db.refresh(delivery)
    return delivery
