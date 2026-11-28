"""Pydantic contracts for effective-dated shift assignments."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.core.schemas import ORMModel


class ShiftAssignmentIn(BaseModel):
    scope_type: Literal["employee", "department"]
    employee_id: str | None = None
    branch_id: str | None = None
    department: str | None = Field(default=None, max_length=120)
    shift_type_id: str
    weekdays: list[int] = Field(min_length=1, max_length=7)
    valid_from: date
    valid_to: date | None = None

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, value: list[int]) -> list[int]:
        if any(isinstance(day, bool) or day < 0 or day > 6 for day in value):
            raise ValueError("Weekdays must use ISO weekday indexes 0 (Monday) through 6 (Sunday)")
        if len(set(value)) != len(value):
            raise ValueError("Weekdays must not contain duplicates")
        return sorted(value)

    @field_validator("department")
    @classmethod
    def normalize_department(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_target_and_dates(self):
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("Assignment end date cannot precede start date")
        if self.scope_type == "employee":
            if not self.employee_id or self.department is not None:
                raise ValueError("Employee assignments require employee_id and cannot set department")
        elif self.employee_id is not None or not self.department:
            raise ValueError("Department assignments require department and cannot set employee_id")
        return self


class ShiftAssignmentEndIn(BaseModel):
    valid_to: date


class ShiftAssignmentOut(ORMModel):
    id: str
    scope_type: str
    employee_id: str | None
    branch_id: str | None
    department: str | None
    shift_type_id: str
    weekdays: list[int]
    valid_from: date
    valid_to: date | None
    supersedes_assignment_id: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime
