"""Payroll, attendance and HR calendar models."""
from __future__ import annotations

from datetime import date, datetime
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.modules._base import _uuid


class HRPayrollSettings(Base):
    __tablename__ = "hr_payroll_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    salary_count_mode: Mapped[str] = mapped_column(String(20), default="working_days", nullable=False)
    monthly_salary_days: Mapped[int] = mapped_column(Integer, default=26, nullable=False)
    week_off_days: Mapped[str] = mapped_column(String(20), default="5,6", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HRCalendarDay(Base):
    __tablename__ = "hr_calendar_days"
    __table_args__ = (UniqueConstraint("work_date", name="uq_hr_calendar_work_date"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    day_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class EmployeeSalaryProfile(Base):
    __tablename__ = "employee_salary_profiles"
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True)
    annual_salary: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    basic_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=50, nullable=False)
    hra_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=40, nullable=False)
    da_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    conveyance_monthly: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    medical_allowance_monthly: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    pf_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=12, nullable=False)
    professional_tax_monthly: Mapped[float] = mapped_column(Numeric(12, 2), default=200, nullable=False)
    tds_monthly: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class EmployeeAttendance(Base):
    __tablename__ = "employee_attendance"
    __table_args__ = (UniqueConstraint("employee_id", "work_date", name="uq_hr_employee_attendance_day"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True, nullable=False)
    work_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="present", nullable=False)
    punch_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    punch_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    overtime_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HRPayrollRun(Base):
    __tablename__ = "hr_payroll_runs"
    __table_args__ = (UniqueConstraint("year", "month", name="uq_hr_payroll_period"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="finalized", nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finalized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class HRPayrollItem(Base):
    __tablename__ = "hr_payroll_items"
    __table_args__ = (UniqueConstraint("payroll_run_id", "employee_id", name="uq_hr_payroll_employee"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    payroll_run_id: Mapped[str] = mapped_column(ForeignKey("hr_payroll_runs.id", ondelete="CASCADE"), index=True, nullable=False)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True, nullable=False)
    employee_code: Mapped[str] = mapped_column(String(32), nullable=False)
    employee_name: Mapped[str] = mapped_column(String(120), nullable=False)
    department: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    annual_salary: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    monthly_gross: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    basic: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    hra: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    da: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    conveyance: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    medical_allowance: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    special_allowance: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    employee_pf: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    professional_tax: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    tds: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    absence_deduction: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    overtime_pay: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    net_pay: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    present_days: Mapped[float] = mapped_column(Numeric(7, 2), default=0, nullable=False)
    half_days: Mapped[float] = mapped_column(Numeric(7, 2), default=0, nullable=False)
    absent_days: Mapped[float] = mapped_column(Numeric(7, 2), default=0, nullable=False)
    paid_leave_days: Mapped[float] = mapped_column(Numeric(7, 2), default=0, nullable=False)
    unpaid_leave_days: Mapped[float] = mapped_column(Numeric(7, 2), default=0, nullable=False)
    overtime_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
