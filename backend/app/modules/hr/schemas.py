"""Hr domain Pydantic schemas."""

from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.modules._base import Role, ItemKind, EmployeeType, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseRequisitionStatus, PurchaseRequisitionSource, PurchaseOrderStatus
from app.modules.core.schemas import ORMModel


class EmployeeIn(BaseModel):
    """Editable employee fields. Employee code and lifecycle state are server-managed."""
    name: str = Field(min_length=1, max_length=120)
    employee_type: EmployeeType = EmployeeType.staff
    department: str = Field(default="", max_length=120)
    designation: str = Field(default="", max_length=120)

class EmployeeUpdate(BaseModel):
    """Employee details only; employee code and active state cannot be changed here."""
    name: str = Field(min_length=1, max_length=120)
    employee_type: EmployeeType = EmployeeType.staff
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
    employee_type: EmployeeType
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
