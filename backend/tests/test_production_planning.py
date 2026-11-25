"""Unit tests for production planning material calculations."""
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import models
from app.services.production_planning import reserve_order_materials, mrp_net_requirements

def make_db():
    engine=create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()

def seed(db, stock=5, demand=4, bom_qty=2, min_stock=2):
    product=models.Product(code="FG-1",name="Finished",unit="PCS")
    material=models.RawMaterial(code="RM-1",name="Material",unit="KG",stock=stock,min_stock=min_stock,cost=3)
    db.add_all([product,material]);db.flush()
    bom=models.BillOfMaterials(product_id=product.id,version=1,active=True,expected_scrap_percent=0)
    db.add(bom);db.flush()
    db.add(models.BomLine(bom_id=bom.id,material_id=material.id,quantity=bom_qty))
    order=models.ProductionOrder(order_no="PO-TEST",order_date=date.today(),product_id=product.id,quantity=demand,due_date=None,routing_id=None,status="Planned",remarks="")
    db.add(order);db.flush()
    return product,material,order

def test_reservation_does_not_change_physical_stock_and_reports_partial_shortage():
    db=make_db()
    _,material,order=seed(db,stock=5,demand=4,bom_qty=2)
    result=reserve_order_materials(db,order.id)
    db.flush()
    assert material.stock==5
    assert result["physical_stock_unchanged"] is True
    assert result["materials"][0]["required_quantity"]==8
    assert result["materials"][0]["reserved_quantity"]==5
    assert result["materials"][0]["shortage_quantity"]==3
    assert order.status=="Materials Pending"
    db.close()

def test_mrp_net_requirement_includes_safety_stock_without_double_counting_reservation():
    db=make_db()
    _,material,order=seed(db,stock=5,demand=4,bom_qty=2,min_stock=2)
    reserve_order_materials(db,order.id)
    rows=mrp_net_requirements(db)
    row=rows[0]
    assert row["gross_demand"]==8
    assert row["safety_stock"]==2
    assert row["physical_stock"]==5
    assert row["reserved_supply_informational"]==5
    # Demand 8 + safety stock 2 - physical stock 5 = 5.
    assert row["net_requirement"]==5
    db.close()

def test_reservation_fully_covers_demand_and_marks_order_ready():
    db=make_db()
    _,material,order=seed(db,stock=10,demand=4,bom_qty=2)
    result=reserve_order_materials(db,order.id)
    assert result["materials"][0]["reserved_quantity"]==8
    assert result["materials"][0]["shortage_quantity"]==0
    assert order.status=="Ready"
    assert material.stock==10
    db.close()

def test_machine_linked_schedule_is_blocked_by_downtime():
    from datetime import datetime, timezone
    import pytest
    from fastapi import HTTPException
    from app.services.production_planning import schedule_order

    db=make_db()
    product=models.Product(code="FG-M",name="Machine Finished")
    wc=models.Workcenter(code="WC-M",name="Machine Workcenter",capacity_per_hour=100,status="Available",active=True)
    db.add_all([product,wc]);db.flush()
    routing=models.Routing(product_id=product.id,version=1,active=True,name="Route")
    db.add(routing);db.flush()
    operation=models.RoutingOperation(routing_id=routing.id,sequence=1,code="OP1",name="Machine Operation",workcenter_id=wc.id,required_skill="",setup_minutes=0,run_minutes_per_unit=1,active=True)
    db.add(operation);db.flush()
    order=models.ProductionOrder(order_no="PO-MACHINE",order_date=date.today(),product_id=product.id,quantity=5,due_date=None,routing_id=routing.id,status="Ready",remarks="")
    db.add(order);db.flush()
    op_row=models.ProductionOrderOperation(production_order_id=order.id,operation_id=operation.id,sequence=1,workcenter_id=wc.id,assigned_employee_id=None,status="Assigned",planned_qty=5,completed_qty=0)
    machine=models.MachineResource(code="M-1",name="Machine 1",workcenter_id=wc.id,capacity_per_hour=60,hourly_rate=100,status="available",active=True)
    db.add_all([op_row,machine]);db.flush()
    start=datetime(2026,11,25,8,0,tzinfo=timezone.utc)
    scheduled=schedule_order(db,order.id,start,"tester")
    assert scheduled["operations"][0]["machine_id"]==machine.id
    assert db.query(models.OperationSchedule).filter_by(operation_row_id=op_row.id).one().machine_id==machine.id
    db.add(models.MachineDowntime(machine_id=machine.id,start_at=datetime(2026,11,25,8,2,tzinfo=timezone.utc),end_at=datetime(2026,11,25,8,4,tzinfo=timezone.utc),reason_code="BREAK",reason="Test downtime",maintenance=False,created_by="tester"))
    db.flush()
    with pytest.raises(HTTPException) as exc:
        schedule_order(db,order.id,start,"tester")
    assert exc.value.status_code==409
    db.close()

def test_shift_calendar_aligns_scheduling_start_and_rejects_unfittable_operation():
    from datetime import datetime, timezone
    import pytest
    from fastapi import HTTPException
    from app.services.production_planning import align_to_shift
    db=make_db()
    wc=models.Workcenter(code="WC-SHIFT",name="Shift WC",capacity_per_hour=60,status="Available",active=True)
    db.add(wc);db.flush()
    db.add(models.WorkcenterShift(workcenter_id=wc.id,weekday=2,shift_code="A",start_time="09:00",end_time="11:00",active=True))
    db.flush()
    start=datetime(2026,11,25,8,0,tzinfo=timezone.utc) # Wednesday
    aligned,end=align_to_shift(db,wc.id,start,60)
    assert aligned.hour==9 and end.hour==10
    with pytest.raises(HTTPException) as exc:
        align_to_shift(db,wc.id,start,180)
    assert exc.value.status_code==409
    db.close()

