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
