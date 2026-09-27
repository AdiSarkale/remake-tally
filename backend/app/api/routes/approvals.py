"""Department-scoped HOD approvals."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Float, func
from sqlalchemy.orm import Mapped, mapped_column, Session

from app import models
from app.api.deps import current_user, require_area
from app.db.session import Base, get_db
from app.services.inventory import log_audit


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: __import__("uuid").uuid4().__str__())
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    hod_username: Mapped[str] = mapped_column(String(64), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: __import__("uuid").uuid4().__str__())
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), index=True)
    request_type: Mapped[str] = mapped_column(String(48), default="General")
    reference_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    reference_no: Mapped[str] = mapped_column(String(64), default="", index=True)
    title: Mapped[str] = mapped_column(String(200))
    amount: Mapped[float] = mapped_column(Float, default=0)
    requested_by: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="Pending", index=True)
    remarks: Mapped[str] = mapped_column(Text, default="")
    decided_by: Mapped[str] = mapped_column(String(64), default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DepartmentIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    hod_username: str = Field(min_length=1, max_length=64)
    active: bool = True


class DepartmentOut(DepartmentIn):
    id: str

    model_config = {"from_attributes": True}


class ApprovalOut(BaseModel):
    id: str
    department_id: str
    department_code: str
    department_name: str
    request_type: str
    reference_id: str | None
    reference_no: str
    title: str
    amount: float
    requested_by: str
    status: str
    remarks: str
    decided_by: str
    decided_at: datetime | None
    created_at: datetime | None


class ApprovalCreate(BaseModel):
    department_code: str
    request_type: str = "General"
    reference_id: str | None = None
    reference_no: str = ""
    title: str
    amount: float = Field(default=0, ge=0)
    requested_by: str = ""
    remarks: str = ""


class ApprovalDecision(BaseModel):
    status: Literal["Approved", "Rejected"]
    remarks: str = ""


router = APIRouter(prefix="/approvals", tags=["approvals"])


def _is_admin(user: models.User) -> bool:
    return user.role == models.Role.admin


def _department_for_user(db: Session, user: models.User) -> Department | None:
    return db.query(Department).filter(Department.hod_username == user.username, Department.active.is_(True)).first()


def _out(row: ApprovalRequest, dept: Department) -> dict:
    return {
        "id": row.id,
        "department_id": dept.id,
        "department_code": dept.code,
        "department_name": dept.name,
        "request_type": row.request_type,
        "reference_id": row.reference_id,
        "reference_no": row.reference_no,
        "title": row.title,
        "amount": row.amount,
        "requested_by": row.requested_by,
        "status": row.status,
        "remarks": row.remarks,
        "decided_by": row.decided_by,
        "decided_at": row.decided_at,
        "created_at": row.created_at,
    }


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    if not _is_admin(user):
        raise HTTPException(403, "Only Admin can manage departments")
    return db.query(Department).order_by(Department.code).all()


@router.post("/departments", response_model=DepartmentOut, status_code=201)
def create_department(payload: DepartmentIn, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    if not _is_admin(user):
        raise HTTPException(403, "Only Admin can manage departments")
    if db.query(Department).filter((Department.code == payload.code) | (Department.name == payload.name)).first():
        raise HTTPException(409, "Department code or name already exists")
    hod = db.query(models.User).filter(models.User.username == payload.hod_username, models.User.active.is_(True)).first()
    if hod is None:
        raise HTTPException(404, "HOD user not found or inactive")
    row = Department(**payload.model_dump())
    db.add(row)
    log_audit(db, user.username, "CREATE", "department", row.code)
    db.commit()
    db.refresh(row)
    return row


@router.get("/mine", response_model=list[ApprovalOut])
def my_approvals(db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    dept = _department_for_user(db, user)
    if dept is None and not _is_admin(user):
        return []
    q = db.query(ApprovalRequest, Department).join(Department, Department.id == ApprovalRequest.department_id)
    if not _is_admin(user):
        q = q.filter(ApprovalRequest.department_id == dept.id)
    rows = q.order_by(ApprovalRequest.created_at.desc()).all()
    return [_out(row, department) for row, department in rows]


@router.post("", response_model=ApprovalOut, status_code=201)
def create_approval(payload: ApprovalCreate, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    dept = db.query(Department).filter(Department.code == payload.department_code, Department.active.is_(True)).first()
    if dept is None:
        raise HTTPException(404, "Department not found")
    row = ApprovalRequest(
        department_id=dept.id,
        request_type=payload.request_type,
        reference_id=payload.reference_id,
        reference_no=payload.reference_no,
        title=payload.title,
        amount=payload.amount,
        requested_by=payload.requested_by or user.username,
        remarks=payload.remarks,
        status="Pending",
    )
    db.add(row)
    log_audit(db, user.username, "CREATE", "approval_request", payload.reference_no or payload.title)
    db.commit()
    db.refresh(row)
    return _out(row, dept)


@router.patch("/{approval_id}", response_model=ApprovalOut)
def decide_approval(
    approval_id: str,
    payload: ApprovalDecision,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    row = db.get(ApprovalRequest, approval_id)
    if row is None:
        raise HTTPException(404, "Approval request not found")
    dept = db.get(Department, row.department_id)
    if dept is None or not dept.active:
        raise HTTPException(400, "Approval department is inactive")
    if not _is_admin(user) and dept.hod_username != user.username:
        raise HTTPException(403, "You can approve only your department's requests")
    if row.status != "Pending":
        raise HTTPException(400, "Approval is already decided")
    row.status = payload.status
    row.remarks = payload.remarks
    if row.request_type == "Purchase Requisition" and row.reference_id:
        pr = db.get(models.PurchaseRequisition, row.reference_id)
        if pr is not None:
            pr.status = (
                models.PurchaseRequisitionStatus.approved
                if payload.status == "Approved"
                else models.PurchaseRequisitionStatus.rejected
            )
    row.decided_by = user.username
    row.decided_at = datetime.utcnow()
    log_audit(db, user.username, payload.status.upper(), "approval_request", row.reference_no or row.id)
    db.commit()
    db.refresh(row)
    return _out(row, dept)
