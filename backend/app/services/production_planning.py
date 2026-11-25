"""Production planning calculations. Reservations are planning records, not stock movements."""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, time, timedelta
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
    # Lock material rows in stable order so concurrent orders cannot over-reserve.
    for item in sorted(requirements,key=lambda x:x["material_id"]):
        db.query(models.RawMaterial).filter_by(id=item["material_id"]).with_for_update().one()
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
        net_available=max(0,m.stock)+open_po
        safety=m.min_stock or 0
        shortage=max(0,round(gross+safety-net_available,6))
        output.append({"material_id":m.id,"material_code":m.code,"material_name":m.name,"unit":m.unit,"gross_demand":round(gross,6),"safety_stock":safety,"physical_stock":m.stock,"reserved":reserved,"open_purchase_order_supply":round(open_po,6),"net_available_supply":round(net_available,6),"reserved_supply_informational":round(reserved,6),"net_requirement":shortage,"demand_orders":order_refs[material_id],"open_purchase_orders":receipts})
    return sorted(output,key=lambda x:x["material_code"])


def shift_windows_for_date(db: Session, workcenter_id: str, day: date, tzinfo):
    rows=db.query(models.WorkcenterShift).filter_by(workcenter_id=workcenter_id,weekday=day.weekday(),active=True).order_by(models.WorkcenterShift.start_time).all()
    windows=[]
    for row in rows:
        start_time=time.fromisoformat(row.start_time)
        end_time=time.fromisoformat(row.end_time)
        start=datetime.combine(day,start_time,tzinfo=tzinfo)
        end=datetime.combine(day,end_time,tzinfo=tzinfo)
        if end<=start: end+=timedelta(days=1)
        windows.append((start,end,row))
    return windows

def align_to_shift(db: Session, workcenter_id: str, start_at: datetime, duration_minutes: float) -> tuple[datetime,datetime]:
    configured=db.query(models.WorkcenterShift).filter_by(workcenter_id=workcenter_id,active=True).count()
    if configured==0:
        return start_at,start_at+timedelta(minutes=duration_minutes)
    day=start_at.date()
    for offset in range(0,31):
        current_day=day+timedelta(days=offset)
        for shift_start,shift_end,row in shift_windows_for_date(db,workcenter_id,current_day,start_at.tzinfo):
            candidate=max(start_at,shift_start)
            end=candidate+timedelta(minutes=duration_minutes)
            if candidate<shift_end and end<=shift_end:
                return candidate,end
    raise HTTPException(409,"No configured workcenter shift can fit this operation within the next 30 days")

def validate_shift_window(db: Session, workcenter_id: str, start_at: datetime, end_at: datetime) -> bool:
    configured=db.query(models.WorkcenterShift).filter_by(workcenter_id=workcenter_id,active=True).count()
    if configured==0: return True
    return any(start_at>=a and end_at<=b for a,b,_ in shift_windows_for_date(db,workcenter_id,start_at.date(),start_at.tzinfo))

