"""Administrative APIs for explicit employee identity links and role grants."""
from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
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
from app.modules.hr.models import HRBranch, EmployeeOrgAssignment

Scope = Literal["tenant", "self", "department", "branch", "team"]


class EmployeeLinkIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=36)
    employee_id: str = Field(min_length=1, max_length=36)


class EmployeeLinkOut(BaseModel):
    model_config = {"from_attributes": True}

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
    model_config = {"from_attributes": True}

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


class BranchIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    address: str = Field(default="", max_length=2000)
    timezone: str = Field(default="Asia/Kolkata", min_length=1, max_length=64)
    active: bool = True


class BranchOut(BranchIn):
    model_config = {"from_attributes": True}
    id: str


class EmployeeOrgAssignmentIn(BaseModel):
    employee_id: str = Field(min_length=1, max_length=36)
    branch_id: str | None = None
    manager_employee_id: str | None = None
    department: str = Field(default="", max_length=120)
    valid_from: date
    valid_to: date | None = None


class EmployeeOrgAssignmentOut(EmployeeOrgAssignmentIn):
    model_config = {"from_attributes": True}
    id: str
    created_by: str


@router.get("/branches", response_model=list[BranchOut])
def list_branches(db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    _require_admin(user)
    return db.query(HRBranch).order_by(HRBranch.code).all()


@router.post("/branches", response_model=BranchOut, status_code=201)
def create_branch(payload: BranchIn, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    _require_admin(user)
    try:
        ZoneInfo(payload.timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(422, "Branch timezone must be a valid IANA timezone") from exc
    row = HRBranch(**payload.model_dump())
    db.add(row)
    log_audit(db, user.username, "CREATE", "hr_branch", f"{payload.code}; {payload.name}")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Branch code already exists") from exc
    db.refresh(row)
    return row


@router.put("/branches/{branch_id}", response_model=BranchOut)
def update_branch(branch_id: str, payload: BranchIn, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    _require_admin(user)
    row = db.get(HRBranch, branch_id)
    if row is None:
        raise HTTPException(404, "Branch not found")
    try:
        ZoneInfo(payload.timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(422, "Branch timezone must be a valid IANA timezone") from exc
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    log_audit(db, user.username, "UPDATE", "hr_branch", f"{row.code}; active={row.active}")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Branch code already exists") from exc
    db.refresh(row)
    return row


@router.get("/employee-org-assignments", response_model=list[EmployeeOrgAssignmentOut])
def list_employee_org_assignments(
    employee_id: str | None = None, db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    _require_admin(user)
    query = db.query(EmployeeOrgAssignment)
    if employee_id:
        query = query.filter(EmployeeOrgAssignment.employee_id == employee_id)
    return query.order_by(EmployeeOrgAssignment.employee_id, EmployeeOrgAssignment.valid_from.desc()).all()


@router.post("/employee-org-assignments", response_model=EmployeeOrgAssignmentOut, status_code=201)
def create_employee_org_assignment(
    payload: EmployeeOrgAssignmentIn, db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    _require_admin(user)
    if payload.valid_to is not None and payload.valid_to < payload.valid_from:
        raise HTTPException(422, "Assignment end date cannot precede start date")
    employee = db.query(models.Employee).filter_by(id=payload.employee_id).with_for_update().first()
    if employee is None or not employee.active:
        raise HTTPException(404, "Active employee not found")
    if payload.manager_employee_id == payload.employee_id:
        raise HTTPException(422, "An employee cannot report to themselves")
    if payload.branch_id:
        branch = db.get(HRBranch, payload.branch_id)
        if branch is None or not branch.active:
            raise HTTPException(404, "Active branch not found")
    if payload.manager_employee_id:
        manager = db.get(models.Employee, payload.manager_employee_id)
        if manager is None or not manager.active:
            raise HTTPException(404, "Active reporting manager not found")
        # Reject a cycle if the proposed manager already reports, directly or
        # indirectly, to the employee being assigned.
        cursor = payload.manager_employee_id
        seen: set[str] = set()
        while cursor and cursor not in seen:
            if cursor == payload.employee_id:
                raise HTTPException(422, "Reporting assignment would create an organizational cycle")
            seen.add(cursor)
            manager_assignment = db.query(EmployeeOrgAssignment).filter(
                EmployeeOrgAssignment.employee_id == cursor,
                EmployeeOrgAssignment.valid_from <= payload.valid_from,
                (EmployeeOrgAssignment.valid_to.is_(None) | (EmployeeOrgAssignment.valid_to >= payload.valid_from)),
            ).order_by(EmployeeOrgAssignment.valid_from.desc()).first()
            cursor = manager_assignment.manager_employee_id if manager_assignment else None

    # Close an existing open assignment the day before the new one starts.
    current_rows = db.query(EmployeeOrgAssignment).filter(
        EmployeeOrgAssignment.employee_id == payload.employee_id,
        EmployeeOrgAssignment.valid_from < payload.valid_from,
        (EmployeeOrgAssignment.valid_to.is_(None) | (EmployeeOrgAssignment.valid_to >= payload.valid_from)),
    ).with_for_update().all()
    for existing in current_rows:
        existing.valid_to = payload.valid_from - timedelta(days=1)

    overlap = db.query(EmployeeOrgAssignment).filter(
        EmployeeOrgAssignment.employee_id == payload.employee_id,
        EmployeeOrgAssignment.valid_from <= (payload.valid_to or date.max),
        (EmployeeOrgAssignment.valid_to.is_(None) | (EmployeeOrgAssignment.valid_to >= payload.valid_from)),
    ).first()
    if overlap:
        db.rollback()
        raise HTTPException(409, "An organizational assignment already exists for this effective period")
    row = EmployeeOrgAssignment(**payload.model_dump(), created_by=user.username)
    db.add(row)
    log_audit(
        db, user.username, "CREATE", "employee_org_assignment",
        f"employee={payload.employee_id}; branch={payload.branch_id}; manager={payload.manager_employee_id}; from={payload.valid_from}; to={payload.valid_to}",
    )
    db.commit()
    db.refresh(row)
    return row
