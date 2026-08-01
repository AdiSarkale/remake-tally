"""Admin user administration: create users, edit roles, reset passwords."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import current_user, require_area
from app.core.security import hash_password, verify_password
from app.db.session import get_db

router = APIRouter(prefix="/users", tags=["users"])

# "settings" is Admin-only in ROLE_PERMISSIONS.
admin_only = require_area("settings")


def _get(db: Session, user_id: str) -> models.User:
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _active_admins(db: Session, exclude_id: str | None = None) -> int:
    q = db.query(models.User).filter(models.User.role == models.Role.admin, models.User.active.is_(True))
    if exclude_id:
        q = q.filter(models.User.id != exclude_id)
    return q.count()


@router.get("", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db), _: models.User = Depends(admin_only)) -> list[models.User]:
    return db.query(models.User).order_by(models.User.username).all()


@router.post("", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(admin_only),
) -> models.User:
    username = payload.username.strip().lower()
    if db.query(models.User).filter(models.User.username == username).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    user = models.User(
        username=username,
        full_name=payload.full_name.strip(),
        email=payload.email.strip(),
        role=payload.role,
        active=payload.active,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: str,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(admin_only),
) -> models.User:
    user = _get(db, user_id)
    losing_admin = user.role == models.Role.admin and user.active and (
        payload.role != models.Role.admin or not payload.active
    )
    if losing_admin and _active_admins(db, exclude_id=user.id) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one active Admin is required")
    user.full_name = payload.full_name.strip()
    user.email = payload.email.strip()
    user.role = payload.role
    user.active = payload.active
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: str,
    payload: schemas.PasswordReset,
    db: Session = Depends(get_db),
    _: models.User = Depends(admin_only),
) -> None:
    """Admin sets any user's password without knowing the existing one."""
    user = _get(db, user_id)
    user.password_hash = hash_password(payload.new_password)
    db.commit()


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_own_password(
    payload: schemas.PasswordChange,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
) -> None:
    """Self-service change — the current password IS required here."""
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
