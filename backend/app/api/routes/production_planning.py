"""Backend-only production planning and advanced manufacturing APIs; Smart PR generation is intentionally excluded."""
from datetime import date, datetime
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app import models
from app.api.deps import require_area
from app.db.session import get_db
from app.modules.core.audit import log_audit
from app.services.production_planning import material_requirements, reserve_order_materials, mrp_net_requirements, schedule_order, select_machine_and_duration, oee_metrics

router=APIRouter(prefix="/manufacturing/planning",tags=["production-planning"])
guard=Depends(require_area("production"))

class OrderStatusIn(BaseModel):
    status: str=Field(pattern="^(Planned|Materials Pending|Ready|Scheduled|In Progress|Completed|Cancelled)$")
class ScheduleOrderIn(BaseModel):
    start_at: datetime
class RescheduleIn(BaseModel):
    planned_start: datetime
    planned_end: datetime
    employee_id: str | None=None
    machine_id: str | None=None
    reason: str=Field(default="",max_length=500)
class MachineIn(BaseModel):
    code: str=Field(min_length=1,max_length=32)
    name: str=Field(min_length=1,max_length=120)
    workcenter_id: str
    capacity_per_hour: float=Field(ge=0)
    hourly_rate: float=Field(ge=0)
    status: str=Field(default="available",pattern="^(available|down|maintenance|disabled)$")
    active: bool=True
    maintenance_due: date | None=None
class DowntimeIn(BaseModel):
    machine_id: str
    start_at: datetime
    end_at: datetime | None=None
class DowntimeEndIn(BaseModel):
    end_at: datetime
    reason_code: str=""
    reason: str=""
    maintenance: bool=False
class CostIn(BaseModel):
    material_cost: float=Field(ge=0)
    labor_cost: float=Field(ge=0)
    machine_cost: float=Field(ge=0)
    overhead_cost: float=Field(ge=0)
    accepted_quantity: float=Field(ge=0)
    currency: str=Field(default="INR",min_length=3,max_length=3)
    notes: str=""
class WIPIn(BaseModel):
    product_id: str
    production_order_id: str | None=None
    quantity: float=Field(ge=0)
    unit_cost: float=Field(ge=0)
    status: str=Field(default="available",pattern="^(available|reserved|quality_hold|consumed)$")


@router.patch("/orders/{order_id}/status")
def update_order_status(order_id:str,payload:OrderStatusIn,db:Session=Depends(get_db),user:models.User=guard):
    order=db.get(models.ProductionOrder,order_id)
    if not order: raise HTTPException(404,"Production order not found")
    current=order.status; target=payload.status
    allowed={
      "Planned":{"Materials Pending","Ready","Cancelled"},
      "Materials Pending":{"Ready","Cancelled"},
      "Ready":{"Scheduled","In Progress","Cancelled"},
      "Scheduled":{"In Progress","Cancelled"},
      "In Progress":{"Completed"},
      "Completed":set(),"Cancelled":set()
    }
    if target==current: return {"order_id":order.id,"status":order.status}
    if target not in allowed.get(current,set()): raise HTTPException(409,f"Invalid production-order status transition {current} -> {target}")
    if target=="Ready":
        rows=material_requirements(db,order.id)
        reservations=db.query(models.MaterialReservation).filter_by(production_order_id=order.id,status="active").all()
        totals={}
        for r in reservations: totals[r.material_id]=totals.get(r.material_id,0)+r.reserved_quantity
        missing=[m["material_name"] for m in rows if totals.get(m["material_id"],0)<m["required_quantity"]]
        if missing: raise HTTPException(409,"Materials not fully reserved: "+", ".join(missing))
    if target=="Completed":
        operations=db.query(models.ProductionOrderOperation).filter_by(production_order_id=order.id).all()
        if not operations or any(x.completed_qty<x.planned_qty for x in operations): raise HTTPException(409,"All production operations must be completed before closing the order")
    if target=="Cancelled":
        db.query(models.MaterialReservation).filter_by(production_order_id=order.id,status="active").update({"status":"released"},synchronize_session=False)
        db.query(models.OperationSchedule).filter(models.OperationSchedule.operation_row_id.in_([x.id for x in db.query(models.ProductionOrderOperation).filter_by(production_order_id=order.id).all()])).update({"status":"cancelled"},synchronize_session=False)
    order.status=target
    log_audit(db,user.username,"STATUS","production_order",f"{order.order_no}: {current} -> {target}")
    db.commit()
    return {"order_id":order.id,"order_no":order.order_no,"status":order.status}

