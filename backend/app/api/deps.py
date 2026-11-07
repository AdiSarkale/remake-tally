"""Auth dependencies: current user + role guard + tenant DB context."""

from __future__ import annotations

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


def require_area(area: str):
    """Require a persisted module access grant for the authenticated role."""
    def guard(
        user: models.User = Depends(current_user),
        db: Session = Depends(tenant_session_db),
    ) -> models.User:
        # Direct calls are used only by legacy unit tests; HTTP requests always
        # receive a real tenant session from FastAPI's dependency injection.
        if not isinstance(db, Session):
            if area not in ROLE_PERMISSIONS[user.role]:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{user.role.value} cannot access {area}")
            return user
        grant = db.query(RolePermissionGrant).filter_by(
            role=user.role.value, module=area, feature="access",
            action="read", data_scope="tenant", allowed=True,
        ).first()
        if grant is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{user.role.value} cannot access {area}")
        return user
    return guard


def require_any_area(*areas: str):
    """Require at least one persisted module access grant."""
    def guard(
        user: models.User = Depends(current_user),
        db: Session = Depends(tenant_session_db),
    ) -> models.User:
        if not isinstance(db, Session):
            if any(area in ROLE_PERMISSIONS[user.role] for area in areas):
                return user
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this area")
        grant = db.query(RolePermissionGrant).filter(
            RolePermissionGrant.role == user.role.value,
            RolePermissionGrant.module.in_(areas),
            RolePermissionGrant.feature == "access",
            RolePermissionGrant.action == "read",
            RolePermissionGrant.data_scope == "tenant",
            RolePermissionGrant.allowed.is_(True),
        ).first()
        if grant is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this area")
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
    if data_scope == "department":
        if not actor.department or actor.department != target.department:
            raise HTTPException(status_code=403, detail="Department scope does not include this employee")
        return
    today = __import__("datetime").date.today()
    assignments = db.query(EmployeeOrgAssignment).filter(
        EmployeeOrgAssignment.valid_from <= today,
        (EmployeeOrgAssignment.valid_to.is_(None) | (EmployeeOrgAssignment.valid_to >= today)),
    ).all()
    current = {row.employee_id: row for row in assignments}
    actor_assignment = current.get(actor_link.employee_id)
    target_assignment = current.get(employee_id)
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
