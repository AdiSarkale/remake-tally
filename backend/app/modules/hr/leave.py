"""HR leave policy, entitlement and request models."""
from __future__ import annotations

from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.modules._base import _uuid


class HRLeaveType(Base):
    __tablename__ = "hr_leave_types"
    __table_args__ = (UniqueConstraint("code", name="uq_hr_leave_type_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    annual_entitlement: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    carry_forward_limit: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    count_week_offs: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    count_holidays: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_half_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class HRLeaveBalance(Base):
    __tablename__ = "hr_leave_balances"
    __table_args__ = (
        UniqueConstraint("employee_id", "leave_type_id", "year", name="uq_hr_leave_balance_period"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type_id: Mapped[str] = mapped_column(ForeignKey("hr_leave_types.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    opening_balance: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    accrued: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    adjusted: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    used: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HRLeaveRequest(Base):
    __tablename__ = "hr_leave_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    leave_type_id: Mapped[str] = mapped_column(ForeignKey("hr_leave_types.id"), nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_days: Mapped[float] = mapped_column(Float, nullable=False)
    half_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False)
    approver_username: Mapped[str] = mapped_column(String(64), nullable=False)
    decided_by: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    decision_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
