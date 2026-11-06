import os, sys
from pathlib import Path
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import models
from app.db.session import Base
from app.services.bom import explode_material_requirements

@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

def test_nested_bom_explodes_to_aggregated_raw_materials(db):
    finished = models.Product(code="FG-ML", name="Finished", unit="PCS")
    subassembly = models.Product(code="SF-ML", name="Subassembly", unit="PCS")
    steel = models.RawMaterial(code="RM-ML", name="Steel", unit="KG", stock=100)
    db.add_all([finished, subassembly, steel])
    db.flush()
    child = models.BillOfMaterials(product_id=subassembly.id, version=1, active=True)
    parent = models.BillOfMaterials(product_id=finished.id, version=1, active=True)
    db.add_all([child, parent])
    db.flush()
    db.add(models.BomLine(bom_id=child.id, material_id=steel.id, line_type="RM", quantity=3))
    db.add(models.BomLine(bom_id=parent.id, subassembly_product_id=subassembly.id, line_type="SF", quantity=2))
    db.commit()
    assert explode_material_requirements(db, finished.id, 5) == {steel.id: 30.0}

def test_nested_bom_rejects_circular_dependency(db):
    first = models.Product(code="FG-CYCLE", name="First", unit="PCS")
    second = models.Product(code="SF-CYCLE", name="Second", unit="PCS")
    db.add_all([first, second])
    db.flush()
    a = models.BillOfMaterials(product_id=first.id, version=1, active=True)
    b = models.BillOfMaterials(product_id=second.id, version=1, active=True)
    db.add_all([a, b])
    db.flush()
    db.add(models.BomLine(bom_id=a.id, subassembly_product_id=second.id, line_type="SF", quantity=1))
    db.add(models.BomLine(bom_id=b.id, subassembly_product_id=first.id, line_type="SF", quantity=1))
    db.commit()
    with pytest.raises(HTTPException):
        explode_material_requirements(db, first.id, 1)

def test_nested_bom_rejects_missing_child_bom(db):
    finished = models.Product(code="FG-MISS", name="Finished Missing", unit="PCS")
    child = models.Product(code="SF-MISS", name="Missing Subassembly", unit="PCS")
    db.add_all([finished, child])
    db.flush()
    bom = models.BillOfMaterials(product_id=finished.id, version=1, active=True)
    db.add(bom)
    db.flush()
    db.add(models.BomLine(bom_id=bom.id, subassembly_product_id=child.id, line_type="SF", quantity=1))
    db.commit()
    with pytest.raises(HTTPException):
        explode_material_requirements(db, finished.id, 1)
