"""Production order lifecycle transition regression tests."""
import os, sys
from datetime import date
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import models
from app.api.deps import current_user
from app.db.session import Base, get_db
from app.main import app

@pytest.fixture()
def lifecycle_context():
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Session=sessionmaker(bind=engine,autoflush=False,autocommit=False)
    Base.metadata.create_all(bind=engine); db=Session()
    user=models.User(username="lifecycle-test",full_name="Lifecycle Test",password_hash="x",role=models.Role.admin,active=True)
    product=models.Product(code="FG-LIFE-001",name="Lifecycle Product",unit="PCS")
    material=models.RawMaterial(code="RM-LIFE-001",name="Lifecycle Steel",unit="KG",stock=50)
    employee=models.Employee(emp_code="EMP-LIFE-001",name="Lifecycle Operator",active=True)
    wc=models.Workcenter(code="WC-LIFE-001",name="Lifecycle Workcenter",active=True)
    db.add_all([user,product,material,employee,wc]); db.flush()
    bom=models.BillOfMaterials(product_id=product.id,version=1,active=True); db.add(bom); db.flush()
    db.add(models.BomLine(bom_id=bom.id,material_id=material.id,quantity=2))
    routing=models.Routing(product_id=product.id,version=1,active=True,name="Default")
    db.add(routing); db.flush()
    operation=models.RoutingOperation(routing_id=routing.id,sequence=1,name="Assembly",workcenter_id=wc.id,active=True)
    db.add(operation); db.flush()
    order=models.ProductionOrder(order_no="PO-LIFE-001",order_date=date.today(),product_id=product.id,quantity=10,routing_id=routing.id,status="Planned",remarks="")
    db.add(order); db.flush()
    op_row=models.ProductionOrderOperation(production_order_id=order.id,operation_id=operation.id,sequence=1,workcenter_id=wc.id,assigned_employee_id=employee.id,status="Assigned",planned_qty=10,completed_qty=0)
    db.add(op_row)
    db.add(models.StockReservation(production_order_id=order.id,material_id=material.id,quantity=20,consumed_quantity=0,status="Reserved"))
    db.commit()
    app.dependency_overrides[get_db]=lambda:db; app.dependency_overrides[current_user]=lambda:user
    try: yield TestClient(app),db,order,op_row,product,material
    finally:
        app.dependency_overrides.clear(); db.close(); Base.metadata.drop_all(bind=engine); engine.dispose()

def test_lifecycle_rejects_skipping_release_and_start(lifecycle_context):
    http,_,order,_,_,_=lifecycle_context
    response=http.post(f"/api/v1/manufacturing/production-orders/{order.id}/transition",json={"action":"start"})
    assert response.status_code==409
    response=http.post(f"/api/v1/manufacturing/production-orders/{order.id}/transition",json={"action":"release"})
    assert response.status_code==200 and response.json()["status"]=="Released"
    response=http.post(f"/api/v1/manufacturing/production-orders/{order.id}/transition",json={"action":"start"})
    assert response.status_code==200 and response.json()["status"]=="In Progress"

def test_lifecycle_blocks_premature_completion_and_cancelling_posted_production(lifecycle_context):
    http,db,order,op_row,product,_=lifecycle_context
    http.post(f"/api/v1/manufacturing/production-orders/{order.id}/transition",json={"action":"release"})
    http.post(f"/api/v1/manufacturing/production-orders/{order.id}/transition",json={"action":"start"})
    response=http.post(f"/api/v1/manufacturing/production-orders/{order.id}/transition",json={"action":"complete"})
    assert response.status_code==409
    db.add(models.ProductionEntry(batch_no="BATCH-LIFE-001",entry_date=date.today(),product_id=product.id,quantity=2,production_order_id=order.id))
    db.commit()
    response=http.post(f"/api/v1/manufacturing/production-orders/{order.id}/transition",json={"action":"cancel"})
    assert response.status_code==409

def test_cancellation_releases_reservations_when_nothing_is_produced(lifecycle_context):
    http,db,order,_,_,_=lifecycle_context
    response=http.post(f"/api/v1/manufacturing/production-orders/{order.id}/transition",json={"action":"cancel"})
    assert response.status_code==200 and response.json()["status"]=="Cancelled"
    reservation=db.query(models.StockReservation).one()
    assert reservation.status=="Released"


def test_order_requires_explicit_completion_after_all_output_and_operations(lifecycle_context):
    http, db, order, op_row, product, _ = lifecycle_context
    http.post(f"/api/v1/manufacturing/production-orders/{order.id}/transition", json={"action": "release"})
    started = http.post(f"/api/v1/manufacturing/production-orders/{order.id}/transition", json={"action": "start"})
    assert started.status_code == 200
    production = http.post("/api/v1/production", json={
        "entry_date": date.today().isoformat(),
        "product_id": product.id,
        "quantity": 10,
        "production_order_id": order.id,
        "operation_id": op_row.id,
    })
    assert production.status_code == 201, production.text
    db.refresh(order)
    assert order.status == "In Progress"
    db.refresh(op_row)
    assert op_row.status == "Completed"
    completed = http.post(f"/api/v1/manufacturing/production-orders/{order.id}/transition", json={"action": "complete"})
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "Completed"
    reservation = db.query(models.StockReservation).one()
    assert reservation.status == "Consumed"



def test_release_requires_full_material_reservation(lifecycle_context):
    http, db, order, _, _, _ = lifecycle_context
    db.query(models.StockReservation).filter_by(production_order_id=order.id).delete()
    db.commit()

    response = http.post(
        f"/api/v1/manufacturing/production-orders/{order.id}/transition",
        json={"action": "release"},
    )

    assert response.status_code == 409
    db.refresh(order)
    assert order.status == "Planned"
    assert db.query(models.JobCard).filter_by(production_order_id=order.id).count() == 0