@router.get("/orders/{order_id}/requirements")
def order_requirements(order_id:str,db:Session=Depends(get_db),user:models.User=guard):
    return {"production_order_id":order_id,"materials":material_requirements(db,order_id)}

@router.post("/orders/{order_id}/reservations")
def reserve_materials(order_id:str,db:Session=Depends(get_db),user:models.User=guard):
    result=reserve_order_materials(db,order_id)
    log_audit(db,user.username,"RESERVE","production_materials",order_id)
    db.commit()
    return result

@router.get("/mrp/net-requirements")
def net_requirements(db:Session=Depends(get_db),user:models.User=guard):
    return {"items":mrp_net_requirements(db),"smart_pr_generation":"excluded_by_request"}

@router.post("/orders/{order_id}/schedule")
def auto_schedule_order(order_id:str,payload:ScheduleOrderIn,db:Session=Depends(get_db),user:models.User=guard):
    result=schedule_order(db,order_id,payload.start_at,user.username)
    log_audit(db,user.username,"SCHEDULE","production_order",order_id)
    db.commit()
    return result

@router.patch("/operations/{operation_row_id}/reschedule")
def reschedule_operation(operation_row_id:str,payload:RescheduleIn,db:Session=Depends(get_db),user:models.User=guard):
    if payload.planned_end<=payload.planned_start: raise HTTPException(400,"Planned end must be after planned start")
    row=db.get(models.ProductionOrderOperation,operation_row_id)
    if not row: raise HTTPException(404,"Production operation not found")
    previous=db.query(models.ProductionOrderOperation).filter(models.ProductionOrderOperation.production_order_id==row.production_order_id,models.ProductionOrderOperation.sequence<row.sequence).order_by(models.ProductionOrderOperation.sequence.desc()).first()
    following=db.query(models.ProductionOrderOperation).filter(models.ProductionOrderOperation.production_order_id==row.production_order_id,models.ProductionOrderOperation.sequence>row.sequence).order_by(models.ProductionOrderOperation.sequence.asc()).first()
    prev_sched=db.query(models.OperationSchedule).filter_by(operation_row_id=previous.id,status="scheduled").first() if previous else None
    next_sched=db.query(models.OperationSchedule).filter_by(operation_row_id=following.id,status="scheduled").first() if following else None
    if prev_sched and payload.planned_start<prev_sched.planned_end: raise HTTPException(409,"Reschedule violates routing sequence: previous operation is not complete in schedule")
    if next_sched and payload.planned_end>next_sched.planned_start: raise HTTPException(409,"Reschedule violates routing sequence: next operation starts before this operation ends")
    wc=db.get(models.Workcenter,row.workcenter_id)
    if not wc or not wc.active or wc.status in {"Under Maintenance","Breakdown"}: raise HTTPException(409,"Workcenter unavailable")
    operation=db.get(models.RoutingOperation,row.operation_id)
    machine,required_duration=select_machine_and_duration(db,wc,row,operation,payload.planned_start,payload.machine_id)
    requested_duration=(payload.planned_end-payload.planned_start).total_seconds()/60
    if requested_duration+0.001<required_duration: raise HTTPException(409,f"Scheduled duration is shorter than capacity requirement ({required_duration:.2f} minutes)")
    if machine:
        downtime=db.query(models.MachineDowntime).filter(models.MachineDowntime.machine_id==machine.id,models.MachineDowntime.start_at<payload.planned_end,((models.MachineDowntime.end_at.is_(None))|(models.MachineDowntime.end_at>payload.planned_start))).first()
        if downtime: raise HTTPException(409,"Machine downtime overlaps requested schedule")
        machine_overlap=db.query(models.OperationSchedule).filter(models.OperationSchedule.machine_id==machine.id,models.OperationSchedule.operation_row_id!=row.id,models.OperationSchedule.status.in_({"scheduled","reschedule_required","completed"}),models.OperationSchedule.planned_start<payload.planned_end,models.OperationSchedule.planned_end>payload.planned_start).first()
        if machine_overlap: raise HTTPException(409,"Machine schedule overlap")
    overlaps=db.query(models.OperationSchedule).filter(models.OperationSchedule.workcenter_id==wc.id,models.OperationSchedule.operation_row_id!=row.id,models.OperationSchedule.status.in_({"scheduled","reschedule_required"}),models.OperationSchedule.planned_start<payload.planned_end,models.OperationSchedule.planned_end>payload.planned_start).all()
    if overlaps: raise HTTPException(409,"Workcenter schedule overlap")
    emp_id=payload.employee_id if payload.employee_id is not None else row.assigned_employee_id
    if emp_id:
        emp=db.get(models.Employee,emp_id)
        if not emp or not emp.active: raise HTTPException(400,"Employee inactive or missing")
        if operation.required_skill and not db.query(models.EmployeeSkill).filter_by(employee_id=emp.id,skill=operation.required_skill,active=True).first(): raise HTTPException(400,"Employee lacks required skill")
        emp_overlap=db.query(models.OperationSchedule).filter(models.OperationSchedule.employee_id==emp_id,models.OperationSchedule.operation_row_id!=row.id,models.OperationSchedule.status.in_({"scheduled","reschedule_required"}),models.OperationSchedule.planned_start<payload.planned_end,models.OperationSchedule.planned_end>payload.planned_start).first()
        if emp_overlap: raise HTTPException(409,"Employee schedule overlap")
    sched=db.query(models.OperationSchedule).filter_by(operation_row_id=row.id).first()
    if not sched:
        sched=models.OperationSchedule(operation_row_id=row.id,workcenter_id=wc.id,machine_id=machine.id if machine else None,employee_id=emp_id,planned_start=payload.planned_start,planned_end=payload.planned_end,duration_minutes=requested_duration,status="scheduled",reschedule_reason=payload.reason)
        db.add(sched)
    else:
        sched.machine_id=machine.id if machine else None
        sched.employee_id=emp_id
        sched.planned_start=payload.planned_start
        sched.planned_end=payload.planned_end
        sched.duration_minutes=requested_duration
        sched.status="scheduled"
        sched.reschedule_reason=payload.reason
    row.status="Scheduled"
    parent_order=db.get(models.ProductionOrder,row.production_order_id)
    if parent_order and parent_order.status in {"Ready","Materials Pending"}: parent_order.status="Scheduled"
    log_audit(db,user.username,"RESCHEDULE","production_operation",operation_row_id)
    db.commit()
    return {"operation_row_id":row.id,"planned_start":payload.planned_start,"planned_end":payload.planned_end,"duration_minutes":sched.duration_minutes,"machine_id":machine.id if machine else None,"employee_id":emp_id}

