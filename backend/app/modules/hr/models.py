"""Hr domain SQLAlchemy models."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
from app.modules._base import _uuid, Role, ItemKind, EmployeeType, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseRequisitionStatus, PurchaseRequisitionSource, PurchaseOrderStatus


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    emp_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    employee_type: Mapped[str] = mapped_column(
        String(32), default=EmployeeType.staff, nullable=False, index=True
    )
    department: Mapped[str] = mapped_column(String(120), default="")
    designation: Mapped[str] = mapped_column(String(120), default="")
    joining_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class EmployeeCodeConfig(Base):
    """Per-tenant employee-code pattern and sequence configuration."""

    __tablename__ = "employee_code_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    pattern: Mapped[str] = mapped_column(String(120), default="EMP-{SEQ:03}")
    sequence_start: Mapped[int] = mapped_column(Integer, default=1)
    next_sequence: Mapped[int] = mapped_column(Integer, default=1)
    increment_by: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class EmployeeTypeDefinition(Base):
    """Tenant-local employee type and payout-classification mapping."""

    __tablename__ = "employee_types"
    __table_args__ = (
        UniqueConstraint("code", name="uq_employee_type_code"),
        UniqueConstraint("name", name="uq_employee_type_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    payout_classification: Mapped[str] = mapped_column(String(80), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

class EmployeeSkill(Base):
    __tablename__ = "employee_skills"
    __table_args__ = (UniqueConstraint("employee_id", "skill", name="uq_employee_skill"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    skill: Mapped[str] = mapped_column(String(120), index=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    certified: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class HRBranch(Base):
    """Tenant-local physical/business branch used for employee data scoping."""

    __tablename__ = "hr_branches"
    __table_args__ = (UniqueConstraint("code", name="uq_hr_branch_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str] = mapped_column(Text, default="", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EmployeeOrgAssignment(Base):
    """Effective-dated employee branch, department and reporting-manager assignment."""

    __tablename__ = "employee_org_assignments"
    __table_args__ = (
        UniqueConstraint("employee_id", "valid_from", name="uq_employee_org_assignment_start"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("hr_branches.id"), nullable=True, index=True)
    manager_employee_id: Mapped[str | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    department: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
