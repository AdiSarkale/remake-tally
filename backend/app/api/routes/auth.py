"""Tenant-aware authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import current_company, current_user
from app.core.security import create_access_token, verify_password
from app.db.control import get_control_db
from app.db.control_models import TenantCompany
from app.db.tenant import get_tenant_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schemas.TokenResponse)
def login(
    payload: schemas.LoginRequest,
    control_db: Session = Depends(get_control_db),
) -> schemas.TokenResponse:
    company = (
        control_db.query(TenantCompany)
        .filter(\
            TenantCompany.code == payload.company_code.upper(),\
            TenantCompany.active.is_(True),\
            TenantCompany.provisioning_status == "ready",\
        )
        .first()
    )
    if company is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid company or credentials")

    tenant_db = get_tenant_db(company)
    try:
        user = (
            tenant_db.query(models.User)
            .filter(models.User.username == payload.username, models.User.active.is_(True))
            .first()
        )
        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid company or credentials")

        token = create_access_token(user.username, user.role.value, company.id)
        return schemas.TokenResponse(
            access_token=token,
            role=user.role,
            full_name=user.full_name,
            company_id=company.id,
            company_code=company.code,
            company_name=company.name,
            must_change_password=user.must_change_password,
        )
    finally:
        tenant_db.close()


@router.get("/me", response_model=schemas.UserOut)
def me(
    user: models.User = Depends(current_user),
    company: TenantCompany = Depends(current_company),
) -> schemas.UserOut:
    return schemas.UserOut.model_validate(user).model_copy(update={"company_id": company.id})
