"""Manufacturing master data, routing, workcenter and production-order execution APIs."""

from fastapi import APIRouter, Depends, HTTPException
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
    log_audit(db, user.username, "ASSIGN", "production_order_operation", f"{order_id}: {employee.emp_code}")
    db.commit()
    return {"operation_id": operation.id, "workcenter_id": row.workcenter_id, "employee_id": employee.id, "assignment_mode": "manual" if payload.employee_id else "automatic"}
