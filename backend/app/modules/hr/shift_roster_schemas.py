"""Request and response contracts for shift roster generation."""
from __future__ import annotations

from datetime import date, datetime
from pydantic import BaseModel, Field, model_validator

from app.modules.core.schemas import ORMModel


class ShiftRosterGenerateIn(BaseModel):
    start_date: date
    end_date: date
    employee_ids: list[str] | None = Field(default=None, min_length=1, max_length=500)
    branch_id: str | None = None
    department: str | None = Field(default=None, max_length=120)
    all_employees: bool = False

    @model_validator(mode="after")
    def validate_scope_and_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("Roster end date cannot precede start date")
        if (self.end_date - self.start_date).days + 1 > 31:
            raise ValueError("A roster generation request cannot exceed 31 calendar days")
        if self.department is not None:
            self.department = self.department.strip()
            if not self.department:
                raise ValueError("Department cannot be blank")
        selectors = sum((bool(self.employee_ids), bool(self.branch_id or self.department), self.all_employees))
        if selectors != 1:
            raise ValueError("Select exactly one scope: employee_ids, branch/department filters, or all_employees")
        if self.employee_ids and len(set(self.employee_ids)) != len(self.employee_ids):
            raise ValueError("Employee IDs must not contain duplicates")
        if self.employee_ids and (self.branch_id or self.department):
            raise ValueError("Employee IDs cannot be combined with branch/department filters")
        return self


class ShiftRosterGenerateOut(BaseModel):
    start_date: date
    end_date: date
    employee_count: int
    created_count: int
    scheduled_count: int
    weekly_off_count: int
    holiday_count: int
    skipped_existing_count: int
    skipped_outside_employment_count: int
    unassigned_working_day_count: int



class ShiftRosterOverrideIn(BaseModel):
    status: str = Field(pattern="^(scheduled|weekly_off|cancelled)$")
    shift_type_id: str | None = None
    reason: str = Field(min_length=10, max_length=1000)

    @model_validator(mode="after")
    def validate_shift_target(self):
        if self.status == "scheduled" and not self.shift_type_id:
            raise ValueError("A shift_type_id is required for a scheduled roster override")
        if self.status != "scheduled" and self.shift_type_id is not None:
            raise ValueError("Non-scheduled roster overrides cannot specify a shift_type_id")
        if not self.reason.strip():
            raise ValueError("An override reason is required")
        self.reason = self.reason.strip()
        return self


class ShiftRosterOverrideOut(ORMModel):
    id: str
    employee_id: str
    work_date: date
    status: str
    shift_type_id: str | None
    version: int
    is_override: bool
    override_reason: str
    timezone_name: str
    scheduled_start_at_utc: datetime | None
    scheduled_end_at_utc: datetime | None
    shift_code_snapshot: str
    shift_name_snapshot: str
