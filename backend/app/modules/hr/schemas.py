"""Hr domain Pydantic schemas."""

from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.modules._base import Role, ItemKind, EmployeeType, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseRequisitionStatus, PurchaseRequisitionSource, PurchaseOrderStatus
from app.modules.core.schemas import ORMModel


class EmployeeIn(BaseModel):
    emp_code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    employee_type: EmployeeType = EmployeeType.staff
    department: str = Field(default="", max_length=120)
    designation: str = Field(default="", max_length=120)
    active: bool = True

class EmployeeUpdate(BaseModel):
    emp_code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    employee_type: EmployeeType = EmployeeType.staff
    department: str = Field(default="", max_length=120)
    designation: str = Field(default="", max_length=120)
    active: bool = True

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
