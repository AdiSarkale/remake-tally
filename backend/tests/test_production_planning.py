"""Production roadmap backend regression tests."""
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.services.production_planning import plan_materials, calculate_mrp, schedule_order, save_cost


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'production.db'}")
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def seed_order(db, suffix="A", quantity=10, stock=15):
    product = models.Product(id=f"fg-{suffix}", code=f"FG-{suffix}", name=f"Finished {suffix}", stock=0)
    material = models.RawMaterial(id=f"rm-{suffix}", code=f"RM-{suffix}", name=f"Material {suffix}", stock=stock, min_stock=0, cost=3)
    bom = models.BillOfMaterials(id=f"bom-{suffix}", product_id=product.id, version=1, active=True)
    bom.lines.append(models.BomLine(material_id=material.id, quantity=2))
    wc = models.Workcenter(id=f"wc-{suffix}", code=f"WC-{suffix}", name=f"Work centre {suffix}", capacity_per_hour=60, active=True, status="Available")
    routing = models.Routing(id=f"routing-{suffix}", product_id=product.id, version=1, active=True, name="Route")
    operation = models.RoutingOperation(id=f"op-{suffix}", routing_id=routing.id, sequence=10, code="OP10", name="Operation 10", workcenter_id=wc.id, required_skill="assembly", setup_minutes=5, run_minutes_per_unit=2, active=True)
    order = models.ProductionOrder(id=f"order-{suffix}", order_no=f"PO-{suffix}", order_date=datetime(2026, 1, 1).date(), product_id=product.id, quantity=quantity, routing_id=routing.id, status="Planned")
    order_op = models.ProductionOrderOperation(id=f"row-{suffix}", production_order_id=order.id, operation_id=operation.id, sequence=10, workcenter_id=wc.id, status="Pending", planned_qty=quantity, completed_qty=0)
    employee = models.Employee(id=f"emp-{suffix}", emp_code=f"E-{suffix}", name="Operator", employee_type="shop_floor", active=True)
    skill = models.EmployeeSkill(id=f"skill-{suffix}", employee_id=employee.id, skill="assembly", level=2, active=True)
    db.add_all([product, material, bom, wc, routing, operation, order, order_op, employee, skill])
    db.commit()
    return order, material, wc, operation, employee


def test_material_reservation_is_logical_and_shows_shortage(db):
    order, material, *_ = seed_order(db, stock=15, quantity=10)
    rows = plan_materials(db, order)
    assert rows[0]["required_quantity"] == 20
    assert rows[0]["reserved_quantity"] == 15
    assert rows[0]["shortage_quantity"] == 5
    assert order.planning_status == "materials_short"
    assert material.stock == 15
    db.commit()


def test_reservations_protect_stock_from_other_orders(db):
    first, material, *_ = seed_order(db, suffix="A", stock=10, quantity=5)
    second, *_ = seed_order(db, suffix="B", stock=10, quantity=5)
    old_bom = db.query(models.BillOfMaterials).filter_by(product_id=second.product_id).first()
    db.delete(old_bom)
    db.flush()
    replacement = models.BillOfMaterials(id="bom-B-shared", product_id=second.product_id, version=2, active=True)
    replacement.lines.append(models.BomLine(material_id=material.id, quantity=2))
    db.add(replacement)
    db.commit()
    first_result = plan_materials(db, first)
    db.commit()
    second_result = plan_materials(db, second)
    assert first_result[0]["reserved_quantity"] == 10
    assert second_result[0]["reserved_quantity"] == 0
    assert second_result[0]["shortage_quantity"] == 10
    assert material.stock == 10


def test_mrp_nets_gross_demand_against_physical_stock(db):
    order, material, *_ = seed_order(db, stock=15, quantity=10)
    plan_materials(db, order)
    db.commit()
    result = calculate_mrp(db)[0]
    assert result["gross_demand"] == 20
    assert result["reserved"] == 15
    assert result["net_requirement"] == 5
    assert result["demand_orders"] == [order.order_no]


def test_schedule_respects_machine_downtime_and_employee_skill(db):
    order, _, wc, _, employee = seed_order(db, stock=30, quantity=5)
    machine = models.MachineResource(id="machine-A", code="M-A", name="Machine A", workcenter_id=wc.id, capacity_per_hour=60, hourly_rate=50, active=True, status="available")
    downtime = models.MachineDowntime(id="down-A", machine_id=machine.id, workcenter_id=wc.id, start_at=datetime(2026, 1, 2, 8), end_at=datetime(2026, 1, 2, 8, 30), reason="Maintenance")
    db.add_all([machine, downtime])
    db.commit()
    plan_materials(db, order)
    db.commit()
    rows = schedule_order(db, order, datetime(2026, 1, 2, 8), True, machine.id)
    assert rows[0].scheduled_start == datetime(2026, 1, 2, 8, 30)
    assert rows[0].machine_id == machine.id
    assert rows[0].scheduled_end > rows[0].scheduled_start
    assert rows[0].assigned_employee_id == employee.id
    assert order.planning_status == "scheduled"
    db.commit()


def test_cost_components_total_and_unit_cost(db):
    order, *_ = seed_order(db, quantity=4, stock=10)
    row = save_cost(db, order, {"material_cost": 20, "labour_cost": 10, "machine_cost": 5, "overhead_cost": 3, "quantity_produced": 4})
    assert row.total_cost == 38
    assert row.unit_cost == 9.5
