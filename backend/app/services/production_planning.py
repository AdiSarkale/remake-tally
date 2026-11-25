"""Production planning calculations. Reservations are planning records, not stock movements."""
from __future__ import annotations
from collections import defaultdict
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app import models

PLANNABLE_ORDER_STATUSES = {"Planned", "Materials Pending", "Ready", "Scheduled"}

def explode_bom(db: Session, product_id: str, quantity: float) -> list[dict]:
    if quantity <= 0:
        raise HTTPException(400, "Production quantity must be positive")
    bom = db.query(models.BillOfMaterials).filter_by(product_id=product_id, active=True).order_by(models.BillOfMaterials.version.desc()).first()
    if not bom:
        raise HTTPException(400, "No active BOM for product")
    lines=[]
    for line in bom.lines:
        material=db.get(models.RawMaterial,line.material_id)
        if not material:
            raise HTTPException(409, f"BOM material {line.material_id} is missing")
        required=round(float(line.quantity)*quantity,6)
        lines.append({"material_id":material.id,"material_code":material.code,"material_name":material.name,"unit":material.unit,"required_quantity":required,"physical_stock":material.stock,"safety_stock":material.min_stock})
    return lines

def material_requirements(db: Session, order_id: str) -> list[dict]:
    order=db.get(models.ProductionOrder,order_id)
    if not order: raise HTTPException(404,"Production order not found")
    lines=explode_bom(db,order.product_id,order.quantity)
    for line in lines:
        reservations=db.query(models.MaterialReservation).filter_by(material_id=line["material_id"],status="active").all()
        active_reserved=sum(r.reserved_quantity for r in reservations)
        other_reserved=sum(r.reserved_quantity for r in reservations if r.production_order_id!=order.id)
        line["reserved_for_order"]=sum(r.reserved_quantity for r in reservations if r.production_order_id==order.id)
        line["reserved_total"]=active_reserved
        line["available_before_order_reservation"]=max(0,round(line["physical_stock"]-other_reserved,6))
        line["shortage_before_reservation"]=max(0,round(line["required_quantity"]-line["available_before_order_reservation"],6))
    return lines

def reserve_order_materials(db: Session, order_id: str) -> dict:
    order=db.get(models.ProductionOrder,order_id)
    if not order: raise HTTPException(404,"Production order not found")
    requirements=material_requirements(db,order_id)
    # Replace this order's active reservation set; never touch RawMaterial.stock.
    db.query(models.MaterialReservation).filter_by(production_order_id=order.id,status="active").update({"status":"released"},synchronize_session=False)
    results=[]
    for item in requirements:
        other=sum(r.reserved_quantity for r in db.query(models.MaterialReservation).filter_by(material_id=item["material_id"],status="active").all())
        material=db.get(models.RawMaterial,item["material_id"])
        available=max(0,round(material.stock-other,6))
        reserve=min(item["required_quantity"],available)
        shortage=round(item["required_quantity"]-reserve,6)
        row=models.MaterialReservation(production_order_id=order.id,material_id=material.id,required_quantity=item["required_quantity"],reserved_quantity=reserve,status="active")
        db.add(row)
        results.append({**item,"reserved_quantity":reserve,"shortage_quantity":shortage,"status":"reserved" if shortage==0 else "partial"})
    all_reserved=all(x["shortage_quantity"]==0 for x in results)
    order.status="Ready" if all_reserved else "Materials Pending"
    db.flush()
    return {"production_order_id":order.id,"order_no":order.order_no,"status":order.status,"physical_stock_unchanged":True,"materials":results}

def mrp_net_requirements(db: Session) -> list[dict]:
    demand=defaultdict(float)
    order_refs=defaultdict(list)
    orders=db.query(models.ProductionOrder).filter(models.ProductionOrder.status.in_(PLANNABLE_ORDER_STATUSES)).all()
    for order in orders:
        for line in explode_bom(db,order.product_id,order.quantity):
            demand[line["material_id"]]+=line["required_quantity"]
            order_refs[line["material_id"]].append({"order_id":order.id,"order_no":order.order_no,"gross_demand":line["required_quantity"],"due_date":str(order.due_date) if order.due_date else None})
    output=[]
    for material_id,gross in demand.items():
        m=db.get(models.RawMaterial,material_id)
        reserved=sum(x.reserved_quantity for x in db.query(models.MaterialReservation).filter_by(material_id=material_id,status="active").all())
        open_po=0.0
        receipts=[]
        for po in db.query(models.PurchaseOrder).all():
            status=getattr(po.status,"value",str(po.status))
            if status not in {"sent","partially_received"}: continue
            for line in po.lines:
                if line.material_id==material_id:
                    remaining=max(0,line.quantity-(line.received_quantity or 0))
                    open_po+=remaining
                    if remaining:
                        receipts.append({"po_no":po.po_no,"expected_date":str(po.expected_date) if po.expected_date else None,"open_quantity":remaining})
        net_available=max(0,m.stock-reserved)+open_po
        safety=m.min_stock or 0
        shortage=max(0,round(gross+safety-net_available,6))
        output.append({"material_id":m.id,"material_code":m.code,"material_name":m.name,"unit":m.unit,"gross_demand":round(gross,6),"safety_stock":safety,"physical_stock":m.stock,"reserved":reserved,"open_purchase_order_supply":round(open_po,6),"net_available_supply":round(net_available,6),"reserved_supply_informational":round(reserved,6),"net_requirement":shortage,"demand_orders":order_refs[material_id],"open_purchase_orders":receipts})
    return sorted(output,key=lambda x:x["material_code"])

