"""Payroll, monthly attendance and HR calendar schemas."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.core.schemas import ORMModel

SalaryCountMode = Literal["working_days", "calendar_days", "fixed_days"]
CalendarDayType = Literal["working_day", "holiday", "week_off"]
AttendanceStatus = Literal["present", "absent", "half_day", "paid_leave", "unpaid_leave", "unmarked"]


class PayrollSettingsIn(BaseModel):
    salary_count_mode: SalaryCountMode = "working_days"
    monthly_salary_days: int = Field(default=26, ge=1, le=31)
    week_off_days: list[int] = Field(default_factory=lambda: [5, 6], max_length=7)

    @field_validator("week_off_days")
    @classmethod
    def validate_weekdays(cls, values: list[int]) -> list[int]:
        if any(day < 0 or day > 6 for day in values):
            raise ValueError("Week-off days must be weekday numbers from 0 (Monday) to 6 (Sunday)")
        if len(set(values)) != len(values):
            raise ValueError("Week-off days cannot contain duplicates")
        return sorted(values)


class PayrollSettingsOut(ORMModel):
    id: int
    salary_count_mode: SalaryCountMode
    monthly_salary_days: int
    week_off_days: list[int]
    updated_at: datetime | None = None


class CalendarDayIn(BaseModel):
    day_type: CalendarDayType
    description: str = Field(default="", max_length=240)


class CalendarDayOut(BaseModel):
    work_date: date
    day_type: CalendarDayType
    description: str = ""
    is_override: bool = False


class EmployeeSalaryIn(BaseModel):
    annual_salary: float = Field(gt=0, le=1_000_000_000)
    basic_pct: float = Field(default=50, ge=0, le=100)
    hra_pct: float = Field(default=40, ge=0, le=100)
    da_pct: float = Field(default=0, ge=0, le=100)
    conveyance_monthly: float = Field(default=0, ge=0, le=10_000_000)
    medical_allowance_monthly: float = Field(default=0, ge=0, le=10_000_000)
    pf_pct: float = Field(default=12, ge=0, le=100)
    professional_tax_monthly: float = Field(default=200, ge=0, le=1_000_000)
    tds_monthly: float = Field(default=0, ge=0, le=100_000_000)


class EmployeeSalaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    employee_id: str
    employee_code: str
    employee_name: str
    department: str
    active: bool
    configured: bool
    annual_salary: float
    basic_pct: float
    hra_pct: float
    da_pct: float
    conveyance_monthly: float
    medical_allowance_monthly: float
    pf_pct: float
    professional_tax_monthly: float
    tds_monthly: float
    monthly_gross: float
    basic: float
    hra: float
    da: float
    conveyance: float
    medical_allowance: float
    special_allowance: float
    employee_pf: float
    professional_tax: float
    tds: float
    updated_at: datetime | None = None


class EmployeeAttendanceIn(BaseModel):
    employee_id: str
    work_date: date
    status: AttendanceStatus
    punch_in: datetime | None = None
    punch_out: datetime | None = None
    overtime_minutes: int = Field(default=0, ge=0, le=1440)
    note: str = Field(default="", max_length=1000)


class EmployeeAttendanceOut(BaseModel):
    id: str | None = None
    employee_id: str
    employee_code: str
    employee_name: str
    work_date: date
    status: str
    calendar_type: CalendarDayType
    calendar_description: str = ""
    punch_in: datetime | None = None
    punch_out: datetime | None = None
    overtime_minutes: int = 0
    note: str = ""


class PayrollItemOut(BaseModel):
    employee_id: str
    employee_code: str
    employee_name: str
    department: str
    configured: bool = True
    annual_salary: float
    monthly_gross: float
    basic: float
    hra: float
    da: float
    conveyance: float
    medical_allowance: float
    special_allowance: float
    employee_pf: float
    professional_tax: float
    tds: float
    absence_deduction: float
    overtime_pay: float
    net_pay: float
    present_days: float
    half_days: float
    absent_days: float
    paid_leave_days: float
    unpaid_leave_days: float
    overtime_minutes: int


class PayrollPreviewOut(BaseModel):
    year: int
    month: int
    salary_count_mode: SalaryCountMode
    salary_count_days: int
    items: list[PayrollItemOut]


class PayrollRunSummaryOut(BaseModel):
    id: str
    year: int
    month: int
    status: str
    created_by: str
    created_at: datetime
    finalized_at: datetime
    employee_count: int
    net_total: float


class PayrollRunOut(PayrollRunSummaryOut):
    items: list[PayrollItemOut]
