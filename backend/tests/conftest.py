import os
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite://"

from app import models
from app.core.security import hash_password
from app.db.session import Base, get_db
from app.main import app

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)

@pytest.fixture()
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()

@pytest.fixture()
def client(db):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)

@pytest.fixture()
def admin(db):
    user = models.User(
        id=str(uuid4()),
        username=f"admin-{uuid4().hex[:8]}",
        full_name="Test Admin",
        password_hash=hash_password("password123"),
        role=models.Role.admin,
        email="admin@example.com",
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture()
def auth_headers(client, admin):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": admin.username, "password": "password123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

@pytest.fixture()
def product(db):
    row = models.Product(
        id=str(uuid4()),
        code=f"FG-{uuid4().hex[:6].upper()}",
        name="Test Finished Good",
        unit="PCS",
        stock=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

@pytest.fixture()
def material(db):
    row = models.RawMaterial(
        id=str(uuid4()),
        code=f"RM-{uuid4().hex[:6].upper()}",
        name="Test Raw Material",
        unit="KG",
        stock=100,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

@pytest.fixture()
def workcenter(db):
    row = models.Workcenter(
        id=str(uuid4()),
        code=f"WC-{uuid4().hex[:6].upper()}",
        name="Assembly",
        department="Production",
        capacity_per_hour=100,
        status="Available",
        active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
