"""Auth dependencies: current user + role guard + tenant DB context."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import models
from app.core.security import decode_access_token
from app.db.control import get_control_db
from app.db.tenant import get_tenant_db

bearer = HTTPBearer(auto_error=False)

ROLE_PERMISSIONS: dict[models.Role, set[str]] = {
    models.Role.admin: {"masters", "inventory", "production", "scrap", "sales", "finance", "settings", "reports", "approvals", "purchase_requests"},
    models.Role.accountant: {"masters", "inventory", "sales", "reports", "approvals", "purchase_requests"},
    models.Role.operator: {"production", "scrap", "inventory", "approvals", "purchase_requests"},
}


def current_company(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    control_db: Session = Depends(get_control_db),
) -> models.TenantCompany:
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(creds.credentials)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    company_id = payload.get("company_id")
    if not company_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has no company context")

    company = control_db.get(models.TenantCompany, str(company_id))
    if company is None or not company.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Company no longer exists or is inactive")
    return company


def get_db(
    company: models.TenantCompany = Depends(current_company),
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
    company: models.TenantCompany = Depends(current_company),
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
    def guard(user: models.User = Depends(current_user)) -> models.User:
        if area not in ROLE_PERMISSIONS[user.role]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{user.role.value} cannot access {area}")
        return user
    return guard


def require_any_area(*areas: str):
    def guard(user: models.User = Depends(current_user)) -> models.User:
        if not any(area in ROLE_PERMISSIONS[user.role] for area in areas):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{user.role.value} cannot access this area")
        return user
    return guard
