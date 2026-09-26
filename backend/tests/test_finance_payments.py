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
from app.db.session import Base, get_db
from app.main import app
from app.api.deps import current_user


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    user = models.User(
        username="tester",
        full_name="Test User",
        password_hash="not-used",
        role=models.Role.admin,
        active=True,
    )
    customer = models.Party(kind="customer", name="Test Customer")
    supplier = models.Party(kind="supplier", name="Test Supplier")
    db_session.add_all([user, customer, supplier])
    db_session.flush()

    invoice = models.Invoice(
        invoice_no="INV-TEST-001",
        invoice_date=date.today(),
        customer_id=customer.id,
        customer_name=customer.name,
        grand_total=1000,
        paid_amount=0,
        balance_amount=1000,
        status=models.InvoiceStatus.unpaid,
    )
    po = models.PurchaseOrder(
        po_no="PO-TEST-001",
        po_date=date.today(),
        expected_date=date.today(),
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        warehouse_id="WH-TEST",
        sub_total=2000,
        gst_total=360,
        grand_total=2360,
        status=models.PurchaseOrderStatus.approved,
        created_by="tester",
    )
    db_session.add_all([invoice, po])
    db_session.commit()
    db_session.refresh(customer)
    db_session.refresh(supplier)
    db_session.refresh(invoice)
    db_session.refresh(po)

    def override_db():
        yield db_session

    def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[current_user] = override_user
    try:
        yield TestClient(app), customer, supplier, invoice, po
    finally:
        app.dependency_overrides.clear()


def test_customer_payment_creates_record_and_updates_invoice(client):
    http, customer, _, invoice, _ = client

    response = http.post(
        "/api/v1/finance/customer-payments",
        json={
            "payment_date": str(date.today()),
            "customer_id": customer.id,
            "invoice_id": invoice.id,
            "amount": 400,
            "mode": "NEFT",
            "reference": "UTR-400",
            "remarks": "Part payment",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["payment_no"] == "CPAY0001"
    assert body["amount"] == 400
    assert body["invoice_no"] == "INV-TEST-001"

    assert invoice.paid_amount == 400
    assert invoice.balance_amount == 600
    assert invoice.status == models.InvoiceStatus.partial


def test_customer_payment_rejects_overpayment(client):
    http, customer, _, invoice, _ = client

    response = http.post(
        "/api/v1/finance/customer-payments",
        json={
            "payment_date": str(date.today()),
            "customer_id": customer.id,
            "invoice_id": invoice.id,
            "amount": 1001,
            "mode": "NEFT",
        },
    )

    assert response.status_code == 400
    assert "exceeds invoice balance" in response.json()["detail"]


def test_customer_payment_marks_invoice_paid(client):
    http, customer, _, invoice, _ = client

    response = http.post(
        "/api/v1/finance/customer-payments",
        json={
            "payment_date": str(date.today()),
            "customer_id": customer.id,
            "invoice_id": invoice.id,
            "amount": 1000,
            "mode": "Bank Transfer",
        },
    )

    assert response.status_code == 201
    assert invoice.paid_amount == 1000
    assert invoice.balance_amount == 0
    assert invoice.status == models.InvoiceStatus.paid


def test_supplier_payment_creates_record_and_payable(client):
    http, _, supplier, _, po = client

    response = http.post(
        "/api/v1/finance/supplier-payments",
        json={
            "payment_date": str(date.today()),
            "supplier_id": supplier.id,
            "purchase_order_id": po.id,
            "amount": 500,
            "mode": "NEFT",
            "reference": "UTR-500",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["payment_no"] == "SPAY0001"
    assert body["po_no"] == "PO-TEST-001"

    payable = http.get("/api/v1/finance/payables")
    assert payable.status_code == 200
    row = next(x for x in payable.json() if x["purchase_order_id"] == po.id)
    assert row["grand_total"] == 2360
    assert row["paid_amount"] == 500
    assert row["balance_amount"] == 1860


def test_supplier_payment_rejects_overpayment(client):
    http, _, supplier, _, po = client

    response = http.post(
        "/api/v1/finance/supplier-payments",
        json={
            "payment_date": str(date.today()),
            "supplier_id": supplier.id,
            "purchase_order_id": po.id,
            "amount": 2361,
            "mode": "NEFT",
        },
    )

    assert response.status_code == 400
    assert "exceeds purchase order balance" in response.json()["detail"]


def test_receivables_are_derived_from_payment_records(client):
    http, customer, _, invoice, _ = client

    create = http.post(
        "/api/v1/finance/customer-payments",
        json={
            "payment_date": str(date.today()),
            "customer_id": customer.id,
            "invoice_id": invoice.id,
            "amount": 250,
            "mode": "UPI",
        },
    )
    assert create.status_code == 201

    response = http.get("/api/v1/finance/receivables")
    assert response.status_code == 200
    row = next(x for x in response.json() if x["invoice_id"] == invoice.id)
    assert row["grand_total"] == 1000
    assert row["paid_amount"] == 250
    assert row["balance_amount"] == 750
    assert row["status"] == "Partial"


def test_payment_history_endpoints_return_actual_records(client):
    http, customer, supplier, invoice, po = client

    cp = http.post(
        "/api/v1/finance/customer-payments",
        json={
            "payment_date": str(date.today()),
            "customer_id": customer.id,
            "invoice_id": invoice.id,
            "amount": 100,
            "mode": "UPI",
        },
    )
    sp = http.post(
        "/api/v1/finance/supplier-payments",
        json={
            "payment_date": str(date.today()),
            "supplier_id": supplier.id,
            "purchase_order_id": po.id,
            "amount": 200,
            "mode": "NEFT",
        },
    )
    assert cp.status_code == 201
    assert sp.status_code == 201

    customer_history = http.get("/api/v1/finance/customer-payments")
    supplier_history = http.get("/api/v1/finance/supplier-payments")

    assert customer_history.status_code == 200
    assert supplier_history.status_code == 200
    assert any(x["payment_no"] == "CPAY0001" for x in customer_history.json())
    assert any(x["payment_no"] == "SPAY0001" for x in supplier_history.json())