def select_machine_and_duration(db: Session, wc: models.Workcenter, row: models.ProductionOrderOperation, op: models.RoutingOperation, start_at, requested_machine_id: str | None = None) -> tuple[models.MachineResource | None,float]:
    machines=db.query(models.MachineResource).filter_by(workcenter_id=wc.id,active=True).order_by(models.MachineResource.code).all()
    base_duration=op.setup_minutes+(op.run_minutes_per_unit*row.planned_qty)
    if not machines:
        if requested_machine_id: raise HTTPException(409,"No machine resources are registered for this workcenter")
        return None,max(base_duration,op.setup_minutes+(row.planned_qty*60/wc.capacity_per_hour))
    if requested_machine_id:
        machines=[m for m in machines if m.id==requested_machine_id]
        if not machines: raise HTTPException(400,"Requested machine is not active for this workcenter")
    for machine in machines:
        if str(machine.status).lower() not in {"available"}: continue
        capacity=machine.capacity_per_hour or wc.capacity_per_hour
        duration=max(base_duration,op.setup_minutes+(row.planned_qty*60/capacity)) if capacity>0 else base_duration
        end_at=start_at+timedelta(minutes=duration)
        downtime=db.query(models.MachineDowntime).filter(models.MachineDowntime.machine_id==machine.id,models.MachineDowntime.start_at<end_at,((models.MachineDowntime.end_at.is_(None))|(models.MachineDowntime.end_at>start_at))).first()
        if downtime: continue
        conflicts=db.query(models.OperationSchedule).filter(models.OperationSchedule.machine_id==machine.id,models.OperationSchedule.operation_row_id!=row.id,models.OperationSchedule.status.in_({"scheduled","reschedule_required","completed"}),models.OperationSchedule.planned_start<end_at,models.OperationSchedule.planned_end>start_at).first()
        if conflicts: continue
        return machine,duration
    raise HTTPException(409,"No available machine has capacity for the requested schedule window")

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
        base_duration=op.setup_minutes+(op.run_minutes_per_unit*row.planned_qty)
        cursor,_=align_to_shift(db,wc.id,cursor,base_duration)
        machine,duration=select_machine_and_duration(db,wc,row,op,cursor)
        aligned_start,end=align_to_shift(db,wc.id,cursor,duration)
        if aligned_start!=cursor:
            cursor=aligned_start
            machine,duration=select_machine_and_duration(db,wc,row,op,cursor)
            cursor,end=align_to_shift(db,wc.id,cursor,duration)
        overlaps=db.query(models.OperationSchedule).filter(models.OperationSchedule.workcenter_id==wc.id,models.OperationSchedule.status.in_({"scheduled","reschedule_required","completed"}),models.OperationSchedule.operation_row_id!=row.id,models.OperationSchedule.planned_start<end,models.OperationSchedule.planned_end>cursor).all()
        if overlaps: raise HTTPException(409,f"Workcenter {wc.code} has overlapping schedule")
        employee_id=row.assigned_employee_id
        if employee_id:
            emp=db.get(models.Employee,employee_id)
            if not emp or not emp.active: raise HTTPException(409,"Assigned employee is inactive")
            if op.required_skill and not db.query(models.EmployeeSkill).filter_by(employee_id=emp.id,skill=op.required_skill,active=True).first():
                raise HTTPException(409,f"Assigned employee lacks required skill: {op.required_skill}")
            employee_overlaps=db.query(models.OperationSchedule).filter(models.OperationSchedule.employee_id==employee_id,models.OperationSchedule.status.in_({"scheduled","reschedule_required"}),models.OperationSchedule.operation_row_id!=row.id,models.OperationSchedule.planned_start<end,models.OperationSchedule.planned_end>cursor).all()
            if employee_overlaps: raise HTTPException(409,"Assigned employee has schedule overlap")
        existing=db.query(models.OperationSchedule).filter_by(operation_row_id=row.id).first()
        if existing:
            existing.workcenter_id=wc.id; existing.machine_id=machine.id if machine else None; existing.employee_id=employee_id; existing.planned_start=cursor; existing.planned_end=end; existing.duration_minutes=duration; existing.status="scheduled"; existing.reschedule_reason="Auto-scheduled order"
        else:
            existing=models.OperationSchedule(operation_row_id=row.id,workcenter_id=wc.id,machine_id=machine.id if machine else None,employee_id=employee_id,planned_start=cursor,planned_end=end,duration_minutes=duration,status="scheduled",reschedule_reason="Auto-scheduled order")
            db.add(existing)
        row.status="Scheduled"
        scheduled.append({"operation_row_id":row.id,"sequence":row.sequence,"workcenter_id":wc.id,"machine_id":machine.id if machine else None,"employee_id":employee_id,"planned_start":cursor.isoformat(),"planned_end":end.isoformat(),"duration_minutes":round(duration,2)})
        cursor=end
    order.status="Scheduled"
    db.flush()
    return {"order_id":order.id,"order_no":order.order_no,"status":order.status,"operations":scheduled}

