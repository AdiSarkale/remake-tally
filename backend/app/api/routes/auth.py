"""Auth routes: login and current-user profile."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import current_user
from app.core.security import create_access_token, verify_password
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)) -> schemas.TokenResponse:
    user = db.query(models.User).filter(models.User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    token = create_access_token(user.username, user.role.value)
    return schemas.TokenResponse(access_token=token, role=user.role, full_name=user.full_name)


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(current_user)) -> models.User:
    return user
