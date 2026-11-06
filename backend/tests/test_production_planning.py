import os,sys
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

def test_production_planning_aggregates_nested_bom_and_subassembly_requirements():
 engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool);Session=sessionmaker(bind=engine,autoflush=False,autocommit=False);Base.metadata.create_all(bind=engine);db=Session()
 user=models.User(username="plan-test",full_name="Plan Test",password_hash="x",role=models.Role.admin,active=True);fg=models.Product(code="FG-PLAN",name="Plan FG",unit="PCS");sf=models.Product(code="SF-PLAN",name="Plan SF",unit="PCS",stock=2);rm=models.RawMaterial(code="RM-PLAN",name="Plan RM",unit="KG",stock=10);db.add_all([user,fg,sf,rm]);db.flush()
 child=models.BillOfMaterials(product_id=sf.id,version=1,active=True);parent=models.BillOfMaterials(product_id=fg.id,version=1,active=True);db.add_all([child,parent]);db.flush();db.add(models.BomLine(bom_id=child.id,material_id=rm.id,line_type="RM",quantity=3));db.add(models.BomLine(bom_id=parent.id,subassembly_product_id=sf.id,line_type="SF",quantity=2));db.commit();app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[current_user]=lambda:user
 try:
  response=TestClient(app).post("/api/v1/manufacturing/production-planning",json={"items":[{"product_id":fg.id,"quantity":5}]})
  assert response.status_code==200,response.text;body=response.json();assert body["raw_materials"][0]["required_quantity"]==24;assert body["raw_materials"][0]["shortage_quantity"]==20;assert body["subassemblies"][0]["required_quantity"]==10;assert body["subassemblies"][0]["make_quantity"]==8;assert body["materials_available"] is False
  sf.stock=10
  child.active=False
  db.commit()
  stocked=TestClient(app).post("/api/v1/manufacturing/production-planning",json={"items":[{"product_id":fg.id,"quantity":5}]})
  assert stocked.status_code==200,stocked.text
  stocked_body=stocked.json()
  assert stocked_body["raw_materials"]==[]
  assert stocked_body["missing_bom_products"]==[]
  assert stocked_body["subassemblies"][0]["make_quantity"]==0
  assert stocked_body["materials_available"] is True
 finally:
  app.dependency_overrides.clear();db.close();Base.metadata.drop_all(bind=engine);engine.dispose()
