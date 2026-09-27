"""Tenant-aware authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import current_user
from app.core.security import create_access_token, verify_password
from app.db.control import get_control_db
from app.db.tenant import get_tenant_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schemas.TokenResponse)
def login(
    payload: schemas.LoginRequest,
    control_db: Session = Depends(get_control_db),
) -> schemas.TokenResponse:
    # Usernames are tenant-local; the control plane therefore needs a company
    # selection at login in production. The current demo keeps one company per
    # username by requiring a company_code field in the next migration.
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Multi-company login foundation is installed. Add company_code to LoginRequest and wire tenant-local user lookup before enabling login.",
    )


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(current_user)) -> models.User:
    return user
