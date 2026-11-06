import os,sys
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
os.environ["DATABASE_URL"]="sqlite://";sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import models
from app.api.deps import current_user
from app.db.session import Base,get_db
from app.main import app

def test_production_order_cost_summary_includes_material_labour_overhead_and_scrap():
 e=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool);S=sessionmaker(bind=e,autoflush=False,autocommit=False);Base.metadata.create_all(bind=e);d=S()
 u=models.User(username="cost-test",full_name="Cost Test",password_hash="x",role=models.Role.admin,active=True);p=models.Product(code="FG-COST",name="Cost FG",unit="PCS");m=models.RawMaterial(code="RM-COST",name="Cost RM",unit="KG",stock=100,cost=4);emp=models.Employee(emp_code="EMP-COST",name="Cost Operator",active=True,hourly_rate=18);wc=models.Workcenter(code="WC-COST",name="Cost Workcenter",active=True,overhead_rate_per_hour=12);d.add_all([u,p,m,emp,wc]);d.flush()
 routing=models.Routing(product_id=p.id,version=1,active=True,name="Cost Route");d.add(routing);d.flush();op=models.RoutingOperation(routing_id=routing.id,sequence=1,name="Assembly",workcenter_id=wc.id,active=True);d.add(op);d.flush();order=models.ProductionOrder(order_no="PO-COST",order_date=date.today(),product_id=p.id,quantity=10,routing_id=routing.id,status="Completed",remarks="");d.add(order);d.flush();oprow=models.ProductionOrderOperation(production_order_id=order.id,operation_id=op.id,sequence=1,workcenter_id=wc.id,assigned_employee_id=emp.id,planned_qty=10,completed_qty=10,status="Completed");d.add(oprow);card=models.JobCard(production_order_id=order.id,production_order_operation_id=oprow.id,operation_id=op.id,workcenter_id=wc.id,assigned_employee_id=emp.id,planned_qty=10,completed_qty=10,status="Completed");d.add(card);d.flush()
 d.add(models.ProductionEntry(batch_no="BATCH-COST",entry_date=date.today(),product_id=p.id,quantity=10,production_order_id=order.id,planned_material_cost=80,actual_material_cost=100,material_variance_cost=20,scrap_recovery_value=6,total_cost=94,unit_cost=9.4,actual_scrap=2));d.add(models.JobCardTimeLog(job_card_id=card.id,employee_id=emp.id,start_time=datetime.now(timezone.utc)-timedelta(hours=1),end_time=datetime.now(timezone.utc),duration_minutes=60));d.commit();app.dependency_overrides[get_db]=lambda:d;app.dependency_overrides[current_user]=lambda:u
 try:
  response=TestClient(app).get(f"/api/v1/manufacturing/production-orders/{order.id}/cost-summary");assert response.status_code==200,response.text;body=response.json();assert body["planned_material_cost"]==80;assert body["actual_material_cost"]==100;assert body["material_variance_cost"]==20;assert body["labor_cost"]==18;assert body["overhead_cost"]==12;assert body["scrap_recovery_value"]==6;assert body["total_cost"]==124;assert body["unit_cost"]==12.4
 finally:app.dependency_overrides.clear();d.close();Base.metadata.drop_all(bind=e);e.dispose()
