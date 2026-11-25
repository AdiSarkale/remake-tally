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