def test_wip_receipt_and_consumption_are_ledgered():
    from app.api.routes.production_planning import create_wip, consume_wip, WIPIn, WIPConsumeIn
    db=make_db()
    product=models.Product(code="SF-WIP",name="Semi Finished")
    user=models.User(username="tester",full_name="Test",password_hash="x")
    db.add_all([product,user]);db.flush()
    receipt=create_wip(WIPIn(product_id=product.id,production_order_id=None,quantity=10,unit_cost=12,status="available"),db,user)
    consumed=consume_wip(receipt.id,WIPConsumeIn(quantity=3,reference="OP-2",reason="Next-stage issue"),db,user)
    assert consumed["wip"].quantity==7
    movements=db.query(models.WIPMovement).filter_by(wip_stock_id=receipt.id).order_by(models.WIPMovement.created_at).all()
    assert len(movements)==2
    assert movements[0].movement_type=="receipt" and movements[0].quantity==10
    assert movements[1].movement_type=="consumption" and movements[1].quantity==-3
    assert movements[1].balance_after==7
    db.close()

def test_auto_costing_uses_material_machine_labor_and_overhead_rates():
    from datetime import datetime, timezone
    from app.api.routes.production_planning import auto_cost
    db=make_db()
    product=models.Product(code="FG-COST",name="Costed")
    material=models.RawMaterial(code="RM-COST",name="Cost material",unit="KG",stock=20,min_stock=0,cost=4)
    wc=models.Workcenter(code="WC-COST",name="Cost WC",capacity_per_hour=60,labor_hourly_rate=50,overhead_hourly_rate=20,status="Available",active=True)
    user=models.User(username="tester",full_name="Test",password_hash="x")
    db.add_all([product,material,wc,user]);db.flush()
    routing=models.Routing(product_id=product.id,version=1,active=True,name="Cost route")
    db.add(routing);db.flush()
    operation=models.RoutingOperation(routing_id=routing.id,sequence=1,code="OP-C",name="Cost operation",workcenter_id=wc.id,required_skill="",setup_minutes=0,run_minutes_per_unit=1,active=True)
    db.add(operation);db.flush()
    order=models.ProductionOrder(order_no="PO-COST",order_date=date.today(),product_id=product.id,quantity=10,due_date=None,routing_id=routing.id,status="In Progress",remarks="")
    db.add(order);db.flush()
    op_row=models.ProductionOrderOperation(production_order_id=order.id,operation_id=operation.id,sequence=1,workcenter_id=wc.id,assigned_employee_id=None,status="In Progress",planned_qty=10,completed_qty=10)
    machine=models.MachineResource(code="M-COST",name="Cost machine",workcenter_id=wc.id,capacity_per_hour=60,hourly_rate=120,status="available",active=True)
    db.add_all([op_row,machine]);db.flush()
    schedule=models.OperationSchedule(operation_row_id=op_row.id,workcenter_id=wc.id,machine_id=machine.id,employee_id=None,planned_start=datetime(2026,11,25,9,tzinfo=timezone.utc),planned_end=datetime(2026,11,25,10,tzinfo=timezone.utc),duration_minutes=60,status="completed",reschedule_reason="")
    entry=models.ProductionEntry(batch_no="B-COST",entry_date=date.today(),product_id=product.id,quantity=10,machine=machine.code,workcenter_id=wc.id,routing_id=routing.id,operation_id=operation.id,production_order_id=order.id,employee_id=None,operator="Test",shift="A",remarks="",actual_scrap=0,quality_status="Accepted",accepted_qty=8,rejected_qty=2,quality_remarks="")
    db.add_all([schedule,entry]);db.flush()
    db.add(models.ProductionConsumption(production_id=entry.id,material_id=material.id,planned_quantity=5,quantity=5));db.flush()
    result=auto_cost(entry.id,db,user)
    cost=result["cost_record"]
    assert cost.material_cost==20
    assert cost.machine_cost==120
    assert cost.labor_cost==50
    assert cost.overhead_cost==20
    assert cost.total_cost==210
    assert cost.unit_cost==26.25
    from app.api.routes.manufacturing import update_production_quality
    from app import schemas
    updated=update_production_quality(entry.id,schemas.ProductionQualityIn(status="Accepted",accepted_qty=4,rejected_qty=6,remarks="re-inspected"),db,user)
    recalc=db.query(models.ProductionCost).filter_by(production_entry_id=entry.id).one()
    assert updated.accepted_qty==4
    assert recalc.unit_cost==52.5
    db.close()

def test_overnight_shift_covers_early_morning_after_midnight():
    from datetime import datetime, timezone
    from app.services.production_planning import align_to_shift
    db=make_db()
    wc=models.Workcenter(code="WC-NIGHT",name="Night shift WC",capacity_per_hour=60,status="Available",active=True)
    db.add(wc);db.flush()
    db.add(models.WorkcenterShift(workcenter_id=wc.id,weekday=2,shift_code="N",start_time="22:00",end_time="06:00",active=True))
    db.flush()
    start=datetime(2026,11,26,2,0,tzinfo=timezone.utc) # Thursday, within Wednesday overnight shift
    aligned,end=align_to_shift(db,wc.id,start,60)
    assert aligned==start and end.hour==3
    db.close()
