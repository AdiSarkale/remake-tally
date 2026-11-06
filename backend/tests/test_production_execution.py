"""Regression tests for atomic production inventory posting."""

import os
import sys
from datetime import date
from pathlib import Path

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


def _production_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = testing_session()

    user = models.User(
        username="production-regression",
        full_name="Production Regression",
        password_hash="not-used",
        role=models.Role.admin,
        active=True,
    )
    product = models.Product(code="FG-REG-001", name="Regression Finished Good", unit="PCS")
    material = models.RawMaterial(
        code="RM-REG-001",
        name="Regression Steel",
        unit="KG",
        stock=15,
    )
    db.add_all([user, product, material])
    db.flush()

    bom = models.BillOfMaterials(product_id=product.id, version=1, active=True)
    db.add(bom)
    db.flush()
    db.add(models.BomLine(bom_id=bom.id, material_id=material.id, quantity=2))
    db.commit()

    def override_db():
        yield db

    def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[current_user] = override_user
    return engine, db, TestClient(app), product, material


def _cleanup(engine, db):
    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_default_bom_consumption_rejects_insufficient_stock_without_posting():
    engine, db, http, product, material = _production_fixture()
    try:
        response = http.post(
            "/api/v1/production",
            json={
                "entry_date": date.today().isoformat(),
                "product_id": product.id,
                "quantity": 10,
            },
        )

        assert response.status_code == 400
        assert "Insufficient stock" in response.json()["detail"]
        db.expire_all()
        assert db.get(models.RawMaterial, material.id).stock == 15
        assert db.get(models.Product, product.id).stock == 0
        assert db.query(models.ProductionEntry).count() == 0
        assert db.query(models.InventoryMovement).count() == 0
    finally:
        http.close()
        _cleanup(engine, db)


def test_default_bom_consumption_posts_material_out_and_finished_goods_in():
    engine, db, http, product, material = _production_fixture()
    try:
        material.stock = 25
        db.commit()

        response = http.post(
            "/api/v1/production",
            json={
                "entry_date": date.today().isoformat(),
                "product_id": product.id,
                "quantity": 10,
            },
        )

        assert response.status_code == 201, response.text
        db.expire_all()
        assert db.get(models.RawMaterial, material.id).stock == 5
        assert db.get(models.Product, product.id).stock == 10
        assert db.query(models.ProductionEntry).count() == 1
        assert db.query(models.InventoryMovement).count() == 2
        entry = db.query(models.ProductionEntry).one()
        assert entry.consumption[0].planned_quantity == 20
        assert entry.consumption[0].quantity == 20
    finally:
        http.close()
        _cleanup(engine, db)
