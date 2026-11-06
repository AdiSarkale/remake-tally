"""Quality inspection and finished-goods release regression tests."""
import os,sys
from datetime import date
from pathlib import Path
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
os.environ["DATABASE_URL"]="sqlite://";sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import models
from app.api.deps import current_user
from app.db.session import Base,get_db
from app.main import app
from app.services.inventory import apply_movement
@pytest.fixture()
def ctx():
 e=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool);S=sessionmaker(bind=e,autoflush=False,autocommit=False);Base.metadata.create_all(bind=e);d=S();u=models.User(username="qa-test",full_name="QA",password_hash="x",role=models.Role.admin,active=True);p=models.Product(code="FG-QA",name="QA Product",unit="PCS",stock=10,quality_hold_stock=10);d.add_all([u,p]);d.flush();entry=models.ProductionEntry(batch_no="BATCH-QA",entry_date=date.today(),product_id=p.id,quantity=10,quality_status="Pending");d.add(entry);d.flush();inspection=models.QualityInspection(production_entry_id=entry.id,status="Pending",inspected_quantity=10);d.add(inspection);d.commit();app.dependency_overrides[get_db]=lambda:d;app.dependency_overrides[current_user]=lambda:u
 try:yield TestClient(app),d,u,p,entry
 finally:app.dependency_overrides.clear();d.close();Base.metadata.drop_all(bind=e);e.dispose()
def test_finished_goods_are_blocked_until_inspection(ctx):
 h,d,u,p,entry=ctx
 with pytest.raises(HTTPException) as exc: apply_movement(d,kind=models.ItemKind.product,item_id=p.id,movement_type=models.MovementType.OUT,quantity=1,reference="SALE",reason="Sale",entry_date=date.today(),user_id=u.id)
 assert exc.value.status_code==409

def test_acceptance_releases_only_accepted_quantity(ctx):
 h,d,u,p,entry=ctx;x=h.patch(f"/api/v1/manufacturing/production/{entry.id}/quality",json={"status":"Accepted with Deviation","accepted_qty":8,"rejected_qty":2,"remarks":"Two rejected","checks":[{"test_name":"Dimensions","expected_value":"10mm","actual_value":"10mm","passed":True}]});assert x.status_code==200,x.text
 d.refresh(p);assert p.quality_hold_stock==2
 movement=apply_movement(d,kind=models.ItemKind.product,item_id=p.id,movement_type=models.MovementType.OUT,quantity=8,reference="SALE",reason="Sale",entry_date=date.today(),user_id=u.id);assert movement.balance==2
 assert d.query(models.QualityInspectionLine).count()==1

def test_quality_quantities_must_equal_produced_quantity(ctx):
 h,d,u,p,entry=ctx;x=h.patch(f"/api/v1/manufacturing/production/{entry.id}/quality",json={"status":"Accepted","accepted_qty":9,"rejected_qty":0});assert x.status_code==400;assert d.query(models.QualityInspection).one().status=="Pending"
