"""Regression tests for employee deactivation and unfinished production work."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.api.routes.hr import _employee_has_open_production_assignments


def _session():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    return engine, Session(engine)


def test_employee_with_unfinished_production_assignment_is_detected():
    engine, db = _session()
    try:
        employee = models.Employee(
            id="employee-1", emp_code="EMP-001", name="Test Operator",
            employee_type="shop_floor", department="Production",
            designation="Operator", active=True,
        )
        operation = models.ProductionOrderOperation(
            id="operation-1", production_order_id="order-1",
            operation_id="routing-operation-1", sequence=1,
            workcenter_id="workcenter-1", assigned_employee_id=employee.id,
            status="Assigned", planned_qty=10, completed_qty=4,
        )
        db.add_all([employee, operation])
        db.commit()
        assert _employee_has_open_production_assignments(db, employee.id) is True
    finally:
        db.close()
        engine.dispose()


def test_fully_completed_production_assignment_does_not_block_deactivation():
    engine, db = _session()
    try:
        employee = models.Employee(
            id="employee-2", emp_code="EMP-002", name="Completed Operator",
            employee_type="shop_floor", department="Production",
            designation="Operator", active=True,
        )
        operation = models.ProductionOrderOperation(
            id="operation-2", production_order_id="order-2",
            operation_id="routing-operation-2", sequence=1,
            workcenter_id="workcenter-2", assigned_employee_id=employee.id,
            status="Completed", planned_qty=10, completed_qty=10,
        )
        db.add_all([employee, operation])
        db.commit()
        assert _employee_has_open_production_assignments(db, employee.id) is False
    finally:
        db.close()
        engine.dispose()
