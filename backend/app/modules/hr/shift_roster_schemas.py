"""Request and response contracts for shift roster generation."""
from __future__ import annotations

from datetime import date
from pydantic import BaseModel, Field, model_validator


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
