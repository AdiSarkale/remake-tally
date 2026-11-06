"""Warehouse-aware stock and WIP transfer tests."""
import os,sys
from datetime import date
from pathlib import Path
import pytest
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
 e=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool);S=sessionmaker(bind=e,autoflush=False,autocommit=False);Base.metadata.create_all(bind=e);d=S()
 u=models.User(username="wh-test",full_name="WH Test",password_hash="x",role=models.Role.admin,active=True);p=models.Product(code="FG-WH-01",name="FG",unit="PCS");m=models.RawMaterial(code="RM-WH-01",name="Steel",unit="KG",stock=0);pl=models.Plant(code="PL-WH-01",name="Plant",location="Pune",active=True);d.add_all([u,p,m,pl]);d.flush()
 src=models.Warehouse(code="SRC",name="Stores",plant_id=pl.id,active=True);wip=models.Warehouse(code="WIP",name="WIP",plant_id=pl.id,active=True);tgt=models.Warehouse(code="FG",name="Finished",plant_id=pl.id,active=True);d.add_all([src,wip,tgt]);d.flush()
 bom=models.BillOfMaterials(product_id=p.id,version=1,active=True);d.add(bom);d.flush();d.add(models.BomLine(bom_id=bom.id,material_id=m.id,quantity=2));wc=models.Workcenter(code="WC-WH",name="WC",active=True);d.add(wc);d.flush();r=models.Routing(product_id=p.id,version=1,active=True,name="Default");d.add(r);d.flush();op=models.RoutingOperation(routing_id=r.id,sequence=1,name="Build",workcenter_id=wc.id,active=True);d.add(op);d.flush();emp=models.Employee(emp_code="EMP-WH",name="Operator",active=True);d.add(emp);d.flush()
 o=models.ProductionOrder(order_no="PO-WH",order_date=date.today(),product_id=p.id,quantity=10,routing_id=r.id,status="Planned",source_warehouse_id=src.id,wip_warehouse_id=wip.id,target_warehouse_id=tgt.id,remarks="");d.add(o);d.flush();d.add(models.ProductionOrderOperation(production_order_id=o.id,operation_id=op.id,sequence=1,workcenter_id=wc.id,assigned_employee_id=emp.id,status="Assigned",planned_qty=10,completed_qty=0));apply_movement(d,kind=models.ItemKind.material,item_id=m.id,movement_type=models.MovementType.IN,quantity=30,reference="OPEN",reason="Opening",entry_date=date.today(),user_id=u.id,warehouse_id=src.id);d.add(models.StockReservation(production_order_id=o.id,material_id=m.id,quantity=20,consumed_quantity=0,status="Reserved"));d.commit();app.dependency_overrides[get_db]=lambda:d;app.dependency_overrides[current_user]=lambda:u
 try: yield TestClient(app),d,o,m,src,wip
 finally: app.dependency_overrides.clear();d.close();Base.metadata.drop_all(bind=e);e.dispose()
def test_transfer_to_wip_moves_location_balance_and_preserves_total(ctx):
 h,d,o,m,src,wip=ctx;release=h.post(f"/api/v1/manufacturing/production-orders/{o.id}/transition",json={"action":"release"});assert release.status_code==200,release.text
 x=h.post(f"/api/v1/manufacturing/production-orders/{o.id}/transfer-to-wip");assert x.status_code==201,x.text
 a=d.query(models.WarehouseStock).filter_by(warehouse_id=src.id,item_id=m.id).one();b=d.query(models.WarehouseStock).filter_by(warehouse_id=wip.id,item_id=m.id).one();assert a.quantity==10 and b.quantity==20;assert d.get(models.RawMaterial,m.id).stock==30
def test_warehouse_stock_out_rejects_overdraw(ctx):
 h,d,o,m,src,wip=ctx;x=h.post("/api/v1/inventory/movements",json={"item_kind":"material","item_id":m.id,"movement_type":"OUT","quantity":31,"warehouse_id":src.id});assert x.status_code==400;assert d.get(models.RawMaterial,m.id).stock==30


def test_manufacture_consumes_from_wip_and_receives_finished_goods_in_target(ctx):
    h,d,o,m,src,wip=ctx
    # The target warehouse is already attached to the order fixture.
    release=h.post(f"/api/v1/manufacturing/production-orders/{o.id}/transition",json={"action":"release"})
    assert release.status_code==200,release.text
    start=h.post(f"/api/v1/manufacturing/production-orders/{o.id}/transition",json={"action":"start"})
    assert start.status_code==200,start.text
    transfer=h.post(f"/api/v1/manufacturing/production-orders/{o.id}/transfer-to-wip")
    assert transfer.status_code==201,transfer.text
    card=h.get(f"/api/v1/manufacturing/production-orders/{o.id}/job-cards").json()[0]
    produced=h.post("/api/v1/production",json={"entry_date":date.today().isoformat(),"product_id":o.product_id,"quantity":10,"production_order_id":o.id,"job_card_id":card["id"]})
    assert produced.status_code==201,produced.text
    wip_balance=d.query(models.WarehouseStock).filter_by(warehouse_id=wip.id,item_id=m.id).one()
    assert wip_balance.quantity==0
    finished=d.query(models.WarehouseStock).filter_by(warehouse_id=o.target_warehouse_id,item_id=o.product_id).one()
    assert finished.quantity==10
    assert d.get(models.RawMaterial,m.id).stock==10


def test_warehouse_finished_goods_remain_held_until_quality_acceptance(ctx):
    h,d,o,m,src,wip=ctx
    release=h.post(f"/api/v1/manufacturing/production-orders/{o.id}/transition",json={"action":"release"});assert release.status_code==200,release.text
    start=h.post(f"/api/v1/manufacturing/production-orders/{o.id}/transition",json={"action":"start"});assert start.status_code==200,start.text
    h.post(f"/api/v1/manufacturing/production-orders/{o.id}/transfer-to-wip")
    card=h.get(f"/api/v1/manufacturing/production-orders/{o.id}/job-cards").json()[0]
    produced=h.post("/api/v1/production",json={"entry_date":date.today().isoformat(),"product_id":o.product_id,"quantity":10,"production_order_id":o.id,"job_card_id":card["id"]})
    assert produced.status_code==201,produced.text
    finished=d.query(models.WarehouseStock).filter_by(warehouse_id=o.target_warehouse_id,item_id=o.product_id).one()
    assert finished.quality_hold_quantity==10
    blocked=h.post("/api/v1/inventory/movements",json={"item_kind":"product","item_id":o.product_id,"movement_type":"OUT","quantity":1,"warehouse_id":o.target_warehouse_id})
    assert blocked.status_code==409
    inspection=h.get(f"/api/v1/manufacturing/production/{produced.json()['id']}/quality-inspection")
    assert inspection.status_code==200 and inspection.json()["status"]=="Pending"
    accepted=h.patch(f"/api/v1/manufacturing/production/{produced.json()['id']}/quality",json={"status":"Accepted","accepted_qty":10,"rejected_qty":0,"remarks":"Passed final inspection"})
    assert accepted.status_code==200,accepted.text
    d.refresh(finished);assert finished.quality_hold_quantity==0
    released=h.post("/api/v1/inventory/movements",json={"item_kind":"product","item_id":o.product_id,"movement_type":"OUT","quantity":10,"warehouse_id":o.target_warehouse_id})
    assert released.status_code==201,released.text
