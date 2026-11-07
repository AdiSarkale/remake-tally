"""Auth dependencies: current user + role guard + tenant DB context."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.modules.core.authorization import EmployeeUserLink, RolePermissionGrant
from app.modules.hr.models import EmployeeOrgAssignment

from app import models
from app.db.control_models import TenantCompany
from app.core.security import decode_access_token
from app.db.control import get_control_db
from app.db.tenant import get_tenant_db
from app.db.session import get_db as tenant_session_db
from app.services.company_context import resolve_company_from_token

bearer = HTTPBearer(auto_error=False)

ROLE_PERMISSIONS: dict[models.Role, set[str]] = {
    models.Role.admin: {"masters", "inventory", "production", "scrap", "sales", "finance", "settings", "reports", "approvals", "purchase_requests", "hr"},
    models.Role.accountant: {"masters", "inventory", "sales", "reports", "approvals", "purchase_requests"},
    models.Role.operator: {"production", "scrap", "inventory", "approvals", "purchase_requests"},
    # HR is intentionally isolated from finance, settings, and system administration.
    models.Role.hr: {"hr"},
}


def current_company(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    control_db: Session = Depends(get_control_db),
) -> TenantCompany:
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    _, company = resolve_company_from_token(creds.credentials, control_db)
    return company


def get_db(
    company: TenantCompany = Depends(current_company),
):
    """Compatibility name used by ERP routes; always resolves to tenant DB."""
    db = get_tenant_db(company)
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    company: TenantCompany = Depends(current_company),
) -> models.User:
    db = get_tenant_db(company)
    try:
        user = db.query(models.User).filter(models.User.username == decode_access_token(creds.credentials).get("sub")).first()  # type: ignore[union-attr]
        if user is None or not user.active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
        if user.must_change_password and request.url.path not in {"/api/v1/auth/me", "/api/v1/users/me/change-password"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password change required before continuing")
        return user
    finally:
        db.close()


def _route_feature_action(request: Request) -> tuple[str, str]:
    parts = [part for part in request.url.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "api" and parts[1].startswith("v"):
        parts = parts[2:]
    resource = parts[1] if len(parts) > 1 else "overview"
    if resource.startswith("{"):
        resource = "overview"
    action_segment = parts[-1] if parts else ""
    if action_segment in {"prepare", "approve", "finalize", "lock", "reverse", "cancel", "submit", "post"}:
        action = action_segment
    else:
        action = {
            "GET": "read", "POST": "create", "PUT": "update",
            "PATCH": "update", "DELETE": "delete",
        }.get(request.method.upper(), "read")
    return resource.replace("-", "_"), action


def _check_module_route_grant(db: Session, user: models.User, module: str, request: Request) -> None:
    feature, action = _route_feature_action(request)
    exact = db.query(RolePermissionGrant).filter_by(
        role=user.role.value, module=module, feature=feature,
        action=action, data_scope="tenant",
    ).first()
    if exact is not None:
        if not exact.allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission denied: {module}.{feature}.{action}")
        return
    wildcard = db.query(RolePermissionGrant).filter_by(
        role=user.role.value, module=module, feature="*", action="*",
        data_scope="tenant", allowed=True,
    ).first()
    if wildcard is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permission: {module}.{feature}.{action}")


def require_area(area: str):
    """Require module access plus a persisted feature/action grant for the route."""
    def guard(
        request: Request,
        user: models.User = Depends(current_user),
        db: Session = Depends(tenant_session_db),
    ) -> models.User:
        _check_module_route_grant(db, user, area, request)
        return user
    return guard


def require_any_area(*areas: str):
    """Require a persisted feature/action grant for the matching route module."""
    prefix_module = {
        "hr": "hr", "manufacturing": "production", "production": "production",
        "finance": "finance", "inventory": "inventory", "scrap": "scrap",
        "sales": "sales", "sales-orders": "sales", "quotations": "sales",
        "dispatches": "sales", "deliveries": "sales", "purchasing": "purchase_requests",
        "purchase-requests": "purchase_requests", "masters": "masters",
        "settings": "settings", "reports": "reports", "approvals": "approvals",
    }
    def guard(
        request: Request,
        user: models.User = Depends(current_user),
        db: Session = Depends(tenant_session_db),
    ) -> models.User:
        parts = [part for part in request.url.path.split("/") if part]
        prefix = parts[2] if len(parts) >= 3 and parts[0] == "api" else (parts[0] if parts else "")
        module = prefix_module.get(prefix)
        if module not in areas:
            # Preserve a strict deny if a route cannot be mapped to one of its declared modules.
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Route is not mapped to an authorized module")
        _check_module_route_grant(db, user, module, request)
        return user
    return guard



def require_permission(module: str, feature: str, action: str, data_scope: str = "tenant"):
    """Require an explicit role grant for one module/feature/action/data-scope tuple."""
    def guard(
        user: models.User = Depends(current_user),
        db: Session = Depends(tenant_session_db),
    ) -> models.User:
        grant = db.query(RolePermissionGrant).filter_by(
            role=user.role.value,
            module=module,
            feature=feature,
            action=action,
            data_scope=data_scope,
            allowed=True,
        ).first()
        if grant is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {module}.{feature}.{action} ({data_scope})",
            )
        return user
    return guard


def enforce_employee_data_scope(
    db: Session,
    user: models.User,
    employee_id: str,
    data_scope: str,
) -> None:
    """Enforce only scopes backed by persisted employee relationships."""
    if data_scope == "tenant":
        return
    actor_link = db.query(EmployeeUserLink).filter_by(user_id=user.id).first()
    if actor_link is None:
        raise HTTPException(status_code=403, detail="Your login is not linked to an employee record")
    if data_scope == "self":
        if actor_link.employee_id != employee_id:
            raise HTTPException(status_code=403, detail="Employee self-service access is limited to your own record")
        return
    actor = db.get(models.Employee, actor_link.employee_id)
    target = db.get(models.Employee, employee_id)
    if actor is None or target is None:
        raise HTTPException(status_code=403, detail="Employee relationship is unavailable")
    settings = db.get(models.HRPayrollSettings, 1)
    try:
        today = datetime.now(ZoneInfo(settings.timezone if settings else "Asia/Kolkata")).date()
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=500, detail="Tenant timezone is invalid") from exc
    assignments = db.query(EmployeeOrgAssignment).filter(
        EmployeeOrgAssignment.valid_from <= today,
        (EmployeeOrgAssignment.valid_to.is_(None) | (EmployeeOrgAssignment.valid_to >= today)),
    ).all()
    current = {row.employee_id: row for row in assignments}
    actor_assignment = current.get(actor_link.employee_id)
    target_assignment = current.get(employee_id)
    if data_scope == "department":
        actor_department = actor_assignment.department if actor_assignment else actor.department
        target_department = target_assignment.department if target_assignment else target.department
        if not actor_department or actor_department != target_department:
            raise HTTPException(status_code=403, detail="Department scope does not include this employee")
        return
    if data_scope == "branch":
        if actor_assignment is None or target_assignment is None or not actor_assignment.branch_id or actor_assignment.branch_id != target_assignment.branch_id:
            raise HTTPException(status_code=403, detail="Branch scope does not include this employee")
        return
    if data_scope == "team":
        if actor_link.employee_id == employee_id:
            return
        descendants: set[str] = set()
        frontier = {actor_link.employee_id}
        while frontier:
            children = {
                row.employee_id for row in assignments
                if row.manager_employee_id in frontier and row.employee_id not in descendants
            }
            if employee_id in children:
                return
            descendants.update(children)
            frontier = children
        raise HTTPException(status_code=403, detail="Team scope is limited to your direct and indirect reports")
    raise HTTPException(status_code=403, detail="This data scope is not supported by the current employee relationships")
