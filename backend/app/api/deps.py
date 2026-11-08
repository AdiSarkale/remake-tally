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
    """Resolve a stable feature name from the route resource, not an ID/action segment."""
    parts = [part for part in request.url.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "api" and parts[1].startswith("v"):
        parts = parts[2:]
    if not parts:
        feature = "overview"
    else:
        module_resource = parts[0].replace("-", "_")
        child_resource = parts[1] if len(parts) > 1 else ""
        # These routers represent a single feature at their root. Their
        # remaining path components are IDs or utility endpoints.
        root_features = {
            "bom", "customer_pos", "delivery", "deliveries", "dispatches",
            "quotations", "sales_orders", "scrap", "users", "settings",
            "audit", "dashboard", "approvals",
        }
        utility_segments = {"lookup", "next-number", "from-quotation", "me"}
        if module_resource in root_features or not child_resource:
            feature = module_resource
        elif child_resource.startswith("{") or child_resource in utility_segments:
            feature = module_resource
        else:
            feature = child_resource.replace("-", "_")
    action_segment = parts[-1] if parts else ""
    if action_segment in {"prepare", "approve", "finalize", "lock", "reverse", "cancel", "submit", "post"}:
        action = action_segment
    else:
        action = {
            "GET": "read", "POST": "create", "PUT": "update",
            "PATCH": "update", "DELETE": "delete",
        }.get(request.method.upper(), "read")
    return feature, action


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
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing explicit permission: {module}.{feature}.{action}")


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
    """Require a feature/action grant in any one of the declared modules."""
    def guard(
        request: Request,
        user: models.User = Depends(current_user),
        db: Session = Depends(tenant_session_db),
    ) -> models.User:
        denied = []
        for module in areas:
            try:
                _check_module_route_grant(db, user, module, request)
                return user
            except HTTPException as exc:
                denied.append(exc)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access this route through any of its authorized modules",
        )
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


def employee_scope_ids(
    db: Session, user: models.User, module: str, feature: str, action: str,
) -> list[str] | None:
    """Return employee IDs for exact scoped grants; None means tenant-wide."""
    exact_grants = db.query(RolePermissionGrant).filter_by(
        role=user.role.value, module=module, feature=feature, action=action,
    ).all()
    if not exact_grants:
        wildcard = db.query(RolePermissionGrant).filter_by(
            role=user.role.value, module=module, feature="*", action="*",
            data_scope="tenant", allowed=True,
        ).first()
        return None if wildcard else []

    allowed_scopes = {grant.data_scope for grant in exact_grants if grant.allowed}
    if "tenant" in allowed_scopes:
        return None
    if not allowed_scopes:
        return []

    link = db.query(EmployeeUserLink).filter_by(user_id=user.id).first()
    if link is None:
        return []
    employees = db.query(models.Employee).all()
    employee_by_id = {employee.id: employee for employee in employees}
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
    actor = employee_by_id.get(link.employee_id)
    if actor is None:
        return []
    actor_assignment = current.get(link.employee_id)
    result: set[str] = set()

    if "self" in allowed_scopes:
        result.add(link.employee_id)
    if "department" in allowed_scopes:
        actor_department = actor_assignment.department if actor_assignment else actor.department
        if actor_department:
            for employee in employees:
                assignment = current.get(employee.id)
                department = assignment.department if assignment else employee.department
                if department and department.casefold() == actor_department.casefold():
                    result.add(employee.id)
    if "branch" in allowed_scopes and actor_assignment and actor_assignment.branch_id:
        result.update(
            row.employee_id for row in assignments
            if row.branch_id == actor_assignment.branch_id
        )
    if "team" in allowed_scopes:
        descendants: set[str] = {link.employee_id}
        frontier = {link.employee_id}
        while frontier:
            children = {
                row.employee_id for row in assignments
                if row.manager_employee_id in frontier and row.employee_id not in descendants
            }
            descendants.update(children)
            frontier = children
        result.update(descendants)
    return sorted(result)


def apply_employee_scope(
    query, db: Session, user: models.User, module: str, feature: str, action: str,
):
    """Apply employee scope to an Employee-backed query, failing closed."""
    ids = employee_scope_ids(db, user, module, feature, action)
    if ids is None:
        return query
    return query.filter(models.Employee.id.in_(ids))


def require_employee_scope_grant(
    db: Session, user: models.User, module: str, feature: str, action: str,
) -> None:
    grants = db.query(RolePermissionGrant).filter_by(
        role=user.role.value, module=module, feature=feature, action=action,
    ).all()
    if grants:
        if any(grant.allowed for grant in grants):
            return
        raise HTTPException(status_code=403, detail=f"Permission denied: {module}.{feature}.{action}")
    wildcard = db.query(RolePermissionGrant).filter_by(
        role=user.role.value, module=module, feature="*", action="*",
        data_scope="tenant", allowed=True,
    ).first()
    if wildcard is None:
        raise HTTPException(status_code=403, detail=f"Missing permission: {module}.{feature}.{action}")
