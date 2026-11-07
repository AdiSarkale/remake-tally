"""Tenant-scoped HR leave policy, balance and approval workflows."""
from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.api.deps import current_user, enforce_employee_data_scope
from app.db.session import get_db
from app.modules.core.audit import log_audit
from app.modules.hr.leave import HRLeaveBalance, HRLeaveRequest, HRLeaveType
from app.modules.hr.payroll import EmployeeAttendance, HRCalendarDay, HRPayrollSettings
from app.api.routes.approvals import Department

router = APIRouter(prefix="/hr/leave", tags=["hr", "leave"])


class LeaveTypeIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=80)
    is_paid: bool = True
    annual_entitlement: float = Field(default=0, ge=0, le=366)
    carry_forward_limit: float = Field(default=0, ge=0, le=366)
    count_week_offs: bool = False
    count_holidays: bool = False
    allow_half_day: bool = False
    active: bool = True


class LeaveTypeOut(LeaveTypeIn):
    id: str
    model_config = {"from_attributes": True}


class LeaveBalanceIn(BaseModel):
    employee_id: str
    leave_type_id: str
    year: int = Field(ge=2000, le=2100)
    opening_balance: float = Field(default=0, ge=0, le=366)
    accrued: float = Field(default=0, ge=0, le=366)
    adjusted: float = Field(default=0, ge=-366, le=366)


class LeaveBalanceOut(BaseModel):
    id: str
    employee_id: str
    leave_type_id: str
    year: int
    opening_balance: float
    accrued: float
    adjusted: float
    used: float
    available: float


class LeaveRequestIn(BaseModel):
    leave_type_id: str
    start_date: date
    end_date: date
    half_day: bool = False
    reason: str = Field(min_length=1, max_length=2000)


class LeaveDecisionIn(BaseModel):
    status: Literal["approved", "rejected"]
    decision_note: str = Field(default="", max_length=2000)


class LeaveRequestOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    employee_id: str
    leave_type_id: str
    start_date: date
    end_date: date
    total_days: float
    half_day: bool
    reason: str
    status: str
    requested_by: str
    approver_username: str
    decided_by: str
    decision_note: str
    decided_at: datetime | None
    created_at: datetime | None


def _is_hr(user: models.User) -> bool:
    return user.role in (models.Role.admin, models.Role.hr)


def _balance_output(row: HRLeaveBalance) -> dict:
    available = row.opening_balance + row.accrued + row.adjusted - row.used
    return {
        "id": row.id, "employee_id": row.employee_id, "leave_type_id": row.leave_type_id,
        "year": row.year, "opening_balance": row.opening_balance, "accrued": row.accrued,
        "adjusted": row.adjusted, "used": row.used, "available": round(available, 2),
    }


def _leave_days(db: Session, leave_type: HRLeaveType, start: date, end: date) -> float:
    settings = db.get(models.HRPayrollSettings, 1)
    week_offs = {5, 6}
    if settings and settings.week_off_days:
        try:
            week_offs = {int(value) for value in settings.week_off_days.split(",") if value != ""}
        except ValueError:
            raise HTTPException(500, "HR week-off configuration is invalid")
    overrides = {
        row.work_date: row.day_type
        for row in db.query(HRCalendarDay).filter(
            HRCalendarDay.work_date >= start, HRCalendarDay.work_date <= end
        ).all()
    }
    total = 0
    current = start
    while current <= end:
        day_type = overrides.get(current)
        if day_type == "holiday":
            if leave_type.count_holidays:
                total += 1
        elif day_type == "week_off" or (day_type is None and current.weekday() in week_offs):
            if leave_type.count_week_offs:
                total += 1
        else:
            total += 1
        current = date.fromordinal(current.toordinal() + 1)
    return float(total)


def _employee_for_user(db: Session, user: models.User) -> models.Employee:
    link = db.query(models.EmployeeUserLink).filter_by(user_id=user.id).first()
    if link is None:
        raise HTTPException(403, "Your login is not linked to an employee record")
    employee = db.get(models.Employee, link.employee_id)
    if employee is None or not employee.active:
        raise HTTPException(403, "Your linked employee record is inactive")
    return employee


