from datetime import date

from app import models


def create_routing(client, headers, product_id, workcenter_id, required_skill="WELDING"):
    return client.post(
        "/api/v1/manufacturing/routings",
        headers=headers,
        json={
            "product_id": product_id,
            "version": 1,
            "name": "Default Routing",
            "active": True,
            "operations": [
                {
                    "sequence": 1,
                    "code": "OP10",
                    "name": "Assembly",
                    "workcenter_id": workcenter_id,
                    "required_skill": required_skill,
                    "setup_minutes": 5,
                    "run_minutes_per_unit": 1,
                    "active": True,
                }
            ],
        },
    )


def test_manufacturing_requires_auth(client):
    assert client.get("/api/v1/manufacturing/workcenters").status_code == 401


def test_workcenter_crud_and_material_assignment(client, auth_headers, product, material, workcenter):
    response = client.post(
        "/api/v1/manufacturing/workcenters",
        headers=auth_headers,
        json={
            "code": "WC-TEST",
            "name": "Test Cell",
            "department": "Production",
            "capacity_per_hour": 120,
            "status": "Available",
            "active": True,
            "location": "Plant 1",
            "materials": [
                {"item_kind": "RM", "item_id": material.id},
                {"item_kind": "FG", "item_id": product.id},
            ],
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["code"] == "WC-TEST"
    assert {x["item_kind"] for x in data["materials"]} == {"RM", "FG"}

    listed = client.get("/api/v1/manufacturing/workcenters", headers=auth_headers)
    assert listed.status_code == 200
    assert any(x["code"] == "WC-TEST" for x in listed.json())


def test_routing_requires_existing_workcenter_and_enforces_unique_sequence(
    client, auth_headers, product, workcenter
):
    bad = client.post(
        "/api/v1/manufacturing/routings",
        headers=auth_headers,
        json={
            "product_id": product.id,
            "version": 1,
            "name": "Bad",
            "active": True,
            "operations": [
                {"sequence": 1, "name": "A", "workcenter_id": "missing"},
            ],
        },
    )
    assert bad.status_code == 400
    assert "Workcenter" in bad.text

    duplicate = client.post(
        "/api/v1/manufacturing/routings",
        headers=auth_headers,
        json={
            "product_id": product.id,
            "version": 1,
            "name": "Bad",
            "active": True,
            "operations": [
                {"sequence": 1, "name": "A", "workcenter_id": workcenter.id},
                {"sequence": 1, "name": "B", "workcenter_id": workcenter.id},
            ],
        },
    )
    assert duplicate.status_code == 400
    assert "sequence" in duplicate.text


def test_employee_skill_auto_assignment_and_manual_skill_validation(
    client, auth_headers, db, product, workcenter
):
    employee = client.post(
        "/api/v1/manufacturing/employees",
        headers=auth_headers,
        json={
            "emp_code": "EMP-TEST",
            "name": "Skilled Operator",
            "department": "Production",
            "designation": "Operator",
            "active": True,
        },
    )
    assert employee.status_code == 201, employee.text
    employee_id = employee.json()["id"]

    skill = client.post(
        f"/api/v1/manufacturing/employees/{employee_id}/skills",
        headers=auth_headers,
        json={"skill": "WELDING", "level": 5, "certified": True, "active": True},
    )
    assert skill.status_code == 201, skill.text

    routing = create_routing(client, auth_headers, product.id, workcenter.id)
    assert routing.status_code == 201, routing.text

    order = client.post(
        "/api/v1/manufacturing/production-orders",
        headers=auth_headers,
        json={
            "order_date": str(date.today()),
            "product_id": product.id,
            "quantity": 10,
            "routing_id": routing.json()["id"],
        },
    )
    assert order.status_code == 201, order.text
    assert order.json()["operations"][0]["assigned_employee_id"] == employee_id
    assert order.json()["operations"][0]["status"] == "Assigned"

    unskilled = client.post(
        "/api/v1/manufacturing/employees",
        headers=auth_headers,
        json={
            "emp_code": "EMP-UNSKILLED",
            "name": "Unskilled",
            "department": "Production",
            "designation": "Operator",
            "active": True,
        },
    )
    assert unskilled.status_code == 201
    assignment = client.patch(
        f"/api/v1/manufacturing/production-orders/{order.json()['id']}/operations/{order.json()['operations'][0]['id']}/assignment",
        headers=auth_headers,
        json={"employee_id": unskilled.json()["id"]},
    )
    assert assignment.status_code == 400
    assert "required routing skill" in assignment.text


def test_quality_update_rejects_over_allocation(client, auth_headers, db, product):
    entry = models.ProductionEntry(
        batch_no="BATCH-QA-001",
        entry_date=date.today(),
        product_id=product.id,
        quantity=10,
        machine="",
        quality_status="Pending",
        accepted_qty=10,
        rejected_qty=0,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    invalid = client.patch(
        f"/api/v1/manufacturing/production/{entry.id}/quality",
        headers=auth_headers,
        json={
            "status": "Accepted",
            "accepted_qty": 8,
            "rejected_qty": 3,
            "remarks": "Invalid total",
        },
    )
    assert invalid.status_code == 400
    assert "cannot exceed produced quantity" in invalid.text

    valid = client.patch(
        f"/api/v1/manufacturing/production/{entry.id}/quality",
        headers=auth_headers,
        json={
            "status": "Accepted with Deviation",
            "accepted_qty": 8,
            "rejected_qty": 2,
            "remarks": "Reworked",
        },
    )
    assert valid.status_code == 200
    assert valid.json()["accepted_qty"] == 8
    assert valid.json()["rejected_qty"] == 2


def test_manufacturing_report_aggregates_material_variance(client, auth_headers, db, product, workcenter):
    entry = models.ProductionEntry(
        batch_no="BATCH-RPT-001",
        entry_date=date.today(),
        product_id=product.id,
        quantity=10,
        machine="",
        workcenter_id=workcenter.id,
        actual_scrap=1,
    )
    db.add(entry)
    db.flush()
    db.add_all(
        [
            models.ProductionConsumption(
                production_id=entry.id,
                material_id="rm-1",
                planned_quantity=5,
                quantity=6,
            ),
            models.ProductionConsumption(
                production_id=entry.id,
                material_id="rm-2",
                planned_quantity=3,
                quantity=2,
            ),
        ]
    )
    db.commit()

    report = client.get("/api/v1/manufacturing/reports/production", headers=auth_headers)
    assert report.status_code == 200, report.text
    data = report.json()
    assert data["production_qty"] == 10
    assert data["scrap_qty"] == 1
    assert data["planned_material_qty"] == 8
    assert data["actual_material_qty"] == 8
    assert data["material_variance"] == 0
    assert data["by_workcenter"][0]["workcenter_id"] == workcenter.id
    assert data["by_workcenter"][0]["material_variance"] == 0
