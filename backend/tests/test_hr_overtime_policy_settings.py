"""Tests for tenant HR Admin overtime policy settings (P0.1-09 slice 01)."""
import inspect
from datetime import date

import pytest
from fastapi import HTTPException
from fastapi.params import Depends as DependsParam
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.api.routes import hr_overtime_policies as route


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def user(db):
    row = models.User(
        id="ot-admin", username="ot-admin", full_name="OT Admin",
        password_hash="test", role=models.Role.admin, active=True,
        must_change_password=False,
    )
    db.add(row)
    db.commit()
    return row


def _grant(db, action):
    db.add(models.RolePermissionGrant(
        role="Admin", module="hr", feature="overtime_policies",
        action=action, data_scope="tenant", allowed=True, updated_by="test",
    ))
    db.commit()


def _payload(code="OT-POL-1", start=date(2026, 12, 1), end=None, scope=None, config=None):
    return route.OvertimePolicyPayload(
        version_code=code,
        effective_from=start,
        effective_to=end,
        scope=scope or {},
        configuration=config or {},
    )


def _valid_config():
    return {
        "workday_mode": "beyond_scheduled_net",
        "weekly_off_mode": "actual_work",
        "holiday_mode": "actual_work",
        "eligibility": {
            "pre_shift": False,
            "post_shift": True,
            "require_complete_attendance": True,
            "minimum_minutes": 30,
            "maximum_minutes_per_day": 240,
        },
        "rounding": {"method": "nearest", "increment_minutes": 15},
        "compensation": {
            "method": "both",
            "credit_minutes_per_source_minute": 1.0,
        },
    }


def test_policy_routes_require_exact_view_manage_publish_grants(db, user):
    endpoints = (
        (route.list_policies, "view"),
        (route.create_policy, "manage"),
        (route.update_policy, "manage"),
        (route.publish_policy, "publish"),
        (route.retire_policy, "publish"),
    )
    for endpoint, action in endpoints:
        dependency = inspect.signature(endpoint).parameters["user"].default
        assert isinstance(dependency, DependsParam)
        with pytest.raises(HTTPException) as denied:
            dependency.dependency(user=user, db=db)
        assert denied.value.status_code == 403
        _grant(db, action)
        assert dependency.dependency(user=user, db=db) is user


def test_policy_draft_publish_and_retire_are_versioned_and_audited(db, user):
    for action in ("view", "manage", "publish"):
        _grant(db, action)
    created = route.create_policy(_payload(config=_valid_config()), user, db)
    assert created["status"] == "draft"
    assert created["configuration"]["rounding"]["increment_minutes"] == 15

    published = route.publish_policy(created["id"], user, db)
    assert published["status"] == "published"
    assert published["published_by"] == user.username
    assert published["published_at"] is not None

    with pytest.raises(HTTPException) as immutable:
        route.update_policy(created["id"], _payload(code="changed", config=_valid_config()), user, db)
    assert immutable.value.status_code == 409

    retired = route.retire_policy(created["id"], user, db)
    assert retired["status"] == "retired"
    assert route.list_policies(False, user, db) == []


def test_publish_requires_explicit_complete_policy_and_no_same_scope_overlap(db, user):
    _grant(db, "manage")
    _grant(db, "publish")
    incomplete = route.create_policy(_payload(config={}), user, db)
    with pytest.raises(HTTPException) as missing:
        route.publish_policy(incomplete["id"], user, db)
    assert missing.value.status_code == 422

    first = route.create_policy(_payload(code="OT-A", config=_valid_config()), user, db)
    route.publish_policy(first["id"], user, db)
    overlap = route.create_policy(_payload(code="OT-B", config=_valid_config()), user, db)
    with pytest.raises(HTTPException) as conflict:
        route.publish_policy(overlap["id"], user, db)
    assert conflict.value.status_code == 409

    distinct_scope = route.create_policy(
        _payload(code="OT-C", scope={"employee_types": ["contract"]}, config=_valid_config()),
        user, db,
    )
    assert route.publish_policy(distinct_scope["id"], user, db)["status"] == "published"


def test_policy_scope_and_rounding_validation_fail_closed(db, user):
    _grant(db, "manage")
    _grant(db, "publish")
    invalid_scope = route.create_policy(
        _payload(code="OT-SCOPE", scope={"day_types": ["weekend"]}, config=_valid_config()),
        user, db,
    )
    with pytest.raises(HTTPException) as scope_error:
        route.publish_policy(invalid_scope["id"], user, db)
    assert scope_error.value.status_code == 422

    bad_rounding = _valid_config()
    bad_rounding["rounding"] = {"method": "nearest", "increment_minutes": 0}
    invalid_config = route.create_policy(_payload(code="OT-ROUND", config=bad_rounding), user, db)
    with pytest.raises(HTTPException) as rounding_error:
        route.publish_policy(invalid_config["id"], user, db)
    assert rounding_error.value.status_code == 422
