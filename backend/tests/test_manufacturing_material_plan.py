import os
import sys
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
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = testing_session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def manufacturing_client(db_session):
    user = models.User(
        username="manufacturing-tester",
        full_name="Manufacturing Tester",
        password_hash="not-used",
        role=models.Role.admin,
        active=True,
    )
    product = models.Product(code="FG-MFG-001", name="Test Finished Good", unit="PCS")
    material = models.RawMaterial(
        code="RM-MFG-001",
        name="Test Steel",
        unit="KG",
        stock=15,
    )
    db_session.add_all([user, product, material])
    db_session.flush()

    bom = models.BillOfMaterials(
        product_id=product.id,
        version=1,
        active=True,
        expected_scrap_percent=0,
    )
    db_session.add(bom)
    db_session.flush()
    db_session.add(models.BomLine(bom_id=bom.id, material_id=material.id, quantity=2))

    order = models.ProductionOrder(
        order_no="PO-MFG-TEST-001",
        order_date=date.today(),
        product_id=product.id,
        quantity=10,
        status="Planned",
        remarks="",
    )
    db_session.add(order)
    db_session.commit()

    def override_db():
        yield db_session

    def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[current_user] = override_user
    try:
        yield TestClient(app), db_session, order, product, material
    finally:
        app.dependency_overrides.clear()


def test_manufacturing_router_is_mounted_and_material_plan_reports_shortage(manufacturing_client):
    http, _, order, _, _ = manufacturing_client

    workcenters = http.get("/api/v1/manufacturing/workcenters")
    assert workcenters.status_code == 200

    response = http.get(f"/api/v1/manufacturing/production-orders/{order.id}/material-plan")
    assert response.status_code == 200

    body = response.json()
    assert body["order_no"] == "PO-MFG-TEST-001"
    assert body["materials_available"] is False
    assert body["materials"] == [
        {
            "material_id": body["materials"][0]["material_id"],
            "material_code": "RM-MFG-001",
            "material_name": "Test Steel",
            "unit": "KG",
            "required_quantity": 20,
            "consumed_quantity": 0,
            "remaining_quantity": 20,
            "available_quantity": 15,
            "shortage_quantity": 5,
            "status": "Shortage",
        }
    ]


def test_material_plan_subtracts_consumption_already_recorded_for_order(manufacturing_client):
    http, db, order, product, material = manufacturing_client
    material.stock = 14
    entry = models.ProductionEntry(
        batch_no="BATCH-MFG-TEST-001",
        entry_date=date.today(),
        product_id=product.id,
        quantity=3,
        production_order_id=order.id,
    )
    db.add(entry)
    db.flush()
    db.add(
        models.ProductionConsumption(
            production_id=entry.id,
            material_id=material.id,
            planned_quantity=6,
            quantity=6,
        )
    )
    db.commit()

    response = http.get(f"/api/v1/manufacturing/production-orders/{order.id}/material-plan")
    assert response.status_code == 200

    row = response.json()["materials"][0]
    assert row["required_quantity"] == 20
    assert row["consumed_quantity"] == 6
    assert row["remaining_quantity"] == 14
    assert row["available_quantity"] == 14
    assert row["shortage_quantity"] == 0
    assert row["status"] == "Available"
    assert response.json()["materials_available"] is True


def test_material_plan_rejects_orders_without_an_active_bom(manufacturing_client):
    http, db, order, _, _ = manufacturing_client
    db.query(models.BillOfMaterials).filter_by(product_id=order.product_id).update(
        {models.BillOfMaterials.active: False}
    )
    db.commit()

    response = http.get(f"/api/v1/manufacturing/production-orders/{order.id}/material-plan")
    assert response.status_code == 400
    assert "No active BOM" in response.json()["detail"]