def schedule_order(db: Session, order_id: str, start_at, username: str) -> dict:
    order=db.get(models.ProductionOrder,order_id)
    if not order: raise HTTPException(404,"Production order not found")
    op_rows=db.query(models.ProductionOrderOperation).filter_by(production_order_id=order.id).order_by(models.ProductionOrderOperation.sequence).all()
    cursor=start_at
    scheduled=[]
    for row in op_rows:
        op=db.get(models.RoutingOperation,row.operation_id)
        wc=db.get(models.Workcenter,row.workcenter_id)
        if not wc or not wc.active or wc.status in {"Under Maintenance","Breakdown"}:
            raise HTTPException(409,f"Workcenter unavailable for operation {row.sequence}")
        if wc.capacity_per_hour<=0:
            raise HTTPException(409,f"Workcenter {wc.code} has no positive capacity rate")
        duration=op.setup_minutes+(op.run_minutes_per_unit*row.planned_qty)
        if duration<=0: duration=max(1,row.planned_qty*60/wc.capacity_per_hour)
        end=cursor+timedelta(minutes=duration)
        overlaps=db.query(models.OperationSchedule).filter(models.OperationSchedule.workcenter_id==wc.id,models.OperationSchedule.status=="scheduled",models.OperationSchedule.planned_start<end,models.OperationSchedule.planned_end>cursor).all()
        if overlaps: raise HTTPException(409,f"Workcenter {wc.code} has overlapping schedule")
        employee_id=row.assigned_employee_id
        if employee_id:
            emp=db.get(models.Employee,employee_id)
            if not emp or not emp.active: raise HTTPException(409,"Assigned employee is inactive")
            if op.required_skill and not db.query(models.EmployeeSkill).filter_by(employee_id=emp.id,skill=op.required_skill,active=True).first():
                raise HTTPException(409,f"Assigned employee lacks required skill: {op.required_skill}")
            employee_overlaps=db.query(models.OperationSchedule).filter(models.OperationSchedule.employee_id==employee_id,models.OperationSchedule.status=="scheduled",models.OperationSchedule.planned_start<end,models.OperationSchedule.planned_end>cursor).all()
            if employee_overlaps: raise HTTPException(409,"Assigned employee has schedule overlap")
        existing=db.query(models.OperationSchedule).filter_by(operation_row_id=row.id).first()
        if existing:
            existing.workcenter_id=wc.id; existing.employee_id=employee_id; existing.planned_start=cursor; existing.planned_end=end; existing.duration_minutes=duration; existing.status="scheduled"; existing.reschedule_reason="Auto-scheduled order"
        else:
            existing=models.OperationSchedule(operation_row_id=row.id,workcenter_id=wc.id,employee_id=employee_id,planned_start=cursor,planned_end=end,duration_minutes=duration,status="scheduled",reschedule_reason="Auto-scheduled order")
            db.add(existing)
        row.status="Scheduled"
        scheduled.append({"operation_row_id":row.id,"sequence":row.sequence,"workcenter_id":wc.id,"employee_id":employee_id,"planned_start":cursor.isoformat(),"planned_end":end.isoformat(),"duration_minutes":round(duration,2)})
        cursor=end
    order.status="Scheduled"
    db.flush()
    return {"order_id":order.id,"order_no":order.order_no,"status":order.status,"operations":scheduled}

def oee_metrics(db: Session) -> dict:
    entries=db.query(models.ProductionEntry).all()
    production=sum(e.quantity for e in entries)
    accepted=sum(e.accepted_qty or 0 for e in entries)
    rejected=sum(e.rejected_qty or 0 for e in entries)
    scrap=sum(e.actual_scrap or 0 for e in entries)
    quality=accepted/production if production else 0
    costs=db.query(models.ProductionCost).all()
    total_cost=sum(c.total_cost for c in costs)
    # OEE components are only available where planned schedule and actual production data exist.
    scheduled_minutes=sum(s.duration_minutes for s in db.query(models.OperationSchedule).filter_by(status="scheduled").all())
    downtime_minutes=sum((d.end_at-d.start_at).total_seconds()/60 for d in db.query(models.MachineDowntime).filter(models.MachineDowntime.end_at.isnot(None)).all())
    availability=max(0,(scheduled_minutes-downtime_minutes)/scheduled_minutes) if scheduled_minutes else None
    return {"production_quantity":production,"accepted_quantity":accepted,"rejected_quantity":rejected,"scrap_quantity":scrap,"quality_ratio":quality,"availability_ratio":availability,"performance_ratio":None,"oee_ratio":None,"total_cost":total_cost,"costed_batches":len(costs),"note":"Performance and OEE are not reported until target cycle-time data and scheduled production time are available."}