@router.get("/machines")
def list_machines(db:Session=Depends(get_db),user:models.User=guard):
    return db.query(models.MachineResource).order_by(models.MachineResource.code).all()

@router.post("/machines",status_code=201)
def create_machine(payload:MachineIn,db:Session=Depends(get_db),user:models.User=guard):
    if db.query(models.MachineResource).filter_by(code=payload.code).first(): raise HTTPException(409,"Machine code exists")
    if not db.get(models.Workcenter,payload.workcenter_id): raise HTTPException(404,"Workcenter not found")
    data=payload.model_dump()
    data.pop("maintenance_due",None)
    machine=models.MachineResource(**data,maintenance_due=payload.maintenance_due)
    db.add(machine);log_audit(db,user.username,"CREATE","machine",payload.code);db.commit();db.refresh(machine);return machine

@router.patch("/machines/{machine_id}")
def update_machine(machine_id:str,payload:MachineIn,db:Session=Depends(get_db),user:models.User=guard):
    machine=db.get(models.MachineResource,machine_id)
    if not machine: raise HTTPException(404,"Machine not found")
    if machine.code!=payload.code and db.query(models.MachineResource).filter_by(code=payload.code).first(): raise HTTPException(409,"Machine code exists")
    if not db.get(models.Workcenter,payload.workcenter_id): raise HTTPException(404,"Workcenter not found")
    for k in ("code","name","workcenter_id","capacity_per_hour","hourly_rate","status","active"): setattr(machine,k,getattr(payload,k))
    machine.maintenance_due=payload.maintenance_due
    log_audit(db,user.username,"UPDATE","machine",machine.code);db.commit();return machine

@router.get("/downtime")
def list_downtime(db:Session=Depends(get_db),user:models.User=guard):
    return db.query(models.MachineDowntime).order_by(models.MachineDowntime.start_at.desc()).all()

