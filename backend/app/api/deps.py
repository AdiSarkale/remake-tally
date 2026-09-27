"""Auth dependencies: current user + role guard."""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import models
from app.core.security import decode_access_token
from app.db.session import get_db

bearer = HTTPBearer(auto_error=False)

ROLE_PERMISSIONS: dict[models.Role, set[str]] = {
    models.Role.admin: {"masters", "inventory", "production", "scrap", "sales", "finance", "settings", "reports", "approvals", "purchase_requests"},
    models.Role.accountant: {"masters", "inventory", "sales", "reports", "approvals"},
    models.Role.operator: {"production", "scrap", "inventory", "approvals", "purchase_requests"},
}


def current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> models.User:
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(creds.credentials)
    except Exception as exc:  # noqa: BLE001 - any decode failure is a 401
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user = db.query(models.User).filter(models.User.username == payload.get("sub")).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
    if user.must_change_password and request is not None and request.url.path not in {"/api/v1/auth/me", "/api/v1/users/me/change-password"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password change required before continuing")
    return user


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
