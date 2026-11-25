"""Production planning, reservation, scheduling and costing calculations."""
from __future__ import annotations

from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models


ACTIVE_ORDER_STATUSES = {"Planned", "Materials Pending", "Ready", "Scheduled", "In Progress"}


def plan_materials(db: Session, order: models.ProductionOrder) -> list[dict]:
    """Reserve available stock logically; physical inventory balances stay unchanged."""
    bom = (
        db.query(models.BillOfMaterials)
        .filter(models.BillOfMaterials.product_id == order.product_id,
                models.BillOfMaterials.active.is_(True))
        .order_by(models.BillOfMaterials.version.desc())
        .first()
    )
    if not bom or not bom.lines:
        raise ValueError("Active BOM is missing or has no material lines")
    prior = db.query(models.MaterialReservation).filter_by(production_order_id=order.id).all()
    prior_by_material = {r.material_id: r for r in prior}
    result = []
    for line in bom.lines:
        material = db.query(models.RawMaterial).filter(models.RawMaterial.id == line.material_id).with_for_update().first()
        if material is None:
            raise ValueError(f"BOM material {line.material_id} no longer exists")
        required = round(float(line.quantity) * float(order.quantity), 3)
        reserved_elsewhere = db.query(func.coalesce(func.sum(models.MaterialReservation.reserved_quantity), 0)).filter(
            models.MaterialReservation.material_id == material.id,
            models.MaterialReservation.production_order_id != order.id,
            models.MaterialReservation.status.in_(["reserved", "partial"]),
        ).scalar() or 0
        available = max(0.0, round(float(material.stock or 0) - float(reserved_elsewhere), 3))
        reserved = min(required, available)
        shortage = round(max(0.0, required - reserved), 3)
        row = prior_by_material.get(material.id)
        if row is None:
            row = models.MaterialReservation(production_order_id=order.id, material_id=material.id)
            db.add(row)
        row.required_quantity = required
        row.reserved_quantity = round(reserved, 3)
        row.status = "reserved" if shortage == 0 else ("partial" if reserved > 0 else "shortage")
        row.updated_at = datetime.utcnow()
        result.append({
            "material_id": material.id, "material_name": material.name,
            "required_quantity": required, "available_quantity": available,
            "reserved_quantity": round(reserved, 3), "shortage_quantity": shortage,
        })
    valid_ids = {x["material_id"] for x in result}
    for row in prior:
        if row.material_id not in valid_ids:
            db.delete(row)
    order.planning_status = "materials_ready" if all(x["shortage_quantity"] == 0 for x in result) else "materials_short"
    order.status = "Ready" if order.planning_status == "materials_ready" else "Materials Pending"
    db.flush()
    return result


def _overlap(start: datetime, end: datetime, other_start: datetime, other_end: datetime) -> bool:
    return start < other_end and other_start < end


def schedule_order(db: Session, order: models.ProductionOrder, start_at: datetime,
                   respect_employee_availability: bool = True, machine_id: str | None = None) -> list[models.ProductionOrderOperation]:
    rows = db.query(models.ProductionOrderOperation).filter_by(
        production_order_id=order.id
    ).order_by(models.ProductionOrderOperation.sequence).all()
    if not rows:
        raise ValueError("Production order has no routing operations")
    previous_end = start_at
    for row in rows:
        op = db.get(models.RoutingOperation, row.operation_id)
        wc = db.get(models.Workcenter, row.workcenter_id)
        if not op or not wc or not wc.active or wc.status in {"Under Maintenance", "Breakdown"}:
            raise ValueError(f"Operation {row.sequence} has an inactive or unavailable work centre")
        if wc.capacity_per_hour <= 0:
            raise ValueError(f"Work centre {wc.code} has no positive capacity")
        machine = db.get(models.MachineResource, machine_id) if machine_id else None
        if machine_id and (not machine or machine.workcenter_id != wc.id or not machine.active or machine.status != "available"):
            raise ValueError(f"Machine {machine_id} is unavailable or not assigned to this work centre")
        if machine is None:
            machine = db.query(models.MachineResource).filter(
                models.MachineResource.workcenter_id == wc.id,
                models.MachineResource.active.is_(True),
                models.MachineResource.status == "available",
            ).order_by(models.MachineResource.capacity_per_hour.desc()).first()
        capacity = float(machine.capacity_per_hour) if machine else float(wc.capacity_per_hour)
        duration = float(op.setup_minutes or 0) + float(order.quantity) * float(op.run_minutes_per_unit or 0)
        if not op.run_minutes_per_unit:
            duration += float(order.quantity) / max(capacity, 0.0001) * 60
        duration = max(1.0, duration)
        candidate = max(start_at, previous_end)
        employee = db.get(models.Employee, row.assigned_employee_id) if row.assigned_employee_id else None
        if employee and (not employee.active or employee.employee_type != models.EmployeeType.shop_floor):
            employee = None
        if employee and op.required_skill and not db.query(models.EmployeeSkill).filter_by(
            employee_id=employee.id, skill=op.required_skill, active=True
        ).first():
            employee = None
        if employee is None:
            q = db.query(models.Employee).join(models.EmployeeSkill).filter(
                models.Employee.active.is_(True), models.Employee.employee_type == models.EmployeeType.shop_floor,
                models.EmployeeSkill.active.is_(True),
            )
            if op.required_skill:
                q = q.filter(models.EmployeeSkill.skill == op.required_skill)
            employee = q.order_by(models.EmployeeSkill.level.desc(), models.Employee.emp_code).first()
        for _ in range(1000):
            end = candidate + timedelta(minutes=duration)
            other_rows = db.query(models.ProductionOrderOperation).filter(
                models.ProductionOrderOperation.id != row.id,
                models.ProductionOrderOperation.scheduled_start.is_not(None),
            ).all()
            blocking_end = None
            current_order_operation_ids = {x.id for x in rows}
            for other in other_rows:
                if other.id in current_order_operation_ids:
                    continue
                if not other.scheduled_start or not other.scheduled_end:
                    continue
                same_wc = other.workcenter_id == row.workcenter_id
                same_employee = employee is not None and other.assigned_employee_id == employee.id
                same_machine = machine is not None and other.machine_id == machine.id
                if (same_wc or same_machine or (respect_employee_availability and same_employee)) and _overlap(candidate, end, other.scheduled_start, other.scheduled_end):
                    blocking_end = max(blocking_end or other.scheduled_end, other.scheduled_end)
            if machine:
                downtime_rows = db.query(models.MachineDowntime).filter(
                    models.MachineDowntime.machine_id == machine.id,
                    models.MachineDowntime.start_at < end,
                ).all()
                for downtime in downtime_rows:
                    if downtime.end_at is None and _overlap(candidate, end, downtime.start_at, end):
                        raise ValueError(f"Machine {machine.code} has an open downtime; close it before scheduling")
                    downtime_end = downtime.end_at or end
                    if _overlap(candidate, end, downtime.start_at, downtime_end):
                        blocking_end = max(blocking_end or downtime_end, downtime_end)
            if blocking_end is None:
                break
            candidate = blocking_end
        else:
            raise ValueError("Unable to find a schedule slot within planning horizon")
        row.assigned_employee_id = employee.id if employee else None
        row.machine_id = machine.id if machine else None
        row.planned_minutes = round(duration, 2)
        row.scheduled_start = candidate
        row.scheduled_end = candidate + timedelta(minutes=duration)
        row.status = "Scheduled" if employee else "Scheduled - Unassigned"
        previous_end = row.scheduled_end
    order.planning_status = "scheduled"
    order.status = "Scheduled"
    db.flush()
    return rows


