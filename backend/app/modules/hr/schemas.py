"""Hr domain Pydantic schemas."""

from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.modules._base import Role, ItemKind, EmployeeType, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseRequisitionStatus, PurchaseRequisitionSource, PurchaseOrderStatus
from app.modules.core.schemas import ORMModel


class EmployeeCodeConfigIn(BaseModel):
    pattern: str = Field(min_length=1, max_length=120)
    sequence_start: int = Field(ge=1, le=999999999)
    increment_by: int = Field(ge=1, le=1000000)

class EmployeeCodeConfigOut(ORMModel):
    id: int
    pattern: str
    sequence_start: int
    next_sequence: int
    increment_by: int
    updated_at: datetime

class EmployeeTypeIn(BaseModel):
    code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=80)
    payout_classification: str = Field(default="", max_length=80)
    active: bool = True

class EmployeeTypeOut(ORMModel):
    id: str
    code: str
    name: str
    payout_classification: str
    active: bool

class EmployeeIn(BaseModel):
    """Editable employee fields. Employee code and lifecycle state are server-managed."""
    name: str = Field(min_length=1, max_length=120)
    employee_type: str = Field(default="staff", min_length=2, max_length=32)
    department: str = Field(default="", max_length=120)
    designation: str = Field(default="", max_length=120)

class EmployeeUpdate(BaseModel):
    """Employee details only; employee code and active state cannot be changed here."""
    name: str = Field(min_length=1, max_length=120)
    employee_type: str = Field(default="staff", min_length=2, max_length=32)
    department: str = Field(default="", max_length=120)
    designation: str = Field(default="", max_length=120)

class EmployeeStatusUpdate(BaseModel):
    active: bool

class EmployeeSkillIn(BaseModel):
    skill: str
    level: int = Field(default=1, ge=1, le=5)
    certified: bool = False
    active: bool = True

class EmployeeOut(ORMModel):
    id: str
    emp_code: str
    name: str
    employee_type: str
    department: str
    designation: str
    active: bool

class EmployeeSkillOut(ORMModel):
    id: str
    employee_id: str
    skill: str
    level: int
    certified: bool
    active: bool

class AssignEmployeeIn(BaseModel):
    employee_id: str | None = None
