"""Dispatch and logistics routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.services.inventory import log_audit


router = APIRouter(
    prefix="/dispatches",
    tags=["dispatches"],
)

guard = Depends(require_area("sales"))


def next_dispatch_no(
    db: Session,
    prefix: str = "DSP",
) -> str:
    numbers = [
        int(tail)
        for (no,) in (
            db.query(models.Dispatch.dispatch_no)
            .filter(
                models.Dispatch.dispatch_no.like(
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
    response_model=list[schemas.DispatchOut],
)
def list_dispatches(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return (
        db.query(models.Dispatch)
        .order_by(
            models.Dispatch.dispatch_date.desc(),
            models.Dispatch.dispatch_no.desc(),
        )
        .all()
    )


@router.get("/next-number")
def peek_next_dispatch_number(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return {
        "dispatch_no": next_dispatch_no(db)
    }


@router.get(
    "/{dispatch_id}",
    response_model=schemas.DispatchOut,
)
def get_dispatch(
    dispatch_id: str,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    dispatch = db.get(
        models.Dispatch,
        dispatch_id,
    )

    if dispatch is None:
        raise HTTPException(
            status_code=404,
            detail="Dispatch not found",
        )

    return dispatch


@router.post(
    "",
    response_model=schemas.DispatchOut,
    status_code=201,
)
def create_dispatch(
    payload: schemas.DispatchIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    delivery = None

    if payload.delivery_id:
        delivery = db.get(
            models.DeliveryNote,
            payload.delivery_id,
        )

        if delivery is None:
            raise HTTPException(
                status_code=404,
                detail="Delivery note not found",
            )
        existing_dispatch = (
            db.query(models.Dispatch)
            .filter(
                models.Dispatch.delivery_id
                == delivery.id
            )
            .first()
        )

        if existing_dispatch is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Delivery note "
                    f"{delivery.delivery_no} "
                    f"already has dispatch "
                    f"{existing_dispatch.dispatch_no}"
                ),
            )

    if (
        payload.status
        is models.DispatchStatus.delivered
        and payload.delivered_on is None
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "delivered_on is required "
                "when dispatch is Delivered"
            ),
        )

    dispatch = models.Dispatch(
        dispatch_no=next_dispatch_no(db),
        dispatch_date=payload.dispatch_date,
        delivery_id=(
            delivery.id
            if delivery
            else None
        ),
        delivery_no=(
            delivery.delivery_no
            if delivery
            else ""
        ),
        customer_id=(
            delivery.customer_id
            if delivery
            else ""
        ),
        customer_name=(
            delivery.customer_name
            if delivery
            else ""
        ),
        transporter=payload.transporter,
        vehicle_no=payload.vehicle_no,
        driver_name=payload.driver_name,
        driver_phone=payload.driver_phone,
        lr_number=payload.lr_number,
        status=payload.status,
        delivered_on=payload.delivered_on,
        pod_ref=payload.pod_ref,
        created_by=user.username,
    )

    db.add(dispatch)

    log_audit(
        db,
        user.username,
        "CREATE",
        "dispatch",
        (
            f"{dispatch.dispatch_no} · "
            f"{dispatch.delivery_no} · "
            f"{dispatch.customer_name}"
        ),
    )

    db.commit()
    db.refresh(dispatch)

    return dispatch


@router.patch(
    "/{dispatch_id}/status",
    response_model=schemas.DispatchOut,
)
def update_dispatch_status(
    dispatch_id: str,
    payload: schemas.DispatchStatusIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    dispatch = db.get(
        models.Dispatch,
        dispatch_id,
    )

    if dispatch is None:
        raise HTTPException(
            status_code=404,
            detail="Dispatch not found",
        )

    if (
        payload.status
        is models.DispatchStatus.delivered
    ):
        if dispatch.delivered_on is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "delivered_on is required "
                    "when marking dispatch "
                    "as Delivered"
                ),
            )

    dispatch.status = payload.status

    log_audit(
        db,
        user.username,
        "UPDATE",
        "dispatch",
        (
            f"{dispatch.dispatch_no} -> "
            f"{dispatch.status.value}"
        ),
    )

    db.commit()
    db.refresh(dispatch)

    return dispatch
