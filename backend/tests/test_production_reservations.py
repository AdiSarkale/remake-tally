"""Regression tests for production-order stock reservations."""
import os
import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi import HTTPException
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
from app.services.inventory import apply_movement


@pytest.fixture()
def reservation_context():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = Session()
    user = models.User(username="reservation-test", full_name="Reservation Test", password_hash="x", role=models.Role.admin, active=True)
    product = models.Product(code="FG-RES-001", name="Reserved Product", unit="PCS")
    material = models.RawMaterial(code="RM-RES-001", name="Reserved Steel", unit="KG", stock=30)
    db.add_all([user, product, material])
    db.flush()
    bom = models.BillOfMaterials(product_id=product.id, version=1, active=True)
    db.add(bom)
    db.flush()
    db.add(models.BomLine(bom_id=bom.id, material_id=material.id, quantity=2))
    order = models.ProductionOrder(order_no="PO-RES-001", order_date=date.today(), product_id=product.id, quantity=10, status="Planned", remarks="")
    db.add(order)
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[current_user] = lambda: user
    try:
        yield TestClient(app), db, order, product, material
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_reservation_is_atomic_when_any_bom_material_is_short(reservation_context):
    http, db, order, _, material = reservation_context
    material.stock = 15
    db.commit()
    response = http.post(f"/api/v1/manufacturing/production-orders/{order.id}/reserve-materials")
    assert response.status_code == 409
    assert db.query(models.StockReservation).count() == 0
    assert db.get(models.RawMaterial, material.id).stock == 15


def test_reservation_is_idempotent_and_release_returns_unconsumed_stock(reservation_context):
    http, db, order, _, material = reservation_context
    first = http.post(f"/api/v1/manufacturing/production-orders/{order.id}/reserve-materials")
    assert first.status_code == 200, first.text
    assert first.json()["reservations"][0]["quantity"] == 20
    second = http.post(f"/api/v1/manufacturing/production-orders/{order.id}/reserve-materials")
    assert second.status_code == 200, second.text
    assert db.query(models.StockReservation).count() == 1
    assert second.json()["reservations"][0]["quantity"] == 20
    released = http.post(f"/api/v1/manufacturing/production-orders/{order.id}/release-materials")
    assert released.status_code == 200, released.text
    row = db.query(models.StockReservation).one()
    assert row.status == "Released"
    assert row.remaining_quantity == 20
    assert db.get(models.RawMaterial, material.id).stock == 30


def test_inventory_outbound_cannot_consume_another_orders_reserved_stock(reservation_context):
    _, db, order, _, material = reservation_context
    db.add(models.StockReservation(production_order_id=order.id, material_id=material.id, quantity=20, consumed_quantity=0, status="Reserved"))
    db.commit()
    with pytest.raises(HTTPException) as exc:
        apply_movement(db, kind=models.ItemKind.material, item_id=material.id, movement_type=models.MovementType.OUT,
            quantity=11, reference="TEST", reason="Unrelated issue", entry_date=date.today(), user_id="tester")
    assert exc.value.status_code == 400
    assert db.get(models.RawMaterial, material.id).stock == 30


def test_reserved_order_can_consume_its_own_reserved_stock(reservation_context):
    _, db, order, _, material = reservation_context
    db.add(models.StockReservation(production_order_id=order.id, material_id=material.id, quantity=20, consumed_quantity=0, status="Reserved"))
    db.commit()
    movement = apply_movement(db, kind=models.ItemKind.material, item_id=material.id, movement_type=models.MovementType.OUT,
        quantity=20, reference="TEST", reason="Order consumption", entry_date=date.today(), user_id="tester", reservation_order_id=order.id)
    assert movement.balance == 10
    assert db.get(models.RawMaterial, material.id).stock == 10



def test_company_wide_reservation_blocks_warehouse_issue(reservation_context):
    _, db, order, _, material = reservation_context
    plant = models.Plant(code="PL-RES-001", name="Reservation Plant", location="Test floor", active=True)
    db.add(plant)
    db.flush()
    warehouse = models.Warehouse(code="WH-RES-001", name="Reservation Warehouse", plant_id=plant.id, active=True)
    db.add(warehouse)
    db.flush()
    db.add(models.WarehouseStock(
        warehouse_id=warehouse.id,
        item_kind=models.ItemKind.material,
        item_id=material.id,
        item_name=material.name,
        quantity=30,
        unit=material.unit,
    ))
    db.add(models.StockReservation(
        production_order_id=order.id,
        material_id=material.id,
        quantity=20,
        consumed_quantity=0,
        status="Reserved",
        warehouse_id=None,
    ))
    db.commit()

    with pytest.raises(HTTPException) as exc:
        apply_movement(
            db,
            kind=models.ItemKind.material,
            item_id=material.id,
            movement_type=models.MovementType.OUT,
            quantity=11,
            reference="WAREHOUSE-ISSUE",
            reason="Unrelated warehouse issue",
            entry_date=date.today(),
            user_id="tester",
            warehouse_id=warehouse.id,
        )
    assert exc.value.status_code == 400
    assert db.get(models.RawMaterial, material.id).stock == 30
    balance = db.query(models.WarehouseStock).filter_by(
        warehouse_id=warehouse.id, item_kind=models.ItemKind.material, item_id=material.id
    ).one()
    assert balance.quantity == 30
