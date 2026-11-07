"""Tests for the shared Core audit-event service."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.modules.core.audit import log_audit


def test_audit_event_is_staged_in_the_callers_transaction():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    db = Session(engine)
    try:
        log_audit(db, "hr.admin", "DEACTIVATE", "employee", "EMP-001")
        db.flush()

        events = db.query(models.AuditLog).all()
        assert len(events) == 1
        assert events[0].username == "hr.admin"
        assert events[0].action == "DEACTIVATE"
        assert events[0].entity == "employee"
        assert events[0].detail == "EMP-001"
    finally:
        db.close()
        engine.dispose()
