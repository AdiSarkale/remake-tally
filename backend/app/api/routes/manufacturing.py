"""Manufacturing master data, routing, workcenter and production-order execution APIs."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.services.inventory import log_audit, next_batch_no

router = APIRouter(prefix="/manufacturing", tags=["manufacturing"])
guard = Depends(require_area("production"))


def _auto_employee(db: Session, operation: models.RoutingOperation) -> models.Employee | None:
    q = db.query(models.Employee).join(
        models.EmployeeSkill,
        models.EmployeeSkill.employee_id == models.Employee.id,
    ).filter(
        models.Employee.active.is_(True),
        models.EmployeeSkill.active.is_(True),
    )
    if operation.required_skill.strip():
        q = q.filter(models.EmployeeSkill.skill == operation.required_skill.strip())
    return q.order_by(models.EmployeeSkill.level.desc(), models.Employee.emp_code.asc()).first()


@router.get("/workcenters", response_model=list[schemas.WorkcenterOut])
def list_workcenters(db: Session = Depends(get_db), user: models.User = guard):
    rows = db.query(models.Workcenter).order_by(models.Workcenter.code).all()
    return [
        {**{k: getattr(w, k) for k in ("id","code","name","department","capacity_per_hour","status","active","location")},
         "materials": db.query(models.WorkcenterMaterial).filter_by(workcenter_id=w.id).all()}
        for w in rows
    ]


@router.post("/workcenters", response_model=schemas.WorkcenterOut, status_code=201)
def create_workcenter(payload: schemas.WorkcenterIn, db: Session = Depends(get_db), user: models.User = guard):
    if db.query(models.Workcenter).filter(models.Workcenter.code == payload.code).first():
        raise HTTPException(400, "Workcenter code already exists")
    w = models.Workcenter(
        code=payload.code, name=payload.name, department=payload.department,
        capacity_per_hour=payload.capacity_per_hour, status=payload.status,
        active=payload.active, location=payload.location,
    )
    db.add(w)
    db.flush()
    for item in payload.materials:
        db.add(models.WorkcenterMaterial(workcenter_id=w.id, **item.model_dump()))
    log_audit(db, user.username, "CREATE", "workcenter", w.code)
    db.commit()
    db.refresh(w)
    return {**{k: getattr(w, k) for k in ("id","code","name","department","capacity_per_hour","status","active","location")},
            "materials": db.query(models.WorkcenterMaterial).filter_by(workcenter_id=w.id).all()}


@router.put("/workcenters/{workcenter_id}", response_model=schemas.WorkcenterOut)
def update_workcenter(workcenter_id: str, payload: schemas.WorkcenterIn, db: Session = Depends(get_db), user: models.User = guard):
    w = db.get(models.Workcenter, workcenter_id)
    if not w:
        raise HTTPException(404, "Workcenter not found")
    for k in ("code","name","department","capacity_per_hour","status","active","location"):
        setattr(w, k, getattr(payload, k))
    db.query(models.WorkcenterMaterial).filter_by(workcenter_id=w.id).delete()
    for item in payload.materials:
        db.add(models.WorkcenterMaterial(workcenter_id=w.id, **item.model_dump()))
    log_audit(db, user.username, "UPDATE", "workcenter", w.code)
    db.commit()
    db.refresh(w)
    return {**{k: getattr(w, k) for k in ("id","code","name","department","capacity_per_hour","status","active","location")},
            "materials": db.query(models.WorkcenterMaterial).filter_by(workcenter_id=w.id).all()}


@router.get("/routings", response_model=list[schemas.RoutingOut])
def list_routings(product_id: str | None = None, db: Session = Depends(get_db), user: models.User = guard):
    q = db.query(models.Routing)
    if product_id:
        q = q.filter(models.Routing.product_id == product_id)
    rows = q.order_by(models.Routing.product_id, models.Routing.version.desc()).all()
    return [{**{k:getattr(r,k) for k in ("id","product_id","version","name","active")},
             "operations": db.query(models.RoutingOperation).filter_by(routing_id=r.id).order_by(models.RoutingOperation.sequence).all()} for r in rows]


@router.post("/routings", response_model=schemas.RoutingOut, status_code=201)
def create_routing(payload: schemas.RoutingIn, db: Session = Depends(get_db), user: models.User = guard):
    if not db.get(models.Product, payload.product_id):
        raise HTTPException(400, "Product not found")
    if len({x.sequence for x in payload.operations}) != len(payload.operations):
        raise HTTPException(400, "Routing operation sequence must be unique")
    for op in payload.operations:
        if not db.get(models.Workcenter, op.workcenter_id):
            raise HTTPException(400, f"Workcenter {op.workcenter_id} not found")
    if payload.active:
        db.query(models.Routing).filter(
            models.Routing.product_id == payload.product_id,
            models.Routing.active.is_(True),
        ).update({"active": False}, synchronize_session=False)
    r = models.Routing(product_id=payload.product_id, version=payload.version, name=payload.name, active=payload.active)
    db.add(r)
    db.flush()
    for op in payload.operations:
        db.add(models.RoutingOperation(routing_id=r.id, **op.model_dump()))
    log_audit(db, user.username, "CREATE", "routing", f"{payload.product_id} v{payload.version}")
    db.commit()
    db.refresh(r)
    return {**{k:getattr(r,k) for k in ("id","product_id","version","name","active")},
            "operations": db.query(models.RoutingOperation).filter_by(routing_id=r.id).order_by(models.RoutingOperation.sequence).all()}


@router.get("/employees", response_model=list[schemas.EmployeeOut])
def list_employees(db: Session = Depends(get_db), user: models.User = guard):
    return db.query(models.Employee).order_by(models.Employee.emp_code).all()


@router.post("/employees", response_model=schemas.EmployeeOut, status_code=201)
def create_employee(payload: schemas.EmployeeIn, db: Session = Depends(get_db), user: models.User = guard):
    if db.query(models.Employee).filter(models.Employee.emp_code == payload.emp_code).first():
        raise HTTPException(400, "Employee code already exists")
    row = models.Employee(**payload.model_dump())
    db.add(row)
    log_audit(db, user.username, "CREATE", "employee", row.emp_code)
    db.commit()
    db.refresh(row)
    return row


@router.get("/employees/{employee_id}/skills", response_model=list[schemas.EmployeeSkillOut])
def list_employee_skills(employee_id: str, db: Session = Depends(get_db), user: models.User = guard):
    if not db.get(models.Employee, employee_id):
        raise HTTPException(404, "Employee not found")
    return db.query(models.EmployeeSkill).filter_by(employee_id=employee_id).order_by(models.EmployeeSkill.skill).all()


@router.post("/employees/{employee_id}/skills", response_model=schemas.EmployeeSkillOut, status_code=201)
def add_employee_skill(employee_id: str, payload: schemas.EmployeeSkillIn, db: Session = Depends(get_db), user: models.User = guard):
    if not db.get(models.Employee, employee_id):
        raise HTTPException(404, "Employee not found")
    if db.query(models.EmployeeSkill).filter_by(employee_id=employee_id, skill=payload.skill).first():
        raise HTTPException(400, "Employee already has this skill")
    row = models.EmployeeSkill(employee_id=employee_id, **payload.model_dump())
    db.add(row)
    log_audit(db, user.username, "CREATE", "employee_skill", f"{employee_id}: {payload.skill}")
    db.commit()
    db.refresh(row)
    return row


@router.get("/production-orders", response_model=list[schemas.ProductionOrderOut])
def list_production_orders(db: Session = Depends(get_db), user: models.User = guard):
    rows = db.query(models.ProductionOrder).order_by(models.ProductionOrder.order_date.desc()).all()
    return [
        {**{k:getattr(o,k) for k in ("id","order_no","order_date","product_id","quantity","due_date","routing_id","status","remarks")},
         "operations": db.query(models.ProductionOrderOperation).filter_by(production_order_id=o.id).order_by(models.ProductionOrderOperation.sequence).all()}
        for o in rows
    ]


@router.get("/production-orders/{order_id}/material-plan", response_model=schemas.ProductionOrderMaterialPlanOut)
def production_order_material_plan(
    order_id: str,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    """Return a point-in-time BOM material requirement and shortage snapshot.

    This endpoint does not reserve stock. Inventory can change after the response.
    """
    order = db.get(models.ProductionOrder, order_id)
    if order is None:
        raise HTTPException(404, "Production order not found")

    bom = (
        db.query(models.BillOfMaterials)
        .filter(
            models.BillOfMaterials.product_id == order.product_id,
            models.BillOfMaterials.active.is_(True),
        )
        .order_by(models.BillOfMaterials.version.desc())
        .first()
    )
    if bom is None or not bom.lines:
        raise HTTPException(400, "No active BOM with material lines found for this production order")

    materials = []
    for line in bom.lines:
        material = db.get(models.RawMaterial, line.material_id)
        if material is None:
            raise HTTPException(409, f"BOM material {line.material_id} no longer exists")

        consumed_value = (
            db.query(func.coalesce(func.sum(models.ProductionConsumption.quantity), 0.0))
            .join(
                models.ProductionEntry,
                models.ProductionEntry.id == models.ProductionConsumption.production_id,
            )
            .filter(
                models.ProductionEntry.production_order_id == order.id,
                models.ProductionConsumption.material_id == material.id,
            )
            .scalar()
        )
        required_quantity = round(float(line.quantity) * float(order.quantity), 3)
        consumed_quantity = round(float(consumed_value or 0), 3)
        remaining_quantity = round(max(required_quantity - consumed_quantity, 0.0), 3)
        available_quantity = round(float(material.stock or 0), 3)
        shortage_quantity = round(max(remaining_quantity - available_quantity, 0.0), 3)

        materials.append({
            "material_id": material.id,
            "material_code": material.code,
            "material_name": material.name,
            "unit": material.unit,
            "required_quantity": required_quantity,
            "consumed_quantity": consumed_quantity,
            "remaining_quantity": remaining_quantity,
            "available_quantity": available_quantity,
            "shortage_quantity": shortage_quantity,
            "status": "Available" if shortage_quantity == 0 else "Shortage",
        })

    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "product_id": order.product_id,
        "order_quantity": order.quantity,
        "materials_available": all(row["shortage_quantity"] == 0 for row in materials),
        "materials": materials,
    }


@router.post("/production-orders/{order_id}/reserve-materials", response_model=schemas.ProductionOrderReservationOut)
def reserve_production_order_materials(order_id: str, db: Session = Depends(get_db), user: models.User = guard):
    """Atomically reserve remaining active-BOM requirements for a planned order."""
    order = db.query(models.ProductionOrder).filter_by(id=order_id).with_for_update().first()
    if order is None:
        raise HTTPException(404, "Production order not found")
    if order.status not in ("Planned", "In Progress"):
        raise HTTPException(409, "Materials can only be reserved for planned or in-progress orders")
    bom = db.query(models.BillOfMaterials).filter(
        models.BillOfMaterials.product_id == order.product_id,
        models.BillOfMaterials.active.is_(True),
    ).order_by(models.BillOfMaterials.version.desc()).first()
    if bom is None or not bom.lines:
        raise HTTPException(400, "No active BOM with material lines found for this production order")

    plans = []
    for line in bom.lines:
        material = db.query(models.RawMaterial).filter_by(id=line.material_id).with_for_update().first()
        if material is None:
            raise HTTPException(409, f"BOM material {line.material_id} no longer exists")
        consumed = float(db.query(func.coalesce(func.sum(models.ProductionConsumption.quantity), 0.0))
            .join(models.ProductionEntry, models.ProductionEntry.id == models.ProductionConsumption.production_id)
            .filter(models.ProductionEntry.production_order_id == order.id,
                    models.ProductionConsumption.material_id == material.id).scalar() or 0.0)
        current = db.query(models.StockReservation).filter_by(
            production_order_id=order.id, material_id=material.id
        ).with_for_update().first()
        own_reserved = current.remaining_quantity if current and current.status == "Reserved" else 0.0
        other_reserved = float(db.query(func.coalesce(func.sum(models.StockReservation.quantity - models.StockReservation.consumed_quantity), 0.0))
            .filter(models.StockReservation.material_id == material.id,
                    models.StockReservation.status == "Reserved",
                    models.StockReservation.production_order_id != order.id).scalar() or 0.0)
        required_remaining = max(round(float(line.quantity) * float(order.quantity) - consumed, 3), 0.0)
        to_reserve = max(round(required_remaining - own_reserved, 3), 0.0)
        available_unreserved = max(round(float(material.stock) - other_reserved - own_reserved, 3), 0.0)
        if to_reserve > available_unreserved:
            raise HTTPException(409, f"Insufficient unreserved stock for {material.name} (required {to_reserve}, available {available_unreserved})")
        plans.append((material.id, current, consumed, own_reserved, to_reserve))

    # No writes occur until every BOM line passes the stock preflight.
    for material_id, current, consumed, own_reserved, to_reserve in plans:
        if current is None:
            current = models.StockReservation(
                production_order_id=order.id, material_id=material_id,
                quantity=round(consumed + to_reserve, 3), consumed_quantity=round(consumed, 3), status="Reserved",
            )
            db.add(current)
        else:
            current.quantity = round(consumed + own_reserved + to_reserve, 3)
            current.consumed_quantity = round(consumed, 3)
            current.status = "Reserved" if current.quantity > current.consumed_quantity else "Consumed"
            current.released_at = None
    log_audit(db, user.username, "RESERVE", "production_order", order.order_no)
    db.commit()
    rows = db.query(models.StockReservation).filter_by(production_order_id=order.id).order_by(models.StockReservation.material_id).all()
    return {"order_id": order.id, "order_no": order.order_no, "reservations": rows}


@router.post("/production-orders/{order_id}/release-materials", response_model=schemas.ProductionOrderReservationOut)
def release_production_order_materials(order_id: str, db: Session = Depends(get_db), user: models.User = guard):
    """Release unused reservations while preserving consumed quantities for audit."""
    order = db.query(models.ProductionOrder).filter_by(id=order_id).with_for_update().first()
    if order is None:
        raise HTTPException(404, "Production order not found")
    rows = db.query(models.StockReservation).filter_by(
        production_order_id=order.id, status="Reserved"
    ).with_for_update().all()
    from datetime import datetime, timezone
    for row in rows:
        row.status = "Released"
        row.released_at = datetime.now(timezone.utc)
    log_audit(db, user.username, "RELEASE", "production_order", order.order_no)
    db.commit()
    rows = db.query(models.StockReservation).filter_by(production_order_id=order.id).order_by(models.StockReservation.material_id).all()
    return {"order_id": order.id, "order_no": order.order_no, "reservations": rows}


@router.post("/production-orders", response_model=schemas.ProductionOrderOut, status_code=201)
def create_production_order(payload: schemas.ProductionOrderIn, db: Session = Depends(get_db), user: models.User = guard):
    product = db.get(models.Product, payload.product_id)
    if not product:
        raise HTTPException(400, "Product not found")
    routing = db.get(models.Routing, payload.routing_id) if payload.routing_id else db.query(models.Routing).filter_by(product_id=payload.product_id, active=True).order_by(models.Routing.version.desc()).first()
    if not routing:
        raise HTTPException(400, "No active routing found for this product")
    if routing.product_id != payload.product_id:
        raise HTTPException(400, "Routing does not belong to product")
    order = models.ProductionOrder(
        order_no=next_batch_no(db).replace("BATCH-", "PO-"),
        order_date=payload.order_date, product_id=payload.product_id, quantity=payload.quantity,
        due_date=payload.due_date, routing_id=routing.id, status="Planned", remarks=payload.remarks,
    )
    db.add(order)
    db.flush()
    for op in db.query(models.RoutingOperation).filter_by(routing_id=routing.id, active=True).order_by(models.RoutingOperation.sequence):
        employee = _auto_employee(db, op)
        db.add(models.ProductionOrderOperation(
            production_order_id=order.id, operation_id=op.id, sequence=op.sequence,
            workcenter_id=op.workcenter_id, assigned_employee_id=employee.id if employee else None,
            planned_qty=payload.quantity, status="Assigned" if employee else "Pending",
        ))
    log_audit(db, user.username, "CREATE", "production_order", order.order_no)
    db.commit()
    db.refresh(order)
    return {**{k:getattr(order,k) for k in ("id","order_no","order_date","product_id","quantity","due_date","routing_id","status","remarks")},
            "operations": db.query(models.ProductionOrderOperation).filter_by(production_order_id=order.id).order_by(models.ProductionOrderOperation.sequence).all()}


@router.post("/production-orders/{order_id}/transition", response_model=schemas.ProductionOrderOut)
def transition_production_order(order_id: str, payload: schemas.ProductionOrderTransitionIn, db: Session = Depends(get_db), user: models.User = guard):
    """Apply an explicit, validated production-order lifecycle transition."""
    order = db.query(models.ProductionOrder).filter_by(id=order_id).with_for_update().first()
    if order is None:
        raise HTTPException(404, "Production order not found")

    action = payload.action
    allowed = {
        "Planned": {"release", "cancel"},
        "Released": {"start", "cancel"},
        "In Progress": {"complete", "cancel"},
        "Completed": set(),
        "Cancelled": set(),
    }
    if action not in allowed.get(order.status, set()):
        raise HTTPException(409, f"Cannot {action} a production order in {order.status} status")

    if action in ("release", "start"):
        bom = db.query(models.BillOfMaterials).filter(
            models.BillOfMaterials.product_id == order.product_id,
            models.BillOfMaterials.active.is_(True),
        ).order_by(models.BillOfMaterials.version.desc()).first()
        if bom is None or not bom.lines:
            raise HTTPException(409, "An active BOM with material lines is required")
        for line in bom.lines:
            reservation = db.query(models.StockReservation).filter_by(
                production_order_id=order.id, material_id=line.material_id, status="Reserved"
            ).with_for_update().first()
            required = round(float(line.quantity) * float(order.quantity), 3)
            if reservation is None or reservation.remaining_quantity + 0.0001 < required:
                raise HTTPException(409, f"Material {line.material_id} is not fully reserved for this order")

    if action == "release":
        operations = db.query(models.ProductionOrderOperation).filter_by(production_order_id=order.id).all()
        if not operations:
            raise HTTPException(409, "At least one production operation is required")
        order.status = "Released"
        for operation_row in operations:
            existing_card = db.query(models.JobCard).filter_by(production_order_operation_id=operation_row.id).first()
            if existing_card is None:
                db.add(models.JobCard(
                    production_order_id=order.id,
                    production_order_operation_id=operation_row.id,
                    operation_id=operation_row.operation_id,
                    workcenter_id=operation_row.workcenter_id,
                    assigned_employee_id=operation_row.assigned_employee_id,
                    planned_qty=operation_row.planned_qty,
                    status="Pending",
                ))
    elif action == "start":
        operations = db.query(models.ProductionOrderOperation).filter_by(production_order_id=order.id).all()
        if not operations:
            raise HTTPException(409, "At least one production operation is required")
        unassigned = [row for row in operations if row.assigned_employee_id is None]
        if unassigned:
            raise HTTPException(409, "Assign an employee to every operation before starting production")
        order.status = "In Progress"
    elif action == "complete":
        produced = float(db.query(func.coalesce(func.sum(models.ProductionEntry.quantity), 0.0)).filter(
            models.ProductionEntry.production_order_id == order.id
        ).scalar() or 0.0)
        operations = db.query(models.ProductionOrderOperation).filter_by(production_order_id=order.id).all()
        if round(produced, 3) < round(order.quantity, 3):
            raise HTTPException(409, f"Cannot complete order: produced {round(produced, 3)} of {order.quantity}")
        if not operations or any(row.completed_qty + 0.0001 < row.planned_qty for row in operations):
            raise HTTPException(409, "All production operations must be completed before closing the order")
        order.status = "Completed"
        for reservation in db.query(models.StockReservation).filter_by(production_order_id=order.id, status="Reserved").with_for_update().all():
            reservation.status = "Released"
            reservation.released_at = datetime.now(timezone.utc)
    else:  # cancel
        produced = float(db.query(func.coalesce(func.sum(models.ProductionEntry.quantity), 0.0)).filter(
            models.ProductionEntry.production_order_id == order.id
        ).scalar() or 0.0)
        if produced > 0:
            raise HTTPException(409, "An order with posted production cannot be cancelled; complete or use a controlled reversal")
        order.status = "Cancelled"
        for reservation in db.query(models.StockReservation).filter_by(production_order_id=order.id, status="Reserved").with_for_update().all():
            reservation.status = "Released"
            reservation.released_at = datetime.now(timezone.utc)

    log_audit(db, user.username, "TRANSITION", "production_order", f"{order.order_no}: {action}")
    db.commit()
    db.refresh(order)
    return {**{k:getattr(order,k) for k in ("id","order_no","order_date","product_id","quantity","due_date","routing_id","status","remarks")},
            "operations": db.query(models.ProductionOrderOperation).filter_by(production_order_id=order.id).order_by(models.ProductionOrderOperation.sequence).all()}


@router.patch("/production-orders/{order_id}/operations/{operation_row_id}/assignment", response_model=schemas.ManufacturingAssignmentOut)
def assign_operation_employee(order_id: str, operation_row_id: str, payload: schemas.AssignEmployeeIn, db: Session = Depends(get_db), user: models.User = guard):
    row = db.get(models.ProductionOrderOperation, operation_row_id)
    if not row or row.production_order_id != order_id:
        raise HTTPException(404, "Production order operation not found")
    operation = db.get(models.RoutingOperation, row.operation_id)
    employee = db.get(models.Employee, payload.employee_id) if payload.employee_id else _auto_employee(db, operation)
    if employee is None or not employee.active:
        raise HTTPException(400, "No active employee matches the routing skill")
    if operation.required_skill:
        skilled = db.query(models.EmployeeSkill).filter_by(employee_id=employee.id, skill=operation.required_skill, active=True).first()
        if not skilled:
            raise HTTPException(400, "Employee does not have the required routing skill")
    row.assigned_employee_id = employee.id
    row.status = "Assigned"
    card = db.query(models.JobCard).filter_by(production_order_operation_id=row.id).first()
    if card is not None:
        card.assigned_employee_id = employee.id
    log_audit(db, user.username, "ASSIGN", "production_order_operation", f"{order_id}: {employee.emp_code}")
    db.commit()
    return {"operation_id": operation.id, "workcenter_id": row.workcenter_id, "employee_id": employee.id, "assignment_mode": "manual" if payload.employee_id else "automatic"}


def _job_card_payload(db: Session, card: models.JobCard):
    logs = db.query(models.JobCardTimeLog).filter_by(job_card_id=card.id).order_by(models.JobCardTimeLog.start_time).all()
    return {**{k: getattr(card, k) for k in ("id", "production_order_id", "production_order_operation_id", "operation_id", "workcenter_id", "assigned_employee_id", "planned_qty", "completed_qty", "status", "started_at", "completed_at", "remarks")}, "time_logs": logs}


@router.get("/production-orders/{order_id}/job-cards", response_model=list[schemas.JobCardOut])
def list_job_cards(order_id: str, db: Session = Depends(get_db), user: models.User = guard):
    if db.get(models.ProductionOrder, order_id) is None:
        raise HTTPException(404, "Production order not found")
    cards = db.query(models.JobCard).filter_by(production_order_id=order_id).order_by(models.JobCard.id).all()
    return [_job_card_payload(db, card) for card in cards]


@router.post("/production-orders/{order_id}/job-cards", response_model=list[schemas.JobCardOut], status_code=201)
def generate_job_cards(order_id: str, db: Session = Depends(get_db), user: models.User = guard):
    order = db.get(models.ProductionOrder, order_id)
    if order is None:
        raise HTTPException(404, "Production order not found")
    operations = db.query(models.ProductionOrderOperation).filter_by(production_order_id=order.id).order_by(models.ProductionOrderOperation.sequence).all()
    if not operations:
        raise HTTPException(409, "Production order has no operations")
    for operation_row in operations:
        card = db.query(models.JobCard).filter_by(production_order_operation_id=operation_row.id).first()
        if card is None:
            db.add(models.JobCard(production_order_id=order.id, production_order_operation_id=operation_row.id,
                operation_id=operation_row.operation_id, workcenter_id=operation_row.workcenter_id,
                assigned_employee_id=operation_row.assigned_employee_id, planned_qty=operation_row.planned_qty, status="Pending"))
    log_audit(db, user.username, "GENERATE", "job_cards", order.order_no)
    db.commit()
    cards = db.query(models.JobCard).filter_by(production_order_id=order.id).order_by(models.JobCard.id).all()
    return [_job_card_payload(db, card) for card in cards]


@router.post("/job-cards/{job_card_id}/start", response_model=schemas.JobCardOut)
def start_job_card(job_card_id: str, db: Session = Depends(get_db), user: models.User = guard):
    card = db.query(models.JobCard).filter_by(id=job_card_id).with_for_update().first()
    if card is None:
        raise HTTPException(404, "Job card not found")
    order = db.get(models.ProductionOrder, card.production_order_id)
    if order is None or order.status != "In Progress":
        raise HTTPException(409, "Production order must be In Progress before starting a job card")
    if card.status != "Pending":
        raise HTTPException(409, f"Cannot start a job card in {card.status} status")
    if not card.assigned_employee_id:
        raise HTTPException(409, "Assign an employee before starting this job card")
    employee = db.get(models.Employee, card.assigned_employee_id)
    if employee is None or not employee.active:
        raise HTTPException(409, "Assigned employee is inactive or missing")
    now = datetime.now(timezone.utc)
    card.status = "In Progress"
    card.started_at = now
    db.add(models.JobCardTimeLog(job_card_id=card.id, employee_id=employee.id, start_time=now, remarks="Started from job card"))
    log_audit(db, user.username, "START", "job_card", card.id)
    db.commit()
    db.refresh(card)
    return _job_card_payload(db, card)


@router.post("/job-cards/{job_card_id}/stop", response_model=schemas.JobCardOut)
def stop_job_card(job_card_id: str, db: Session = Depends(get_db), user: models.User = guard):
    card = db.query(models.JobCard).filter_by(id=job_card_id).with_for_update().first()
    if card is None:
        raise HTTPException(404, "Job card not found")
    if card.status != "In Progress":
        raise HTTPException(409, "Only an in-progress job card can be stopped")
    active_log = db.query(models.JobCardTimeLog).filter_by(job_card_id=card.id, end_time=None).with_for_update().first()
    if active_log is None:
        raise HTTPException(409, "No active time log exists for this job card")
    now = datetime.now(timezone.utc)
    active_log.end_time = now
    started_at = active_log.start_time
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    active_log.duration_minutes = round(max((now - started_at).total_seconds() / 60, 0), 2)
    card.status = "Pending" if card.completed_qty <= 0 else "In Progress"
    log_audit(db, user.username, "STOP", "job_card", card.id)
    db.commit()
    db.refresh(card)
    return _job_card_payload(db, card)


@router.post("/job-cards/{job_card_id}/time-logs", response_model=schemas.JobCardTimeLogOut, status_code=201)
def add_job_card_time_log(job_card_id: str, payload: schemas.JobCardTimeLogIn, db: Session = Depends(get_db), user: models.User = guard):
    card = db.get(models.JobCard, job_card_id)
    if card is None:
        raise HTTPException(404, "Job card not found")
    employee_id = payload.employee_id or card.assigned_employee_id
    employee = db.get(models.Employee, employee_id) if employee_id else None
    if employee is None or not employee.active:
        raise HTTPException(400, "An active employee is required for a time log")
    if payload.end_time is not None and payload.end_time <= payload.start_time:
        raise HTTPException(400, "Time-log end must be later than start")
    overlap = db.query(models.JobCardTimeLog).filter(
        models.JobCardTimeLog.employee_id == employee.id,
        models.JobCardTimeLog.start_time < (payload.end_time or datetime.max.replace(tzinfo=timezone.utc)),
        (models.JobCardTimeLog.end_time.is_(None)) | (models.JobCardTimeLog.end_time > payload.start_time),
    ).first()
    if overlap is not None:
        raise HTTPException(409, "Employee already has an overlapping job-card time log")
    duration = round((payload.end_time - payload.start_time).total_seconds() / 60, 2) if payload.end_time else 0
    row = models.JobCardTimeLog(job_card_id=card.id, employee_id=employee.id, start_time=payload.start_time,
        end_time=payload.end_time, duration_minutes=duration, completed_qty=payload.completed_qty, remarks=payload.remarks)
    db.add(row)
    log_audit(db, user.username, "CREATE", "job_card_time_log", card.id)
    db.commit()
    db.refresh(row)
    return row


@router.post("/job-cards/{job_card_id}/complete", response_model=schemas.JobCardOut)
def complete_job_card(job_card_id: str, db: Session = Depends(get_db), user: models.User = guard):
    card = db.query(models.JobCard).filter_by(id=job_card_id).with_for_update().first()
    if card is None:
        raise HTTPException(404, "Job card not found")
    if card.status == "Completed":
        raise HTTPException(409, "Job card is already completed")
    if card.completed_qty + 0.0001 < card.planned_qty:
        raise HTTPException(409, f"Job card output is incomplete ({card.completed_qty} of {card.planned_qty})")
    active_log = db.query(models.JobCardTimeLog).filter_by(job_card_id=card.id, end_time=None).first()
    if active_log is not None:
        raise HTTPException(409, "Stop the active time log before completing the job card")
    card.status = "Completed"
    card.completed_at = datetime.now(timezone.utc)
    operation_row = db.get(models.ProductionOrderOperation, card.production_order_operation_id)
    if operation_row is not None:
        operation_row.status = "Completed"
        operation_row.completed_qty = max(operation_row.completed_qty, card.completed_qty)
    log_audit(db, user.username, "COMPLETE", "job_card", card.id)
    db.commit()
    db.refresh(card)
    return _job_card_payload(db, card)


@router.patch("/production/{production_id}/quality", response_model=schemas.ProductionOut)
def update_production_quality(production_id: str, payload: schemas.ProductionQualityIn, db: Session = Depends(get_db), user: models.User = guard):
    production = db.get(models.ProductionEntry, production_id)
    if not production:
        raise HTTPException(404, "Production entry not found")
    if round(payload.accepted_qty + payload.rejected_qty, 3) > round(production.quantity, 3):
        raise HTTPException(400, "Accepted plus rejected quantity cannot exceed produced quantity")
    production.quality_status = payload.status
    production.accepted_qty = payload.accepted_qty
    production.rejected_qty = payload.rejected_qty
    production.quality_remarks = payload.remarks
    log_audit(db, user.username, "QUALITY", "production", production.batch_no + ": " + payload.status)
    db.commit()
    db.refresh(production)
    return production


@router.get("/reports/production", response_model=schemas.ManufacturingReportOut)
def manufacturing_report(db: Session = Depends(get_db), user: models.User = guard):
    rows = db.query(models.ProductionEntry).all()
    production_qty = sum(x.quantity for x in rows)
    scrap_qty = sum(x.actual_scrap or 0 for x in rows)
    planned = sum(c.planned_quantity for x in rows for c in x.consumption)
    actual = sum(c.quantity for x in rows for c in x.consumption)
    by = {}
    for x in rows:
        key = x.workcenter_id or "Unassigned"
        item = by.setdefault(key, {"workcenter_id": key, "production_qty": 0, "scrap_qty": 0, "material_variance": 0})
        item["production_qty"] += x.quantity
        item["scrap_qty"] += x.actual_scrap or 0
        item["material_variance"] += sum(c.quantity - c.planned_quantity for c in x.consumption)
    return {
        "production_qty": production_qty,
        "scrap_qty": scrap_qty,
        "planned_material_qty": planned,
        "actual_material_qty": actual,
        "material_variance": actual - planned,
        "by_workcenter": list(by.values()),
    }