def oee_metrics(db: Session) -> dict:
    entries=db.query(models.ProductionEntry).all()
    produced=sum(e.quantity for e in entries)
    accepted=sum(e.accepted_qty or 0 for e in entries)
    rejected=sum(e.rejected_qty or 0 for e in entries)
    scrap=sum(e.actual_scrap or 0 for e in entries)
    costs=db.query(models.ProductionCost).all()
    total_cost=sum(c.total_cost for c in costs)
    order_rows=[]
    orders=db.query(models.ProductionOrder).all()
    for order in orders:
        operations=db.query(models.ProductionOrderOperation).filter_by(production_order_id=order.id).order_by(models.ProductionOrderOperation.sequence).all()
        order_rows.append({"order_id":order.id,"order_no":order.order_no,"status":order.status,"planned_qty":order.quantity,"completed_qty":sum(o.completed_qty for o in operations)/len(operations) if operations else 0,"operations":[{"sequence":o.sequence,"planned_qty":o.planned_qty,"completed_qty":o.completed_qty,"status":o.status} for o in operations]})
    wc_rows=[]
    schedules=db.query(models.OperationSchedule).filter(models.OperationSchedule.status.in_({"scheduled","completed"})).all()
    for wc in db.query(models.Workcenter).all():
        wc_schedules=[s for s in schedules if s.workcenter_id==wc.id]
        planned_qty=sum(db.get(models.ProductionOrderOperation,s.operation_row_id).planned_qty for s in wc_schedules if db.get(models.ProductionOrderOperation,s.operation_row_id))
        hours=sum(s.duration_minutes for s in wc_schedules)/60
        cap=wc.capacity_per_hour
        load_ratio=(planned_qty/(cap*hours)) if cap>0 and hours>0 else None
        actual=sum(e.quantity for e in entries if e.workcenter_id==wc.id)
        wc_rows.append({"workcenter_id":wc.id,"code":wc.code,"name":wc.name,"scheduled_hours":round(hours,2),"scheduled_operation_count":len(wc_schedules),"planned_qty":planned_qty,"capacity_load_ratio":load_ratio,"actual_qty":actual})
    employees={}
    for e in entries:
        if e.employee_id:
            item=employees.setdefault(e.employee_id,{"employee_id":e.employee_id,"produced_qty":0,"production_entries":0})
            item["produced_qty"]+=e.quantity;item["production_entries"]+=1
    material_planned=sum(c.planned_quantity for e in entries for c in e.consumption)
    material_actual=sum(c.quantity for e in entries for c in e.consumption)
    machine_schedules=[s for s in schedules if s.machine_id]
    scheduled_machine_minutes=sum(s.duration_minutes for s in machine_schedules)
    downtime_overlap=0.0
    for schedule in machine_schedules:
        records=db.query(models.MachineDowntime).filter(models.MachineDowntime.machine_id==schedule.machine_id,models.MachineDowntime.start_at<schedule.planned_end,((models.MachineDowntime.end_at.is_(None))|(models.MachineDowntime.end_at>schedule.planned_start))).all()
        for record in records:
            overlap_start=max(schedule.planned_start,record.start_at)
            overlap_end=min(schedule.planned_end,record.end_at or schedule.planned_end)
            downtime_overlap+=max(0,(overlap_end-overlap_start).total_seconds()/60)
    availability=max(0,1-downtime_overlap/scheduled_machine_minutes) if scheduled_machine_minutes else None
    return {
      "production_quantity":produced,"accepted_quantity":accepted,"rejected_quantity":rejected,"scrap_quantity":scrap,
      "yield_ratio":accepted/produced if produced else None,"rejection_ratio":rejected/produced if produced else None,
      "scrap_ratio":scrap/produced if produced else None,
      "plan_vs_actual_by_order":order_rows,"workcenter_capacity_load":wc_rows,"employee_productivity":list(employees.values()),
      "planned_material_quantity":material_planned,"actual_material_quantity":material_actual,"material_variance":round(material_actual-material_planned,6),
      "total_cost":total_cost,"costed_batches":len(costs),"availability_ratio":availability,"performance_ratio":None,"oee_ratio":None,
      "note":"Machine-linked scheduled availability is calculated where schedules and downtime records exist. Performance and full OEE are not reported until target cycle-time data is available."
    }
