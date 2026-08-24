"""Dispatch and logistics routes with one-dispatch-per-delivery enforcement and editing."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.services.inventory import log_audit

router = APIRouter(prefix="/dispatches", tags=["dispatches"])
guard = Depends(require_area("sales"))


def next_dispatch_no(db: Session, prefix: str = "DSP") -> str:
    values = db.query(models.Dispatch.dispatch_no).filter(models.Dispatch.dispatch_no.like(f"{prefix}%")).all()
    nums = []
    for (no,) in values:
        tail = "".join(ch for ch in no[len(prefix):] if ch.isdigit())
        if tail:
            nums.append(int(tail))
    return f"{prefix}{(max(nums) + 1 if nums else 1):04d}"


@router.get("", response_model=list[schemas.DispatchOut])
def list_dispatches(db: Session = Depends(get_db), user: models.User = guard):
    return db.query(models.Dispatch).order_by(models.Dispatch.dispatch_date.desc(), models.Dispatch.dispatch_no.desc()).all()


@router.get("/next-number")
def next_number(db: Session = Depends(get_db), user: models.User = guard):
    return {"dispatch_no": next_dispatch_no(db)}


@router.get("/{dispatch_id}", response_model=schemas.DispatchOut)
def get_dispatch(dispatch_id: str, db: Session = Depends(get_db), user: models.User = guard):
    dispatch = db.get(models.Dispatch, dispatch_id)
    if dispatch is None:
        raise HTTPException(404, "Dispatch not found")
    return dispatch


@router.post("", response_model=schemas.DispatchOut, status_code=201)
def create_dispatch(payload: schemas.DispatchIn, db: Session = Depends(get_db), user: models.User = guard):
    delivery = db.get(models.DeliveryNote, payload.delivery_id)
    if delivery is None:
        raise HTTPException(404, "Delivery note not found")

    existing = db.query(models.Dispatch).filter(models.Dispatch.delivery_id == delivery.id).first()
    if existing:
        raise HTTPException(409, f"Delivery note {delivery.delivery_no} already has dispatch {existing.dispatch_no}")

    if payload.status is models.DispatchStatus.delivered and payload.delivered_on is None:
        raise HTTPException(400, "delivered_on is required when dispatch is Delivered")

    dispatch = models.Dispatch(
        dispatch_no=next_dispatch_no(db),
        dispatch_date=payload.dispatch_date,
        delivery_id=delivery.id,
        delivery_no=delivery.delivery_no,
        customer_id=delivery.customer_id,
        customer_name=delivery.customer_name,
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
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Delivery note {delivery.delivery_no} already has a dispatch")
    log_audit(db, user.username, "CREATE", "dispatch", f"{dispatch.dispatch_no} · {delivery.delivery_no} · {delivery.customer_name}")
    db.commit()
    db.refresh(dispatch)
    return dispatch


@router.patch("/{dispatch_id}", response_model=schemas.DispatchOut)
def update_dispatch(
    dispatch_id: str,
    payload: schemas.DispatchUpdateIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    dispatch = db.get(models.Dispatch, dispatch_id)
    if dispatch is None:
        raise HTTPException(404, "Dispatch not found")

    if payload.status is models.DispatchStatus.delivered and payload.delivered_on is None:
        raise HTTPException(400, "delivered_on is required when dispatch is Delivered")

    dispatch.transporter = payload.transporter
    dispatch.vehicle_no = payload.vehicle_no
    dispatch.driver_name = payload.driver_name
    dispatch.driver_phone = payload.driver_phone
    dispatch.lr_number = payload.lr_number
    dispatch.status = payload.status
    dispatch.delivered_on = payload.delivered_on
    dispatch.pod_ref = payload.pod_ref

    log_audit(db, user.username, "UPDATE", "dispatch", f"{dispatch.dispatch_no} -> {dispatch.status.value}")
    db.commit()
    db.refresh(dispatch)
    return dispatch


@router.patch("/{dispatch_id}/status", response_model=schemas.DispatchOut)
def update_dispatch_status(
    dispatch_id: str,
    payload: schemas.DispatchStatusIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    dispatch = db.get(models.Dispatch, dispatch_id)
    if dispatch is None:
        raise HTTPException(404, "Dispatch not found")
    if payload.status is models.DispatchStatus.delivered and dispatch.delivered_on is None:
        raise HTTPException(400, "delivered_on is required when dispatch is Delivered")
    dispatch.status = payload.status
    log_audit(db, user.username, "UPDATE", "dispatch", f"{dispatch.dispatch_no} -> {dispatch.status.value}")
    db.commit()
    db.refresh(dispatch)
    return dispatch
