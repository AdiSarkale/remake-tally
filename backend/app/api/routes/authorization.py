"""Administrative APIs for explicit employee identity links and role grants."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.api.deps import current_user
from app.db.session import get_db
from app.modules.core.authorization import EmployeeUserLink, RolePermissionGrant
from app.modules.core.audit import log_audit

router = APIRouter(prefix="/authorization", tags=["authorization"])
Scope = Literal["tenant", "self", "department"]


class EmployeeLinkIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=36)
    employee_id: str = Field(min_length=1, max_length=36)


class EmployeeLinkOut(BaseModel):
    id: str
    user_id: str
    employee_id: str
    created_by: str


class RoleGrantIn(BaseModel):
    role: str = Field(min_length=1, max_length=64)
    module: str = Field(min_length=1, max_length=64)
    feature: str = Field(min_length=1, max_length=80)
    action: str = Field(min_length=1, max_length=32)
    data_scope: Scope = "tenant"
    allowed: bool = True


class RoleGrantOut(RoleGrantIn):
    id: str
    updated_by: str


def _require_admin(user: models.User) -> None:
    if user.role != models.Role.admin:
        raise HTTPException(403, "Only Admin can manage authorization settings")


@router.get("/employee-links", response_model=list[EmployeeLinkOut])
def list_employee_links(db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    _require_admin(user)
    return db.query(EmployeeUserLink).order_by(EmployeeUserLink.created_at.desc()).all()


@router.post("/employee-links", response_model=EmployeeLinkOut, status_code=201)
def create_employee_link(payload: EmployeeLinkIn, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    _require_admin(user)
    account = db.get(models.User, payload.user_id)
    employee = db.get(models.Employee, payload.employee_id)
    if account is None or not account.active:
        raise HTTPException(404, "Active user account not found")
    if employee is None or not employee.active:
        raise HTTPException(404, "Active employee record not found")
    if db.query(EmployeeUserLink).filter(
        (EmployeeUserLink.user_id == payload.user_id) |
        (EmployeeUserLink.employee_id == payload.employee_id)
    ).first():
        raise HTTPException(409, "User or employee is already linked")
    row = EmployeeUserLink(user_id=payload.user_id, employee_id=payload.employee_id, created_by=user.username)
    db.add(row)
    log_audit(db, user.username, "CREATE", "employee_user_link", f"user_id={payload.user_id}; employee_id={payload.employee_id}")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "User or employee is already linked") from exc
    db.refresh(row)
    return row


@router.delete("/employee-links/{link_id}", status_code=204)
def delete_employee_link(link_id: str, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    _require_admin(user)
    row = db.get(EmployeeUserLink, link_id)
    if row is None:
        raise HTTPException(404, "Employee account link not found")
    log_audit(db, user.username, "DELETE", "employee_user_link", f"user_id={row.user_id}; employee_id={row.employee_id}")
    db.delete(row)
    db.commit()


@router.get("/role-grants", response_model=list[RoleGrantOut])
def list_role_grants(db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    _require_admin(user)
    return db.query(RolePermissionGrant).order_by(
        RolePermissionGrant.role, RolePermissionGrant.module,
        RolePermissionGrant.feature, RolePermissionGrant.action,
    ).all()


@router.put("/role-grants", response_model=RoleGrantOut)
def upsert_role_grant(payload: RoleGrantIn, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    _require_admin(user)
    valid_roles = {role.value for role in models.Role}
    if payload.role not in valid_roles:
        raise HTTPException(422, "Unknown role")
    row = db.query(RolePermissionGrant).filter_by(
        role=payload.role, module=payload.module, feature=payload.feature,
        action=payload.action, data_scope=payload.data_scope,
    ).first()
    if row is None:
        row = RolePermissionGrant(**payload.model_dump(), updated_by=user.username)
        db.add(row)
        operation = "CREATE"
    else:
        row.allowed = payload.allowed
        row.updated_by = user.username
        operation = "UPDATE"
    log_audit(db, user.username, operation, "role_permission_grant",
              f"{payload.role}:{payload.module}:{payload.feature}:{payload.action}:{payload.data_scope}:{payload.allowed}")
    db.commit()
    db.refresh(row)
    return row