@router.patch("/downtime/{downtime_id}/close")
def close_downtime(downtime_id:str,payload:DowntimeEndIn,db:Session=Depends(get_db),user:models.User=guard):
    row=db.get(models.MachineDowntime,downtime_id)
    if not row: raise HTTPException(404,"Downtime record not found")
    if row.end_at is not None: raise HTTPException(409,"Downtime record is already closed")
    if payload.end_at<=row.start_at: raise HTTPException(400,"Downtime end must be after start")
    row.end_at=payload.end_at
    machine=db.get(models.MachineResource,row.machine_id)
    open_rows=db.query(models.MachineDowntime).filter(models.MachineDowntime.machine_id==machine.id,models.MachineDowntime.id!=row.id,models.MachineDowntime.end_at.is_(None)).all()
    if machine and machine.active:
        machine.status="maintenance" if any(x.maintenance for x in open_rows) else ("down" if open_rows else "available")
    log_audit(db,user.username,"DOWNTIME_END","machine",machine.code if machine else row.machine_id)
    db.commit();db.refresh(row);return row

@router.post("/downtime",status_code=201)
def create_downtime(payload:DowntimeIn,db:Session=Depends(get_db),user:models.User=guard):
    if payload.end_at and payload.end_at<=payload.start_at: raise HTTPException(400,"Downtime end must be after start")
    machine=db.get(models.MachineResource,payload.machine_id)
    if not machine: raise HTTPException(404,"Machine not found")
    row=models.MachineDowntime(**payload.model_dump(),created_by=user.username)
    db.add(row)
    affected_query=db.query(models.OperationSchedule).filter(models.OperationSchedule.machine_id==machine.id,models.OperationSchedule.status.in_({"scheduled","completed"}),models.OperationSchedule.planned_end>payload.start_at)
    if payload.end_at:
        affected_query=affected_query.filter(models.OperationSchedule.planned_start<payload.end_at)
    affected=affected_query.all()
    for schedule in affected:
        schedule.status="reschedule_required"
    machine.status="maintenance" if payload.maintenance and payload.end_at is None else ("down" if payload.end_at is None else machine.status)
    log_audit(db,user.username,"DOWNTIME","machine",machine.code+":"+payload.reason_code)
    db.commit();db.refresh(row)
    return {"downtime":row,"affected_operation_schedules":[x.id for x in affected],"reschedule_required":len(affected)}

@router.post("/costs/{production_entry_id}")
def record_cost(production_entry_id:str,payload:CostIn,db:Session=Depends(get_db),user:models.User=guard):
    entry=db.get(models.ProductionEntry,production_entry_id)
    if not entry: raise HTTPException(404,"Production entry not found")
    total=round(payload.material_cost+payload.labor_cost+payload.machine_cost+payload.overhead_cost,4)
    unit=round(total/payload.accepted_quantity,4) if payload.accepted_quantity else 0
    row=db.query(models.ProductionCost).filter_by(production_entry_id=entry.id).first()
    data=payload.model_dump();data.update(total_cost=total,unit_cost=unit)
    if row:
        for k,v in data.items():setattr(row,k,v)
    else:
        row=models.ProductionCost(production_entry_id=entry.id,**data);db.add(row)
    log_audit(db,user.username,"COST","production_entry",entry.batch_no)
    db.commit();db.refresh(row);return row

@router.get("/costs")
def list_costs(db:Session=Depends(get_db),user:models.User=guard):
    return db.query(models.ProductionCost).all()

@router.get("/wip")
def list_wip(db:Session=Depends(get_db),user:models.User=guard):
    return db.query(models.WIPStock).order_by(models.WIPStock.updated_at.desc()).all()

@router.post("/wip",status_code=201)
def create_wip(payload:WIPIn,db:Session=Depends(get_db),user:models.User=guard):
    if not db.get(models.Product,payload.product_id): raise HTTPException(404,"Product/SF master not found")
    if payload.production_order_id and not db.get(models.ProductionOrder,payload.production_order_id): raise HTTPException(404,"Production order not found")
    existing=db.query(models.WIPStock).filter_by(product_id=payload.product_id,production_order_id=payload.production_order_id).first()
    if existing:
        existing.quantity+=payload.quantity;existing.unit_cost=payload.unit_cost;existing.status=payload.status;row=existing
    else:
        row=models.WIPStock(**payload.model_dump());db.add(row)
    log_audit(db,user.username,"WIP_RECEIPT","wip",payload.product_id)
    db.commit();db.refresh(row);return row

@router.patch("/wip/{wip_id}")
def adjust_wip(wip_id:str,quantity:float=Query(ge=0),status:str="available",db:Session=Depends(get_db),user:models.User=guard):
    row=db.get(models.WIPStock,wip_id)
    if not row: raise HTTPException(404,"WIP record not found")
    row.quantity=quantity;row.status=status
    log_audit(db,user.username,"WIP_ADJUST","wip",wip_id);db.commit();return row

@router.get("/analytics")
def analytics(db:Session=Depends(get_db),user:models.User=guard):
    return oee_metrics(db)
