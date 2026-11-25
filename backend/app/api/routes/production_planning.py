"""Production planning and advanced manufacturing APIs (no Smart PR generation)."""
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.modules.core.audit import log_audit
from app.services.production_planning import plan_materials, schedule_order, calculate_mrp, save_cost

router = APIRouter(prefix="/production-planning", tags=["production-planning"])
guard = Depends(require_area("production"))


def _order(db: Session, order_id: str) -> models.ProductionOrder:
    order = db.get(models.ProductionOrder, order_id)
    if not order:
        raise HTTPException(404, "Production order not found")
    if order.status in {"Completed", "Cancelled"}:
        raise HTTPException(409, "Completed or cancelled orders cannot be replanned")
    return order


@router.post("/orders/{order_id}/plan-materials", response_model=schemas.ProductionPlanningOut)
def plan_order_materials(order_id: str, db: Session = Depends(get_db), user: models.User = guard):
    order = _order(db, order_id)
    try:
        materials = plan_materials(db, order)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    log_audit(db, user.username, "PLAN", "production_order", order.order_no)
    db.commit()
    rows = db.query(models.ProductionOrderOperation).filter_by(production_order_id=order.id).order_by(models.ProductionOrderOperation.sequence).all()
    return {"production_order_id": order.id, "planning_status": order.planning_status, "materials": materials, "operations": rows}


