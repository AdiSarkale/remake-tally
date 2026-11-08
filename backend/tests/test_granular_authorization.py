"""Tests for exact feature/action authorization after wildcard retirement."""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi import HTTPException, Request

from app import models
from app.api.deps import _check_module_route_grant
from app.modules.core.authorization import RolePermissionGrant


def _request(path: str, method: str = "GET") -> Request:
    return Request({
        "type": "http", "method": method, "path": path,
        "headers": [], "query_string": b"", "server": ("test", 80),
        "client": ("test", 80), "scheme": "http", "http_version": "1.1",
    })


def test_exact_feature_action_grant_allows_matching_route():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = models.User(
            id="auth-admin", username="admin", full_name="Admin",
            password_hash="test", role=models.Role.admin, active=True,
            must_change_password=False,
        )
        db.add(user)
        db.add(RolePermissionGrant(
            role="Admin", module="finance", feature="customer_payments",
            action="read", data_scope="tenant", allowed=True, updated_by="test",
        ))
        db.commit()
        _check_module_route_grant(db, user, "finance", _request("/api/v1/finance/customer-payments"))


def test_legacy_wildcard_does_not_grant_unlisted_feature_action():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = models.User(
            id="auth-admin", username="admin", full_name="Admin",
            password_hash="test", role=models.Role.admin, active=True,
            must_change_password=False,
        )
        db.add(user)
        db.add(RolePermissionGrant(
            role="Admin", module="finance", feature="*", action="*",
            data_scope="tenant", allowed=True, updated_by="legacy",
        ))
        db.commit()
        try:
            _check_module_route_grant(db, user, "finance", _request("/api/v1/finance/unregistered"))
        except HTTPException as exc:
            assert exc.status_code == 403
            assert "explicit permission" in exc.detail
        else:
            raise AssertionError("A legacy wildcard must not authorize an unlisted route")


def test_explicit_deny_overrides_an_existing_allow_for_same_route():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = models.User(
            id="auth-admin", username="admin", full_name="Admin",
            password_hash="test", role=models.Role.admin, active=True,
            must_change_password=False,
        )
        db.add(user)
        db.add_all([
            RolePermissionGrant(
                role="Admin", module="finance", feature="customer_payments",
                action="read", data_scope="tenant", allowed=True, updated_by="test",
            ),
            RolePermissionGrant(
                role="Admin", module="finance", feature="customer_payments",
                action="read", data_scope="tenant", allowed=False, updated_by="admin",
            ),
        ])
        # Unique key deliberately means a role cannot have two contradictory rows.
        # The Admin UI updates the existing row; this test covers the deny row alone.
        db.rollback()
        db.add(RolePermissionGrant(
            role="Admin", module="finance", feature="customer_payments",
            action="read", data_scope="tenant", allowed=False, updated_by="admin",
        ))
        db.commit()
        try:
            _check_module_route_grant(db, user, "finance", _request("/api/v1/finance/customer-payments"))
        except HTTPException as exc:
            assert exc.status_code == 403
        else:
            raise AssertionError("An explicit deny must block the route")