@router.get("/types", response_model=list[LeaveTypeOut])
def list_leave_types(db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    query = db.query(HRLeaveType)
    if not _is_hr(user):
        query = query.filter(HRLeaveType.active.is_(True))
    return query.order_by(HRLeaveType.code).all()


@router.post("/types", response_model=LeaveTypeOut, status_code=201)
def create_leave_type(payload: LeaveTypeIn, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    if not _is_hr(user):
        raise HTTPException(403, "Only HR or Admin can manage leave types")
    row = HRLeaveType(**payload.model_dump())
    db.add(row)
    log_audit(db, user.username, "CREATE", "hr_leave_type", payload.code)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Leave type code already exists") from exc
    db.refresh(row)
    return row


@router.put("/types/{leave_type_id}", response_model=LeaveTypeOut)
def update_leave_type(leave_type_id: str, payload: LeaveTypeIn, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    if not _is_hr(user):
        raise HTTPException(403, "Only HR or Admin can manage leave types")
    row = db.get(HRLeaveType, leave_type_id)
    if row is None:
        raise HTTPException(404, "Leave type not found")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    log_audit(db, user.username, "UPDATE", "hr_leave_type", row.code)
    db.commit()
    db.refresh(row)
    return row


@router.get("/balances", response_model=list[LeaveBalanceOut])
def list_leave_balances(
    employee_id: str | None = None, year: int = Query(ge=2000, le=2100),
    db: Session = Depends(get_db), user: models.User = Depends(current_user),
):
    if _is_hr(user):
        query = db.query(HRLeaveBalance).filter(HRLeaveBalance.year == year)
        if employee_id:
            query = query.filter(HRLeaveBalance.employee_id == employee_id)
    else:
        employee = _employee_for_user(db, user)
        query = db.query(HRLeaveBalance).filter(
            HRLeaveBalance.year == year, HRLeaveBalance.employee_id == employee.id
        )
    return [_balance_output(row) for row in query.order_by(HRLeaveBalance.employee_id).all()]


@router.put("/balances", response_model=LeaveBalanceOut)
def upsert_leave_balance(payload: LeaveBalanceIn, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    if not _is_hr(user):
        raise HTTPException(403, "Only HR or Admin can allocate or adjust leave balances")
    employee = db.get(models.Employee, payload.employee_id)
    leave_type = db.get(HRLeaveType, payload.leave_type_id)
    if employee is None or leave_type is None:
        raise HTTPException(404, "Employee or leave type not found")
    row = db.query(HRLeaveBalance).filter_by(
        employee_id=payload.employee_id, leave_type_id=payload.leave_type_id, year=payload.year
    ).with_for_update().first()
    if row is None:
        row = HRLeaveBalance(**payload.model_dump(), updated_by=user.username, used=0)
        db.add(row)
    else:
        if payload.opening_balance + payload.accrued + payload.adjusted < row.used:
            raise HTTPException(409, "New balance cannot be lower than leave already used")
        row.opening_balance = payload.opening_balance
        row.accrued = payload.accrued
        row.adjusted = payload.adjusted
        row.updated_by = user.username
    log_audit(db, user.username, "UPSERT", "hr_leave_balance",
              f"{payload.employee_id}:{payload.leave_type_id}:{payload.year}")
    db.commit()
    db.refresh(row)
    return _balance_output(row)


@router.post("/requests", response_model=LeaveRequestOut, status_code=201)
def create_leave_request(payload: LeaveRequestIn, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    employee = _employee_for_user(db, user)
    if payload.end_date < payload.start_date:
        raise HTTPException(422, "End date cannot be earlier than start date")
    if payload.start_date.year != payload.end_date.year:
        raise HTTPException(422, "A leave request must stay within one calendar year")
    leave_type = db.get(HRLeaveType, payload.leave_type_id)
    if leave_type is None or not leave_type.active:
        raise HTTPException(404, "Active leave type not found")
    if payload.half_day and (not leave_type.allow_half_day or payload.start_date != payload.end_date):
        raise HTTPException(422, "This leave type does not permit the requested half-day format")
    total_days = _leave_days(db, leave_type, payload.start_date, payload.end_date)
    if payload.half_day:
        if total_days <= 0:
            raise HTTPException(422, "Half-day leave must fall on a date that counts under the leave policy")
        total_days = 0.5
    if total_days <= 0:
        raise HTTPException(422, "The selected dates do not contain any leave-counting days")
    overlap = db.query(HRLeaveRequest).filter(
        HRLeaveRequest.employee_id == employee.id,
        HRLeaveRequest.status.in_(["pending", "approved"]),
        HRLeaveRequest.start_date <= payload.end_date,
        HRLeaveRequest.end_date >= payload.start_date,
    ).first()
    if overlap:
        raise HTTPException(409, "This request overlaps an existing pending or approved leave")
    balance = db.query(HRLeaveBalance).filter_by(
        employee_id=employee.id, leave_type_id=leave_type.id, year=payload.start_date.year
    ).with_for_update().first()
    if balance is None:
        raise HTTPException(409, "Leave balance has not been allocated for this employee and year")
    available = balance.opening_balance + balance.accrued + balance.adjusted - balance.used
    if available < total_days:
        raise HTTPException(409, "Insufficient leave balance")
    department = db.query(Department).filter(
        func.lower(Department.name) == employee.department.strip().lower(),
        Department.active.is_(True),
    ).first()
    if department is None or not department.hod_username:
        raise HTTPException(409, "No active department approver is configured for this employee")
    row = HRLeaveRequest(
        employee_id=employee.id, leave_type_id=leave_type.id,
        start_date=payload.start_date, end_date=payload.end_date, total_days=total_days,
        half_day=payload.half_day, reason=payload.reason.strip(), status="pending",
        requested_by=user.username, approver_username=department.hod_username,
    )
    db.add(row)
    log_audit(db, user.username, "CREATE", "hr_leave_request", f"{employee.emp_code}:{payload.start_date}:{payload.end_date}")
    db.commit()
    db.refresh(row)
    return row


@router.get("/requests", response_model=list[LeaveRequestOut])
def list_leave_requests(
    status_filter: str | None = None, db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    query = db.query(HRLeaveRequest)
    if _is_hr(user):
        pass
    else:
        employee = _employee_for_user(db, user)
        query = query.filter(
            (HRLeaveRequest.employee_id == employee.id) |
            (HRLeaveRequest.approver_username == user.username)
        )
    if status_filter:
        if status_filter not in {"pending", "approved", "rejected"}:
            raise HTTPException(422, "Invalid leave status filter")
        query = query.filter(HRLeaveRequest.status == status_filter)
    return query.order_by(HRLeaveRequest.created_at.desc()).all()


@router.patch("/requests/{request_id}", response_model=LeaveRequestOut)
def decide_leave_request(
    request_id: str, payload: LeaveDecisionIn,
    db: Session = Depends(get_db), user: models.User = Depends(current_user),
):
    row = db.query(HRLeaveRequest).filter_by(id=request_id).with_for_update().first()
    if row is None:
        raise HTTPException(404, "Leave request not found")
    if row.status != "pending":
        raise HTTPException(409, "Only pending leave requests can be decided")
    if user.role != models.Role.admin and user.role != models.Role.hr and row.approver_username != user.username:
        raise HTTPException(403, "Only the assigned department approver, HR or Admin can decide this request")
    employee = db.get(models.Employee, row.employee_id)
    leave_type = db.get(HRLeaveType, row.leave_type_id)
    if employee is None or leave_type is None:
        raise HTTPException(409, "Leave request references missing employee or leave type")
    if payload.status == "approved":
        balance = db.query(HRLeaveBalance).filter_by(
            employee_id=row.employee_id, leave_type_id=row.leave_type_id, year=row.start_date.year
        ).with_for_update().first()
        if balance is None:
            raise HTTPException(409, "Leave balance is missing")
        available = balance.opening_balance + balance.accrued + balance.adjusted - balance.used
        if available < row.total_days:
            raise HTTPException(409, "Leave balance is no longer sufficient")
        settings = db.get(models.HRPayrollSettings, 1)
        week_offs = {5, 6}
        if settings and settings.week_off_days:
            week_offs = {int(value) for value in settings.week_off_days.split(",") if value != ""}
        calendar_rows = db.query(HRCalendarDay).filter(
            HRCalendarDay.work_date >= row.start_date, HRCalendarDay.work_date <= row.end_date
        ).all()
        overrides = {item.work_date: item.day_type for item in calendar_rows}
        current = row.start_date
        while current <= row.end_date:
            day_type = overrides.get(current)
            is_working = day_type == "working_day" or (
                day_type is None and current.weekday() not in week_offs
            )
            if is_working:
                attendance = db.query(EmployeeAttendance).filter_by(
                    employee_id=row.employee_id, work_date=current
                ).with_for_update().first()
                if attendance is not None and attendance.status not in {"unmarked", "absent", "paid_leave", "unpaid_leave"}:
                    raise HTTPException(409, f"Attendance already exists for {current}; resolve it before approving leave")
                status = ("paid_half_day" if leave_type.is_paid else "unpaid_half_day") if row.half_day else ("paid_leave" if leave_type.is_paid else "unpaid_leave")
                if attendance is None:
                    attendance = EmployeeAttendance(
                        employee_id=row.employee_id, work_date=current, status=status,
                        overtime_minutes=0, note=f"Leave request {row.id}",
                    )
                    db.add(attendance)
                else:
                    attendance.status = status
                    attendance.note = f"Leave request {row.id}"
            current = date.fromordinal(current.toordinal() + 1)
        balance.used += row.total_days
    row.status = payload.status
    row.decided_by = user.username
    row.decision_note = payload.decision_note.strip()
    row.decided_at = datetime.utcnow()
    log_audit(db, user.username, payload.status.upper(), "hr_leave_request", row.id)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/requests/{request_id}", status_code=204)
def cancel_leave_request(request_id: str, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    row = db.query(HRLeaveRequest).filter_by(id=request_id).with_for_update().first()
    if row is None:
        raise HTTPException(404, "Leave request not found")
    employee = _employee_for_user(db, user)
    if row.employee_id != employee.id:
        raise HTTPException(403, "You can cancel only your own leave request")
    if row.status != "pending":
        raise HTTPException(409, "Only pending requests can be cancelled; approved leave requires an HR reversal workflow")
    row.status = "cancelled"
    log_audit(db, user.username, "CANCEL", "hr_leave_request", row.id)
    db.commit()
    return Response(status_code=204)
