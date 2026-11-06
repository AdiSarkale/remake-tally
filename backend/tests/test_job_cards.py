"""Job-card and time-log workflow regression tests."""
import os, sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
os.environ["DATABASE_URL"]="sqlite://"
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import models
from app.api.deps import current_user
from app.db.session import Base,get_db
from app.main import app

@pytest.fixture()
def job_card_context():
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Session=sessionmaker(bind=engine,autoflush=False,autocommit=False)
    Base.metadata.create_all(bind=engine); db=Session()
    user=models.User(username="jobcard-test",full_name="Job Card Test",password_hash="x",role=models.Role.admin,active=True)
    product=models.Product(code="FG-JC-001",name="Job Card Product",unit="PCS")
    material=models.RawMaterial(code="RM-JC-001",name="Job Card Steel",unit="KG",stock=50)
    employee=models.Employee(emp_code="EMP-JC-001",name="Job Card Operator",active=True)
    wc=models.Workcenter(code="WC-JC-001",name="Job Card Workcenter",active=True)
    db.add_all([user,product,material,employee,wc]);db.flush()
    bom=models.BillOfMaterials(product_id=product.id,version=1,active=True);db.add(bom);db.flush()
    db.add(models.BomLine(bom_id=bom.id,material_id=material.id,quantity=2))
    routing=models.Routing(product_id=product.id,version=1,active=True,name="Default");db.add(routing);db.flush()
    operation=models.RoutingOperation(routing_id=routing.id,sequence=1,name="Cut",workcenter_id=wc.id,active=True);db.add(operation);db.flush()
    order=models.ProductionOrder(order_no="PO-JC-001",order_date=date.today(),product_id=product.id,quantity=10,routing_id=routing.id,status="Planned",remarks="");db.add(order);db.flush()
    op_row=models.ProductionOrderOperation(production_order_id=order.id,operation_id=operation.id,sequence=1,workcenter_id=wc.id,assigned_employee_id=employee.id,status="Assigned",planned_qty=10,completed_qty=0);db.add(op_row)
    db.add(models.StockReservation(production_order_id=order.id,material_id=material.id,quantity=20,consumed_quantity=0,status="Reserved"));db.commit()
    app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[current_user]=lambda:user
    try:yield TestClient(app),db,order,employee
    finally:app.dependency_overrides.clear();db.close();Base.metadata.drop_all(bind=engine);engine.dispose()

def test_release_generates_job_cards_and_start_stop_records_time(job_card_context):
    http,db,order,employee=job_card_context
    release=http.post(f"/api/v1/manufacturing/production-orders/{order.id}/transition",json={"action":"release"})
    assert release.status_code==200
    cards=http.get(f"/api/v1/manufacturing/production-orders/{order.id}/job-cards")
    assert cards.status_code==200 and len(cards.json())==1
    card_id=cards.json()[0]["id"]
    start=http.post(f"/api/v1/manufacturing/production-orders/{order.id}/transition",json={"action":"start"})
    assert start.status_code==200
    started=http.post(f"/api/v1/manufacturing/job-cards/{card_id}/start")
    assert started.status_code==200 and started.json()["status"]=="In Progress"
    assert started.json()["time_logs"][0]["employee_id"]==employee.id
    stopped=http.post(f"/api/v1/manufacturing/job-cards/{card_id}/stop")
    assert stopped.status_code==200
    log= db.query(models.JobCardTimeLog).one()
    assert log.end_time is not None and log.duration_minutes>=0

def test_time_logs_reject_overlapping_employee_assignments(job_card_context):
    http,db,order,employee=job_card_context
    cards=http.post(f"/api/v1/manufacturing/production-orders/{order.id}/job-cards")
    card_id=cards.json()[0]["id"]
    start=datetime.now(timezone.utc)
    first=http.post(f"/api/v1/manufacturing/job-cards/{card_id}/time-logs",json={"start_time":start.isoformat(),"end_time":(start+timedelta(hours=1)).isoformat()})
    assert first.status_code==201,first.text
    second=http.post(f"/api/v1/manufacturing/job-cards/{card_id}/time-logs",json={"start_time":(start+timedelta(minutes=30)).isoformat(),"end_time":(start+timedelta(hours=2)).isoformat()})
    assert second.status_code==409