def calculate_mrp(db: Session) -> list[dict]:
    """Aggregate demand and net supply; no purchase requisitions are generated."""
    gross = defaultdict(float)
    demand_orders = defaultdict(set)
    for order in db.query(models.ProductionOrder).filter(models.ProductionOrder.status.in_(ACTIVE_ORDER_STATUSES)).all():
        bom = db.query(models.BillOfMaterials).filter_by(product_id=order.product_id, active=True).order_by(models.BillOfMaterials.version.desc()).first()
        if not bom:
            continue
        for line in bom.lines:
            gross[line.material_id] += float(line.quantity) * float(order.quantity)
            demand_orders[line.material_id].add(order.order_no)
    result = []
    open_statuses = [models.PurchaseOrderStatus.sent, models.PurchaseOrderStatus.partially_received]
    open_pos = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.status.in_(open_statuses)).all()
    for material_id, gross_qty in sorted(gross.items()):
        material = db.get(models.RawMaterial, material_id)
        if not material:
            continue
        reserved = db.query(func.coalesce(func.sum(models.MaterialReservation.reserved_quantity), 0)).filter(
            models.MaterialReservation.material_id == material_id,
            models.MaterialReservation.status.in_(["reserved", "partial"]),
        ).scalar() or 0
        open_supply = sum(
            max(0.0, float(line.quantity or 0) - float(line.received_quantity or 0))
            for po in open_pos for line in po.lines if line.material_id == material_id
        )
        stock = float(material.stock or 0)
        safety = float(material.min_stock or 0)
        available_supply = stock + open_supply
        net = round(max(0.0, gross_qty + safety - available_supply), 3)
        result.append({
            "material_id": material_id, "material_name": material.name,
            "gross_demand": round(gross_qty, 3), "stock": stock,
            "reserved": round(float(reserved), 3), "open_purchase_supply": round(open_supply, 3),
            "safety_stock": safety, "net_requirement": net,
            "demand_orders": sorted(demand_orders[material_id]),
        })
    return result


def save_cost(db: Session, order: models.ProductionOrder, payload: dict) -> models.ProductionCost:
    row = db.query(models.ProductionCost).filter_by(production_order_id=order.id).first()
    if row is None:
        row = models.ProductionCost(production_order_id=order.id)
        db.add(row)
    for field in ("labour_cost", "machine_cost", "overhead_cost", "quantity_produced"):
        setattr(row, field, float(payload.get(field, 0)))
    material_cost = float(payload.get("material_cost", 0))
    if material_cost <= 0:
        actual_material_cost = 0.0
        entries = db.query(models.ProductionEntry).filter_by(production_order_id=order.id).all()
        for entry in entries:
            for consumption in entry.consumption:
                material = db.get(models.RawMaterial, consumption.material_id)
                if material:
                    actual_material_cost += float(consumption.quantity or 0) * float(material.cost or 0)
        row.material_cost = round(actual_material_cost, 2)
    else:
        row.material_cost = material_cost
    row.total_cost = round(row.material_cost + row.labour_cost + row.machine_cost + row.overhead_cost, 2)
    row.unit_cost = round(row.total_cost / row.quantity_produced, 4) if row.quantity_produced > 0 else 0
    db.flush()
    return row