@router.post("/orders/{order_id}/schedule", response_model=schemas.ProductionPlanningOut)
def schedule_production_order(order_id: str, payload: schemas.ScheduleIn, db: Session = Depends(get_db), user: models.User = guard):
    order = _order(db, order_id)
    if order.planning_status not in {"materials_ready", "scheduled"}:
        raise HTTPException(409, "Resolve material shortages before scheduling")
    try:
        rows = schedule_order(db, order, payload.start_at, payload.respect_employee_availability, payload.machine_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    log_audit(db, user.username, "SCHEDULE", "production_order", order.order_no)
    db.commit()
    reservations = db.query(models.MaterialReservation).filter_by(production_order_id=order.id).all()
    material_rows = []
    for r in reservations:
        material = db.get(models.RawMaterial, r.material_id)
        material_rows.append({
            "material_id": r.material_id, "material_name": material.name if material else "",
            "required_quantity": r.required_quantity, "available_quantity": r.reserved_quantity,
            "reserved_quantity": r.reserved_quantity,
            "shortage_quantity": round(max(0, r.required_quantity-r.reserved_quantity), 3),
        })
    return {"production_order_id": order.id, "planning_status": order.planning_status, "materials": material_rows, "operations": rows}


@router.get("/mrp", response_model=schemas.MRPOut)
def mrp_calculation(db: Session = Depends(get_db), user: models.User = guard):
    return {"calculated_at": datetime.utcnow(), "requirements": calculate_mrp(db)}


@router.get("/machines", response_model=list[schemas.MachineOut])
def list_machines(db: Session = Depends(get_db), user: models.User = guard):
    return db.query(models.MachineResource).order_by(models.MachineResource.code).all()


@router.post("/machines", response_model=schemas.MachineOut, status_code=201)
def create_machine(payload: schemas.MachineIn, db: Session = Depends(get_db), user: models.User = guard):
    wc = db.get(models.Workcenter, payload.workcenter_id)
    if not wc:
        raise HTTPException(400, "Work centre not found")
    if db.query(models.MachineResource).filter_by(code=payload.code).first():
        raise HTTPException(409, "Machine code already exists")
    row = models.MachineResource(**payload.model_dump(), status="available")
    db.add(row)
    log_audit(db, user.username, "CREATE", "production_machine", payload.code)
    db.commit()
    db.refresh(row)
    return row


@router.post("/downtime", response_model=schemas.DowntimeOut, status_code=201)
def record_downtime(payload: schemas.DowntimeIn, db: Session = Depends(get_db), user: models.User = guard):
    if payload.end_at and payload.end_at <= payload.start_at:
        raise HTTPException(400, "Downtime end must be after start")
    machine = db.get(models.MachineResource, payload.machine_id)
    if not machine:
        raise HTTPException(404, "Machine not found")
    row = models.MachineDowntime(machine_id=machine.id, workcenter_id=machine.workcenter_id,
        start_at=payload.start_at, end_at=payload.end_at, reason=payload.reason, notes=payload.notes)
    if payload.end_at is None:
        machine.status = "breakdown"
    db.add(row)
    log_audit(db, user.username, "CREATE", "machine_downtime", machine.code)
    db.commit()
    db.refresh(row)
    return row


@router.get("/downtime", response_model=list[schemas.DowntimeOut])
def list_downtime(machine_id: str | None = None, db: Session = Depends(get_db), user: models.User = guard):
    q = db.query(models.MachineDowntime)
    if machine_id:
        q = q.filter_by(machine_id=machine_id)
    return q.order_by(models.MachineDowntime.start_at.desc()).all()


@router.post("/wip", response_model=schemas.WIPOut, status_code=201)
def create_wip(payload: schemas.WIPIn, db: Session = Depends(get_db), user: models.User = guard):
    order = db.get(models.ProductionOrder, payload.production_order_id)
    operation = db.get(models.RoutingOperation, payload.operation_id)
    if not order or not operation or operation.routing_id != order.routing_id:
        raise HTTPException(400, "WIP operation must belong to the production order routing")
    row = models.ProductionWIP(**payload.model_dump())
    db.add(row)
    log_audit(db, user.username, "CREATE", "production_wip", order.order_no)
    db.commit()
    db.refresh(row)
    return row


@router.get("/wip", response_model=list[schemas.WIPOut])
def list_wip(production_order_id: str | None = None, db: Session = Depends(get_db), user: models.User = guard):
    q = db.query(models.ProductionWIP)
    if production_order_id:
        q = q.filter_by(production_order_id=production_order_id)
    return q.order_by(models.ProductionWIP.created_at).all()


@router.patch("/wip/{wip_id}/close", response_model=schemas.WIPOut)
def close_wip(wip_id: str, db: Session = Depends(get_db), user: models.User = guard):
    row = db.get(models.ProductionWIP, wip_id)
    if not row:
        raise HTTPException(404, "WIP record not found")
    if row.status != "open":
        raise HTTPException(409, "WIP record is already closed")
    row.status = "closed"
    log_audit(db, user.username, "CLOSE", "production_wip", row.id)
    db.commit()
    db.refresh(row)
    return row


@router.put("/orders/{order_id}/cost", response_model=schemas.CostOut)
def update_production_cost(order_id: str, payload: schemas.CostIn, db: Session = Depends(get_db), user: models.User = guard):
    order = db.get(models.ProductionOrder, order_id)
    if not order:
        raise HTTPException(404, "Production order not found")
    row = save_cost(db, order, payload.model_dump())
    log_audit(db, user.username, "UPDATE", "production_cost", order.order_no)
    db.commit()
    db.refresh(row)
    return row


@router.get("/orders/{order_id}/cost", response_model=schemas.CostOut)
def get_production_cost(order_id: str, db: Session = Depends(get_db), user: models.User = guard):
    row = db.query(models.ProductionCost).filter_by(production_order_id=order_id).first()
    if not row:
        raise HTTPException(404, "Production cost not recorded")
    return row


@router.get("/oee")
def production_oee(workcenter_id: str, start_date: date, end_date: date, db: Session = Depends(get_db), user: models.User = guard):
    if end_date < start_date:
        raise HTTPException(400, "End date must be on or after start date")
    wc = db.get(models.Workcenter, workcenter_id)
    if not wc:
        raise HTTPException(404, "Work centre not found")
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
    planned_minutes = 0.0
    scheduled = db.query(models.ProductionOrderOperation).filter(
        models.ProductionOrderOperation.workcenter_id == workcenter_id,
        models.ProductionOrderOperation.scheduled_start < end_dt,
        models.ProductionOrderOperation.scheduled_end > start_dt,
    ).all()
    for op in scheduled:
        s=max(start_dt,op.scheduled_start); e=min(end_dt,op.scheduled_end)
        planned_minutes += max(0,(e-s).total_seconds()/60)
    downtime_rows=db.query(models.MachineDowntime).filter(
        models.MachineDowntime.workcenter_id==workcenter_id,
        models.MachineDowntime.start_at<end_dt,
    ).all()
    downtime_minutes=0.0
    for d in downtime_rows:
        d_end=d.end_at or end_dt
        s=max(start_dt,d.start_at); e=min(end_dt,d_end)
        downtime_minutes+=max(0,(e-s).total_seconds()/60)
    production=db.query(models.ProductionEntry).filter(
        models.ProductionEntry.workcenter_id==workcenter_id,
        models.ProductionEntry.entry_date>=start_date,
        models.ProductionEntry.entry_date<=end_date,
    ).all()
    produced=sum(float(p.quantity or 0) for p in production)
    accepted=sum(float(p.accepted_qty or 0) for p in production)
    capacity=float(wc.capacity_per_hour or 0)*max(0,planned_minutes-downtime_minutes)/60
    availability=max(0,1-downtime_minutes/planned_minutes) if planned_minutes else 0
    performance=min(1.0,produced/capacity) if capacity>0 else 0
    quality=accepted/produced if produced>0 else 0
    return {
        "workcenter_id":wc.id,"workcenter_code":wc.code,"period_start":start_date,"period_end":end_date,
        "planned_minutes":round(planned_minutes,2),"downtime_minutes":round(downtime_minutes,2),
        "produced_quantity":round(produced,3),"accepted_quantity":round(accepted,3),
        "availability":round(availability,4),"performance":round(performance,4),
        "quality":round(quality,4),"oee":round(availability*performance*quality,4),
    }
