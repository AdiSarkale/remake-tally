"""Seed a complete, repeatable MiniTally demo dataset.

Run from backend:
    python -m app.seed
    python -m app.seed --reset-demo

The dataset is intentionally connected so the demo can walk through:
masters -> purchase order -> GRN -> inventory -> BOM/routing/work centre ->
production order -> employee assignment -> production/quality -> customer PO ->
quotation -> sales order -> delivery -> dispatch -> invoice/payment.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from app import models
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models import ItemKind, MovementType
from app.services.gst import compute_line, round_off
from app.services.inventory import apply_movement


DEMO_USERS = [
    ("admin", "Ravi Kulkarni", "admin123", models.Role.admin),
    ("accounts", "Priya Deshmukh", "accounts123", models.Role.accountant),
    ("operator", "Imran Shaikh", "operator123", models.Role.operator),
]

DEMO = {
    "customer_name": "Vardhman Auto Parts",
    "supplier_name": "Bharat Steel Traders",
    "product_1": "FG-001",
    "product_2": "FG-002",
    "material_1": "RM-001",
    "material_2": "RM-002",
    "scrap_1": "SCR-001",
    "scrap_2": "SCR-002",
    "plant": "PL-01",
    "warehouse": "WH-01",
    "workcenter_1": "WC-CNC",
    "workcenter_2": "WC-FAB",
    "employee_1": "EMP-001",
    "employee_2": "EMP-002",
}


def _first(db, model, **filters):
    return db.query(model).filter_by(**filters).first()


def _party(db, kind: str, name: str, **kwargs):
    row = _first(db, models.Party, kind=kind, name=name)
    if row is None:
        row = models.Party(kind=kind, name=name, **kwargs)
        db.add(row)
        db.flush()
    else:
        for key, value in kwargs.items():
            setattr(row, key, value)
    return row


def _product(db, code: str, name: str, **kwargs):
    row = _first(db, models.Product, code=code)
    if row is None:
        row = models.Product(code=code, name=name, **kwargs)
        db.add(row)
        db.flush()
    else:
        row.name = name
        for key, value in kwargs.items():
            setattr(row, key, value)
    return row


def _material(db, code: str, name: str, **kwargs):
    row = _first(db, models.RawMaterial, code=code)
    if row is None:
        row = models.RawMaterial(code=code, name=name, **kwargs)
        db.add(row)
        db.flush()
    else:
        row.name = name
        for key, value in kwargs.items():
            setattr(row, key, value)
    return row


def _scrap(db, code: str, name: str, **kwargs):
    row = _first(db, models.ScrapType, code=code)
    if row is None:
        row = models.ScrapType(code=code, name=name, **kwargs)
        db.add(row)
        db.flush()
    else:
        row.name = name
        for key, value in kwargs.items():
            setattr(row, key, value)
    return row


def _plant_and_warehouse(db):
    plant = _first(db, models.Plant, code=DEMO["plant"])
    if plant is None:
        plant = models.Plant(
            code=DEMO["plant"],
            name="Shreeji Precision Plant",
            location="Pune, Maharashtra",
            active=True,
        )
        db.add(plant)
        db.flush()

    warehouse = _first(db, models.Warehouse, code=DEMO["warehouse"])
    if warehouse is None:
        warehouse = models.Warehouse(
            code=DEMO["warehouse"],
            name="Main Stores",
            plant_id=plant.id,
            active=True,
        )
        db.add(warehouse)
        db.flush()

    return plant, warehouse


def _workcenter(db, code: str, name: str, department: str, capacity: float, location: str):
    row = _first(db, models.Workcenter, code=code)
    if row is None:
        row = models.Workcenter(
            code=code,
            name=name,
            department=department,
            capacity_per_hour=capacity,
            status="Available",
            active=True,
            location=location,
        )
        db.add(row)
        db.flush()
    else:
        row.name = name
        row.department = department
        row.capacity_per_hour = capacity
        row.status = "Available"
        row.active = True
        row.location = location
    return row


def _employee(db, emp_code: str, name: str, designation: str, skill: str):
    row = _first(db, models.Employee, emp_code=emp_code)
    if row is None:
        row = models.Employee(
            emp_code=emp_code,
            name=name,
            department="Production",
            designation=designation,
            active=True,
        )
        db.add(row)
        db.flush()
    else:
        row.name = name
        row.department = "Production"
        row.designation = designation
        row.active = True

    skill_row = _first(
        db,
        models.EmployeeSkill,
        employee_id=row.id,
        skill=skill,
    )
    if skill_row is None:
        db.add(
            models.EmployeeSkill(
                employee_id=row.id,
                skill=skill,
                level=4,
                certified=True,
                active=True,
            )
        )
        db.flush()
    else:
        skill_row.level = 4
        skill_row.certified = True
        skill_row.active = True

    return row


def _opening_stock(db, *, kind, item, quantity, entry_date):
    existing = db.query(models.InventoryMovement).filter(
        models.InventoryMovement.reference == "DEMO-OPENING",
        models.InventoryMovement.item_kind == kind,
        models.InventoryMovement.item_id == item.id,
    ).first()
    if existing is None:
        apply_movement(
            db,
            kind=kind,
            item_id=item.id,
            movement_type=MovementType.IN,
            quantity=quantity,
            reference="DEMO-OPENING",
            reason="Demo opening stock",
            entry_date=entry_date,
            user_id="seed",
        )


def _bom(db, product, lines, scrap_type, scrap_percent):
    bom = _first(db, models.BillOfMaterials, product_id=product.id, version=1)
    if bom is None:
        bom = models.BillOfMaterials(
            product_id=product.id,
            version=1,
            active=True,
            expected_scrap_percent=scrap_percent,
            scrap_type_id=scrap_type.id,
        )
        db.add(bom)
        db.flush()

    bom.active = True
    bom.expected_scrap_percent = scrap_percent
    bom.scrap_type_id = scrap_type.id

    existing_by_material = {
        line.material_id: line
        for line in db.query(models.BomLine).filter_by(bom_id=bom.id).all()
    }
    for material, quantity in lines:
        row = existing_by_material.get(material.id)
        if row is None:
            db.add(
                models.BomLine(
                    bom_id=bom.id,
                    material_id=material.id,
                    quantity=quantity,
                )
            )
        else:
            row.quantity = quantity

    db.flush()
    return bom


def _routing(db, product, workcenter, skill, name):
    routing = _first(db, models.Routing, product_id=product.id, version=1)
    if routing is None:
        routing = models.Routing(
            product_id=product.id,
            version=1,
            active=True,
            name=name,
        )
        db.add(routing)
        db.flush()
    else:
        routing.active = True
        routing.name = name

    op = _first(
        db,
        models.RoutingOperation,
        routing_id=routing.id,
        sequence=1,
    )
    if op is None:
        op = models.RoutingOperation(
            routing_id=routing.id,
            sequence=1,
            code=f"OP-{product.code}",
            name="Primary Production Operation",
            workcenter_id=workcenter.id,
            required_skill=skill,
            setup_minutes=15,
            run_minutes_per_unit=0.5,
            active=True,
        )
        db.add(op)
    else:
        op.code = f"OP-{product.code}"
        op.name = "Primary Production Operation"
        op.workcenter_id = workcenter.id
        op.required_skill = skill
        op.setup_minutes = 15
        op.run_minutes_per_unit = 0.5
        op.active = True

    db.flush()
    return routing, op


def _supplier_mapping(db, supplier, material, rate):
    row = _first(
        db,
        models.SupplierProduct,
        supplier_id=supplier.id,
        product_id=material.id,
    )
    if row is None:
        db.add(
            models.SupplierProduct(
                supplier_id=supplier.id,
                product_id=material.id,
                supplier_code=material.code,
                purchase_rate=rate,
                minimum_order_qty=100,
                lead_time_days=7,
            )
        )
    else:
        row.supplier_code = material.code
        row.purchase_rate = rate
        row.minimum_order_qty = 100
        row.lead_time_days = 7


def _workcenter_material(db, workcenter, item_kind, item, operation_id=None):
    row = _first(
        db,
        models.WorkcenterMaterial,
        workcenter_id=workcenter.id,
        item_kind=item_kind,
        item_id=item.id,
    )
    if row is None:
        db.add(
            models.WorkcenterMaterial(
                workcenter_id=workcenter.id,
                item_kind=item_kind,
                item_id=item.id,
                operation_id=operation_id,
            )
        )
    else:
        row.operation_id = operation_id


def _purchase_flow(db, supplier, warehouse, material, today):
    po = _first(db, models.PurchaseOrder, po_no="PO-DEMO-001")
    if po is None:
        qty = 250
        rate = 210
        tax = round(qty * rate * 0.18, 2)
        po = models.PurchaseOrder(
            po_no="PO-DEMO-001",
            po_date=today - timedelta(days=4),
            expected_date=today - timedelta(days=1),
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            warehouse_id=warehouse.id,
            notes="Demo purchase order",
            status=models.PurchaseOrderStatus.received,
            sub_total=qty * rate,
            gst_total=tax,
            grand_total=qty * rate + tax,
            created_by="accounts",
        )
        po.lines = [
            models.PurchaseOrderLine(
                material_id=material.id,
                material_name=material.name,
                quantity=qty,
                rate=rate,
                gst_rate=18,
                received_quantity=qty,
                tax=tax,
                total=qty * rate + tax,
            )
        ]
        db.add(po)
        db.flush()

    grn = _first(db, models.GRN, grn_no="GRN-DEMO-001")
    if grn is None:
        grn = models.GRN(
            grn_no="GRN-DEMO-001",
            grn_date=today - timedelta(days=2),
            purchase_order_id=po.id,
            po_no=po.po_no,
            warehouse_id=warehouse.id,
        )
        grn.lines = [
            models.GRNLine(
                material_id=material.id,
                material_name=material.name,
                quantity=150,
                batch_no="RM-DEMO-001",
            )
        ]
        db.add(grn)
        db.flush()

    existing_movement = db.query(models.InventoryMovement).filter(
        models.InventoryMovement.reference == grn.grn_no,
        models.InventoryMovement.item_id == material.id,
        models.InventoryMovement.item_kind == ItemKind.material,
    ).first()
    if existing_movement is None:
        apply_movement(
            db,
            kind=ItemKind.material,
            item_id=material.id,
            movement_type=MovementType.IN,
            quantity=150,
            reference=grn.grn_no,
            reason="GRN receipt",
            entry_date=grn.grn_date,
            user_id="seed",
        )

    return po, grn


def _customer_po(db, customer, product, today):
    row = _first(db, models.CustomerPO, po_no="CPO-DEMO-001")
    if row is None:
        row = models.CustomerPO(
            po_no="CPO-DEMO-001",
            po_date=today - timedelta(days=3),
            customer_id=customer.id,
            customer_name=customer.name,
            delivery_date=today + timedelta(days=7),
        )
        row.lines = [
            models.CustomerPOLine(
                product_id=product.id,
                product_name=product.name,
                quantity=40,
                rate=260,
            )
        ]
        db.add(row)
        db.flush()
    return row


def _quotation(db, customer, product, today):
    row = _first(db, models.Quotation, quotation_no="QT-DEMO-001")
    if row is not None:
        return row

    tax = compute_line(
        quantity=30,
        rate=260,
        discount_percent=0,
        gst_rate=18,
        inter_state=False,
    )
    grand_total, round_value = round_off(tax.total)

    row = models.Quotation(
        quotation_no="QT-DEMO-001",
        quotation_date=today - timedelta(days=3),
        valid_until=today + timedelta(days=14),
        customer_id=customer.id,
        customer_name=customer.name,
        po_reference="CPO-DEMO-001",
        notes="Demo customer quotation",
        inter_state=0,
        sub_total=7800,
        discount_total=0,
        taxable_total=tax.taxable,
        cgst=tax.cgst,
        sgst=tax.sgst,
        igst=tax.igst,
        round_off=round_value,
        grand_total=grand_total,
        status=models.QuotationStatus.converted,
        created_by="admin",
    )
    row.lines = [
        models.QuotationLine(
            product_id=product.id,
            product_name=product.name,
            hsn=product.hsn,
            unit=product.unit,
            quantity=30,
            rate=260,
            discount_percent=0,
            gst_rate=18,
            taxable=tax.taxable,
            cgst=tax.cgst,
            sgst=tax.sgst,
            igst=tax.igst,
            total=tax.total,
        )
    ]
    db.add(row)
    db.flush()
    return row


def _sales_order(db, quotation, product, today):
    row = _first(db, models.SalesOrder, so_no="SO-DEMO-001")
    if row is not None:
        return row

    tax = compute_line(
        quantity=30,
        rate=260,
        discount_percent=0,
        gst_rate=18,
        inter_state=False,
    )
    row = models.SalesOrder(
        so_no="SO-DEMO-001",
        order_date=today - timedelta(days=2),
        delivery_date=today + timedelta(days=5),
        customer_id=quotation.customer_id,
        customer_name=quotation.customer_name,
        notes="Demo sales order",
        status=models.SalesOrderStatus.partially_delivered,
        quote_id=quotation.id,
        quote_no=quotation.quotation_no,
        taxable_total=tax.taxable,
        cgst=tax.cgst,
        sgst=tax.sgst,
        igst=tax.igst,
        grand_total=tax.total,
        created_by="admin",
    )
    row.lines = [
        models.SalesOrderLine(
            product_id=product.id,
            product_name=product.name,
            hsn=product.hsn,
            unit=product.unit,
            quantity=30,
            rate=260,
            discount_percent=0,
            gst_rate=18,
            taxable=tax.taxable,
            cgst=tax.cgst,
            sgst=tax.sgst,
            igst=tax.igst,
            total=tax.total,
            delivered_quantity=10,
        )
    ]
    db.add(row)
    db.flush()
    return row


def _delivery(db, sales_order, product, today):
    row = _first(db, models.DeliveryNote, delivery_no="DN-DEMO-001")
    if row is None:
        row = models.DeliveryNote(
            delivery_no="DN-DEMO-001",
            delivery_date=today - timedelta(days=1),
            sales_order_id=sales_order.id,
            so_no=sales_order.so_no,
            customer_id=sales_order.customer_id,
            customer_name=sales_order.customer_name,
            vehicle_no="MH12AB1234",
            driver_name="Suresh Patil",
            lr_number="LR-DEMO-001",
            remarks="Demo dispatch preparation",
            created_by="seed",
        )
        row.lines = [
            models.DeliveryLine(
                product_id=product.id,
                product_name=product.name,
                unit=product.unit,
                quantity=10,
            )
        ]
        db.add(row)
        db.flush()

    existing_movement = db.query(models.InventoryMovement).filter(
        models.InventoryMovement.reference == row.delivery_no,
        models.InventoryMovement.item_id == product.id,
        models.InventoryMovement.item_kind == ItemKind.product,
    ).first()
    if existing_movement is None:
        apply_movement(
            db,
            kind=ItemKind.product,
            item_id=product.id,
            movement_type=MovementType.OUT,
            quantity=10,
            reference=row.delivery_no,
            reason="Demo delivery",
            entry_date=row.delivery_date,
            user_id="seed",
        )

    return row


def _dispatch(db, delivery, today):
    row = _first(db, models.Dispatch, dispatch_no="DSP-DEMO-001")
    if row is None:
        row = models.Dispatch(
            dispatch_no="DSP-DEMO-001",
            dispatch_date=today - timedelta(days=1),
            delivery_id=delivery.id,
            delivery_no=delivery.delivery_no,
            customer_id=delivery.customer_id,
            customer_name=delivery.customer_name,
            transporter="BlueDart Industrial Logistics",
            vehicle_no=delivery.vehicle_no,
            driver_name=delivery.driver_name,
            driver_phone="9876543210",
            lr_number=delivery.lr_number,
            status=models.DispatchStatus.in_transit,
            created_by="seed",
        )
        db.add(row)
        db.flush()
    return row


def _invoice(db, customer, product, today):
    row = _first(db, models.Invoice, invoice_no="SPW-DEMO-001")
    if row is not None:
        return row

    tax = compute_line(
        quantity=10,
        rate=260,
        discount_percent=0,
        gst_rate=18,
        inter_state=False,
    )
    grand_total, round_value = round_off(tax.total)

    row = models.Invoice(
        invoice_no="SPW-DEMO-001",
        invoice_date=today,
        customer_id=customer.id,
        customer_name=customer.name,
        po_reference="CPO-DEMO-001",
        notes="Demo tax invoice",
        inter_state=0,
        sub_total=2600,
        discount_total=0,
        taxable_total=tax.taxable,
        cgst=tax.cgst,
        sgst=tax.sgst,
        igst=tax.igst,
        round_off=round_value,
        grand_total=grand_total,
        paid_amount=1000,
        balance_amount=round(grand_total - 1000, 2),
        status=models.InvoiceStatus.partial,
        created_by="accounts",
    )
    row.lines = [
        models.InvoiceLine(
            product_id=product.id,
            product_name=product.name,
            hsn=product.hsn,
            unit=product.unit,
            quantity=10,
            rate=260,
            discount_percent=0,
            gst_rate=18,
            taxable=tax.taxable,
            cgst=tax.cgst,
            sgst=tax.sgst,
            igst=tax.igst,
            total=tax.total,
        )
    ]
    db.add(row)
    db.flush()
    return row


def _production_flow(db, product, rm1, rm2, bom, routing, operation, workcenter, employee, scrap, today):
    order = _first(db, models.ProductionOrder, order_no="PO-PROD-DEMO-001")
    if order is None:
        order = models.ProductionOrder(
            order_no="PO-PROD-DEMO-001",
            order_date=today - timedelta(days=2),
            product_id=product.id,
            quantity=25,
            due_date=today,
            routing_id=routing.id,
            status="Completed",
            remarks="Demo production order",
        )
        db.add(order)
        db.flush()

        db.add(
            models.ProductionOrderOperation(
                production_order_id=order.id,
                operation_id=operation.id,
                sequence=operation.sequence,
                workcenter_id=workcenter.id,
                assigned_employee_id=employee.id,
                status="Completed",
                planned_qty=25,
                completed_qty=25,
            )
        )
        db.flush()

    entry = _first(db, models.ProductionEntry, batch_no="BATCH-DEMO-001")
    if entry is None:
        qty = 25
        planned_rm1 = bom.lines[0].quantity * qty
        planned_rm2 = bom.lines[1].quantity * qty

        entry = models.ProductionEntry(
            batch_no="BATCH-DEMO-001",
            entry_date=today - timedelta(days=1),
            product_id=product.id,
            quantity=qty,
            machine="CNC-01",
            workcenter_id=workcenter.id,
            routing_id=routing.id,
            operation_id=operation.id,
            production_order_id=order.id,
            employee_id=employee.id,
            operator=employee.name,
            shift="A",
            remarks="Demo production confirmation",
            actual_scrap=0.5,
            quality_status="Accepted",
            accepted_qty=24.5,
            rejected_qty=0.5,
            quality_remarks="Demo quality check",
            scrap_type_id=scrap.id,
            consumption=[
                models.ProductionConsumption(
                    material_id=rm1.id,
                    planned_quantity=planned_rm1,
                    quantity=planned_rm1,
                ),
                models.ProductionConsumption(
                    material_id=rm2.id,
                    planned_quantity=planned_rm2,
                    quantity=planned_rm2,
                ),
            ],
        )
        db.add(entry)
        db.flush()

        for material, consumed in ((rm1, planned_rm1), (rm2, planned_rm2)):
            apply_movement(
                db,
                kind=ItemKind.material,
                item_id=material.id,
                movement_type=MovementType.OUT,
                quantity=consumed,
                reference=entry.batch_no,
                reason="Demo production consumption",
                entry_date=entry.entry_date,
                user_id="seed",
            )

        apply_movement(
            db,
            kind=ItemKind.product,
            item_id=product.id,
            movement_type=MovementType.IN,
            quantity=qty,
            reference=entry.batch_no,
            reason="Demo production output",
            entry_date=entry.entry_date,
            user_id="seed",
        )

        apply_movement(
            db,
            kind=ItemKind.scrap,
            item_id=scrap.id,
            movement_type=MovementType.IN,
            quantity=0.5,
            reference=entry.batch_no,
            reason="Demo production scrap",
            entry_date=entry.entry_date,
            user_id="seed",
        )

    return order, entry


def _delete_demo_transactions(db):
    invoice = _first(db, models.Invoice, invoice_no="SPW-DEMO-001")
    if invoice is not None:
        db.delete(invoice)

    dispatch = _first(db, models.Dispatch, dispatch_no="DSP-DEMO-001")
    if dispatch is not None:
        db.delete(dispatch)

    delivery = _first(db, models.DeliveryNote, delivery_no="DN-DEMO-001")
    if delivery is not None:
        db.delete(delivery)

    so = _first(db, models.SalesOrder, so_no="SO-DEMO-001")
    if so is not None:
        db.delete(so)

    quotation = _first(db, models.Quotation, quotation_no="QT-DEMO-001")
    if quotation is not None:
        db.delete(quotation)

    customer_po = _first(db, models.CustomerPO, po_no="CPO-DEMO-001")
    if customer_po is not None:
        db.delete(customer_po)

    production = _first(db, models.ProductionEntry, batch_no="BATCH-DEMO-001")
    if production is not None:
        db.delete(production)

    production_order = _first(db, models.ProductionOrder, order_no="PO-PROD-DEMO-001")
    if production_order is not None:
        db.query(models.ProductionOrderOperation).filter_by(
            production_order_id=production_order.id
        ).delete(synchronize_session=False)
        db.delete(production_order)

    grn = _first(db, models.GRN, grn_no="GRN-DEMO-001")
    if grn is not None:
        db.delete(grn)

    po = _first(db, models.PurchaseOrder, po_no="PO-DEMO-001")
    if po is not None:
        db.delete(po)

    db.query(models.InventoryMovement).filter(
        models.InventoryMovement.reference.in_(
            ("DEMO-OPENING", "GRN-DEMO-001", "BATCH-DEMO-001", "DN-DEMO-001")
        )
    ).delete(synchronize_session=False)

    db.commit()


def run(reset_demo: bool = False) -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        if reset_demo:
            _delete_demo_transactions(db)

        for username, full_name, password, role in DEMO_USERS:
            user = _first(db, models.User, username=username)
            if user is None:
                db.add(
                    models.User(
                        username=username,
                        full_name=full_name,
                        password_hash=hash_password(password),
                        role=role,
                    )
                )
            else:
                user.full_name = full_name
                user.password_hash = hash_password(password)
                user.role = role
                user.active = True

        settings = db.get(models.CompanySettings, 1)
        if settings is None:
            settings = models.CompanySettings(id=1)
            db.add(settings)

        settings.name = "Shreeji Precision Works"
        settings.gst_number = "27ABCDE1234F1Z5"
        settings.address = "Pune, Maharashtra"
        settings.invoice_prefix = "SPW"
        settings.financial_year = "2026-2027"

        customer = _party(
            db,
            "customer",
            DEMO["customer_name"],
            gst_number="27AAACV1111A1Z5",
            phone="9820000011",
            email="purchase@vardhman.example",
            address="Bhosari MIDC, Pune",
        )
        supplier = _party(
            db,
            "supplier",
            DEMO["supplier_name"],
            gst_number="27AAACB2222B1Z4",
            phone="9820000022",
            email="sales@bharatsteel.example",
            address="Chakan MIDC, Pune",
        )

        fg1 = _product(
            db,
            DEMO["product_1"],
            "Machined Shaft 150mm",
            unit="PCS",
            hsn="8483",
            cost_price=180,
            selling_price=260,
            gst_rate=18,
            min_stock=100,
        )
        fg2 = _product(
            db,
            DEMO["product_2"],
            "Sheet Metal Bracket A",
            unit="PCS",
            hsn="7326",
            cost_price=95,
            selling_price=145,
            gst_rate=18,
            min_stock=80,
        )
        rm1 = _material(
            db,
            DEMO["material_1"],
            "Aluminium Rod 25mm",
            unit="KG",
            cost=210,
            min_stock=200,
        )
        rm2 = _material(
            db,
            DEMO["material_2"],
            "MS Sheet 2mm",
            unit="KG",
            cost=68,
            min_stock=300,
        )
        scrap1 = _scrap(
            db,
            DEMO["scrap_1"],
            "Aluminium Turnings",
            unit="KG",
            selling_rate=95,
            stock=0,
            min_stock=10,
            active=True,
        )
        scrap2 = _scrap(
            db,
            DEMO["scrap_2"],
            "MS Offcuts",
            unit="KG",
            selling_rate=32,
            stock=0,
            min_stock=10,
            active=True,
        )

        _, warehouse = _plant_and_warehouse(db)

        wc_cnc = _workcenter(
            db,
            DEMO["workcenter_1"],
            "CNC Machining Cell",
            "Machining",
            8,
            "Shop Floor A",
        )
        wc_fab = _workcenter(
            db,
            DEMO["workcenter_2"],
            "Fabrication Cell",
            "Fabrication",
            10,
            "Shop Floor B",
        )

        emp1 = _employee(
            db,
            DEMO["employee_1"],
            "Imran Shaikh",
            "CNC Operator",
            "CNC Machining",
        )
        _employee(
            db,
            DEMO["employee_2"],
            "Neha Jadhav",
            "Fabrication Operator",
            "Fabrication",
        )

        bom1 = _bom(
            db,
            fg1,
            [(rm1, 0.8), (rm2, 0.1)],
            scrap1,
            2,
        )
        _bom(
            db,
            fg2,
            [(rm2, 1.2)],
            scrap2,
            1.5,
        )

        routing1, op1 = _routing(
            db,
            fg1,
            wc_cnc,
            "CNC Machining",
            "Machined Shaft Routing",
        )
        routing2, op2 = _routing(
            db,
            fg2,
            wc_fab,
            "Fabrication",
            "Bracket Fabrication Routing",
        )

        for wc, kind, item, operation in (
            (wc_cnc, "RM", rm1, op1.id),
            (wc_cnc, "RM", rm2, op1.id),
            (wc_cnc, "FG", fg1, op1.id),
            (wc_fab, "RM", rm2, op2.id),
            (wc_fab, "FG", fg2, op2.id),
        ):
            _workcenter_material(db, wc, kind, item, operation)

        _supplier_mapping(db, supplier, rm1, 210)
        _supplier_mapping(db, supplier, rm2, 68)

        today = date.today()
        opening = today - timedelta(days=14)

        _opening_stock(db, kind=ItemKind.material, item=rm1, quantity=1200, entry_date=opening)
        _opening_stock(db, kind=ItemKind.material, item=rm2, quantity=800, entry_date=opening)
        _opening_stock(db, kind=ItemKind.product, item=fg1, quantity=120, entry_date=opening)
        _opening_stock(db, kind=ItemKind.product, item=fg2, quantity=75, entry_date=opening)

        _purchase_flow(db, supplier, warehouse, rm1, today)
        _production_flow(
            db,
            fg1,
            rm1,
            rm2,
            bom1,
            routing1,
            op1,
            wc_cnc,
            emp1,
            scrap1,
            today,
        )

        _customer_po(db, customer, fg1, today)
        quotation = _quotation(db, customer, fg1, today)
        sales_order = _sales_order(db, quotation, fg1, today)
        delivery = _delivery(db, sales_order, fg1, today)
        _dispatch(db, delivery, today)
        _invoice(db, customer, fg1, today)

        quotation.status = models.QuotationStatus.converted
        sales_order.status = models.SalesOrderStatus.partially_delivered

        db.commit()

        print("Demo data ready.")
        print("Admin:    admin / admin123")
        print("Accounts: accounts / accounts123")
        print("Operator: operator / operator123")
        print("Flow:")
        print("  PO-DEMO-001 -> GRN-DEMO-001")
        print("  BOM + routing -> WC-CNC -> EMP-001 -> BATCH-DEMO-001")
        print("  CPO-DEMO-001 -> QT-DEMO-001 -> SO-DEMO-001 -> DN-DEMO-001 -> DSP-DEMO-001")
        print("  SPW-DEMO-001 -> partial payment state")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed MiniTally demo data.")
    parser.add_argument("--reset-demo", action="store_true")
    args = parser.parse_args()
    run(reset_demo=args.reset_demo)
