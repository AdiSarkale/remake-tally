"""Pydantic contracts for the P0.1 shift catalog API."""
from __future__ import annotations

from datetime import time
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.core.schemas import ORMModel


class ShiftTypeIn(BaseModel):
    code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    start_time: time
    end_time: time
    end_day_offset: Literal[0, 1] = 0

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Shift name is required")
        return value

    @model_validator(mode="after")
    def validate_window(self):
        start = self.start_time.hour * 60 + self.start_time.minute
        end = self.end_time.hour * 60 + self.end_time.minute
        duration = end - start + (self.end_day_offset * 1440)
        if duration <= 0 or duration > 1440:
            raise ValueError("Shift duration must be greater than zero and no more than 24 hours")
        return self


class ShiftTypeOut(ORMModel):
    id: str
    code: str
    name: str
    start_time: time
    end_time: time
    end_day_offset: int
    active: bool


class ShiftTypeDetailOut(ShiftTypeOut):
    break_rules: list["ShiftBreakRuleOut"] = Field(default_factory=list)


class ShiftActiveIn(BaseModel):
    active: bool


class ShiftBreakRuleIn(BaseModel):
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    sequence: int = Field(default=0, ge=0, le=10000)
    is_paid: bool = False
    planned_duration_minutes: int = Field(ge=1, le=1440)
    scheduled_start_time: time | None = None
    scheduled_end_time: time | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Break name is required")
        return value

    @model_validator(mode="after")
    def validate_scheduled_window_pair(self):
        if (self.scheduled_start_time is None) != (self.scheduled_end_time is None):
            raise ValueError("Both scheduled break start and end times must be supplied together")
        if self.scheduled_start_time is not None and self.scheduled_end_time <= self.scheduled_start_time:
            raise ValueError("Scheduled break end must be later than its start on the same local day")
        return self


class ShiftBreakRuleOut(ORMModel):
    id: str
    shift_type_id: str
    code: str
    name: str
    sequence: int
    is_paid: bool
    planned_duration_minutes: int
    scheduled_start_time: time | None
    scheduled_end_time: time | None
    active: bool


class ShiftBreakRuleActiveIn(BaseModel):
    active: bool


ShiftTypeDetailOut.model_rebuild()
