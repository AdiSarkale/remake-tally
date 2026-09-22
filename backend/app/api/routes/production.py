"""Production routes: create batches (FG in, RM out) and list history."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.models import ItemKind, MovementType
from app.services.inventory import apply_movement, log_audit, next_batch_no

router = APIRouter(prefix="/production", tags=["production"])
guard = Depends(require_area("production"))


@router.get("", response_model=list[schemas.ProductionOut])
def list_production(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    productions = (
        db.query(models.ProductionEntry)
        .order_by(models.ProductionEntry.entry_date.desc())
        .all()
    )

    result = []

    for production in productions:

        actual_scrap = (
            db.query(func.coalesce(func.sum(models.ScrapEntry.quantity), 0))
            .filter(models.ScrapEntry.batch_no == production.batch_no)
            .scalar()
        )

        result.append({
            "id": production.id,
            "batch_no": production.batch_no,
            "entry_date": production.entry_date,
            "product_id": production.product_id,
            "quantity": production.quantity,
            "machine": production.machine,
            "workcenter_id": production.workcenter_id,
            "routing_id": production.routing_id,
            "operation_id": production.operation_id,
            "production_order_id": production.production_order_id,
            "employee_id": production.employee_id,
            "operator": production.operator,
            "shift": production.shift,
            "remarks": production.remarks,
            "actual_scrap": actual_scrap,
            "quality_status": production.quality_status,
            "accepted_qty": production.accepted_qty,
            "rejected_qty": production.rejected_qty,
            "quality_remarks": production.quality_remarks,
            "consumption": [
                {"material_id": line.material_id, "planned_quantity": line.planned_quantity, "quantity": line.quantity, "variance": round(line.quantity - line.planned_quantity, 3)}
                for line in production.consumption
            ],
        })

    return result

@router.post("", response_model=schemas.ProductionOut, status_code=201)
def create_production(
    payload: schemas.ProductionIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    product = db.get(models.Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=400, detail="Product not found")

    batch_no = next_batch_no(db)

    # Resolve routing/workcenter/employee from the production order when supplied.
    order_op = None
    if payload.production_order_id:
        order = db.get(models.ProductionOrder, payload.production_order_id)
        if not order:
            raise HTTPException(400, "Production order not found")
        if order.product_id != payload.product_id:
            raise HTTPException(400, "Production order does not belong to product")
        if payload.operation_id:
            order_op = db.get(models.ProductionOrderOperation, payload.operation_id)
            if not order_op or order_op.production_order_id != order.id:
                raise HTTPException(400, "Production order operation not found")
        else:
            order_op = db.query(models.ProductionOrderOperation).filter_by(
                production_order_id=order.id, status="Assigned"
            ).order_by(models.ProductionOrderOperation.sequence).first()
        if not order_op:
            raise HTTPException(400, "No assigned production operation available")
        remaining = round(order_op.planned_qty - order_op.completed_qty, 3)
        if payload.quantity > remaining:
            raise HTTPException(400, f"Production quantity exceeds operation remaining quantity ({remaining})")
        payload.workcenter_id = payload.workcenter_id or order_op.workcenter_id
        payload.employee_id = payload.employee_id or order_op.assigned_employee_id
        payload.routing_id = payload.routing_id or order.routing_id

    if payload.workcenter_id:
        wc = db.get(models.Workcenter, payload.workcenter_id)
        if not wc or not wc.active:
            raise HTTPException(400, "Workcenter not found or inactive")
        if wc.status in ("Under Maintenance", "Breakdown"):
            raise HTTPException(400, f"Workcenter {wc.code} is {wc.status}")
    if payload.employee_id:
        employee = db.get(models.Employee, payload.employee_id)
        if not employee or not employee.active:
            raise HTTPException(400, "Employee not found or inactive")
        if order_op and order_op.operation_id:
            operation = db.get(models.RoutingOperation, order_op.operation_id)
            if operation and operation.required_skill:
                skilled = db.query(models.EmployeeSkill).filter_by(employee_id=employee.id, skill=operation.required_skill, active=True).first()
                if not skilled:
                    raise HTTPException(400, "Employee does not have the required routing skill")

    # -------------------------------------------------
    # Find active BOM
    # -------------------------------------------------

    bom = (
        db.query(models.BillOfMaterials)
        .filter(
            models.BillOfMaterials.product_id == payload.product_id,
            models.BillOfMaterials.active.is_(True),
        )
        .order_by(models.BillOfMaterials.version.desc())
        .first()
    )

    if bom is None:
        raise HTTPException(
            status_code=400,
            detail="No active BOM found for this product",
        )

    if not bom.lines:
        raise HTTPException(
            status_code=400,
            detail="Active BOM has no material lines",
        )

    # -------------------------------------------------
    # Calculate BOM consumption
    # -------------------------------------------------

    consumption = []


    for bom_line in bom.lines:
        required_quantity = round(
            bom_line.quantity * payload.quantity,
            3,
        )

        material = db.get(
            models.RawMaterial,
            bom_line.material_id,
        )

        if material is None:
            raise HTTPException(
                status_code=400,
                detail=f"Material {bom_line.material_id} not found",
            )

        consumption.append(
            models.ProductionConsumption(
                material_id=bom_line.material_id,
                planned_quantity=required_quantity,
                quantity=required_quantity
            )
        )
    # -------------------------------------------------
    # Validate legacy/manual consumption input
    # -------------------------------------------------
    if payload.consumption:
        supplied = {}
        for line in payload.consumption:
            if line.material_id in supplied:
                raise HTTPException(400, "A material cannot appear twice in production consumption")
            supplied[line.material_id] = round(line.quantity, 3)

        planned = {line.material_id: round(line.quantity * payload.quantity, 3) for line in bom.lines}
        unknown = set(supplied) - set(planned)
        missing = set(planned) - set(supplied)
        if unknown:
            raise HTTPException(400, "Actual consumption may only contain materials from the active BOM")
        if missing:
            raise HTTPException(400, "Actual consumption must include every active BOM material line")

        for consumption_line in consumption:
            consumption_line.quantity = supplied[consumption_line.material_id]
        for consumption_line in consumption:
            if consumption_line.quantity < 0:
                raise HTTPException(400, "Actual consumption cannot be negative")
            material = db.get(models.RawMaterial, consumption_line.material_id)
            if material and material.stock < consumption_line.quantity:
                raise HTTPException(400, f"Insufficient stock for {material.name} (required {consumption_line.quantity}, available {material.stock})")

    # -------------------------------------------------
    # Calculate scrap
    # -------------------------------------------------

    calculated_scrap = 0.0

    if bom.expected_scrap_percent > 0:
        calculated_scrap = round(
            (payload.quantity * bom.expected_scrap_percent) / 100,
            3,
        )

    # Manual actual scrap overrides BOM calculated scrap
    actual_scrap = (calculated_scrap)

    actual_scrap = round(actual_scrap, 3)

    # Production payload overrides BOM scrap type
    scrap_type_id = payload.scrap_type_id or bom.scrap_type_id

    if actual_scrap > 0:
        scrap_type = db.get(models.ScrapType, scrap_type_id) if scrap_type_id else None
        if scrap_type is None or not scrap_type.active:
            raise HTTPException(
                status_code=400,
                detail="Scrap type is required and must be active when scrap quantity is greater than zero",
            )


    # -------------------------------------------------
    # Create production entry
    # -------------------------------------------------

    entry = models.ProductionEntry(
        batch_no=batch_no,
        entry_date=payload.entry_date,
        product_id=payload.product_id,
        quantity=payload.quantity,
        machine=payload.machine,
        workcenter_id=payload.workcenter_id,
        routing_id=payload.routing_id,
        operation_id=payload.operation_id or (order_op.operation_id if order_op else None),
        production_order_id=payload.production_order_id,
        employee_id=payload.employee_id,
        operator=payload.operator,
        shift=payload.shift,
        remarks=payload.remarks,
        actual_scrap = actual_scrap,
        consumption=consumption,
    )

    db.add(entry)

    # -------------------------------------------------
    # Raw materials OUT
    # -------------------------------------------------

    for consumption_line in consumption:
        apply_movement(
            db,
            kind=ItemKind.material,
            item_id=consumption_line.material_id,
            movement_type=MovementType.OUT,
            quantity=consumption_line.quantity,
            reference=batch_no,
            reason="Production consumption",
            entry_date=payload.entry_date,
            user_id=user.id,
        )

       # -------------------------------------------------
    # Finished product IN
    # -------------------------------------------------

    apply_movement(
        db,
        kind=ItemKind.product,
        item_id=payload.product_id,
        movement_type=MovementType.IN,
        quantity=payload.quantity,
        reference=batch_no,
        reason="Production output",
        entry_date=payload.entry_date,
        user_id=user.id,
    )


    # -------------------------------------------------
    # Scrap IN
    # -------------------------------------------------

    if actual_scrap > 0:

        if not scrap_type_id:
            raise HTTPException(
                status_code=400,
                detail="Scrap type is required when scrap quantity is greater than zero",
            )

        apply_movement(
            db,
            kind=ItemKind.scrap,
            item_id=scrap_type_id,
            movement_type=MovementType.IN,
            quantity=actual_scrap,
            reference=batch_no,
            reason="Production scrap",
            entry_date=payload.entry_date,
            user_id=user.id,
        )

    # -------------------------------------------------
    # Save production
    # -------------------------------------------------

    if order_op:
        order_op.completed_qty += payload.quantity
        order_op.status = "Completed" if order_op.completed_qty >= order_op.planned_qty else "In Progress"
        order = db.get(models.ProductionOrder, payload.production_order_id)
        if order:
            ops = db.query(models.ProductionOrderOperation).filter_by(production_order_id=order.id).all()
            if ops and all(x.completed_qty >= x.planned_qty for x in ops):
                order.status = "Completed"
            elif any(x.completed_qty > 0 for x in ops):
                order.status = "In Progress"

    log_audit(
        db,
        user.username,
        "CREATE",
        "production",
        f"{batch_no}: {payload.quantity} units, scrap: {actual_scrap}",
    )

    db.commit()
    db.refresh(entry)

    return entry
