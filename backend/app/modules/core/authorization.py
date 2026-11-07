"""Core authorization and employee-account relationship models."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.modules._base import _uuid


class EmployeeUserLink(Base):
    """Explicit one-to-one link between a login and an employee record."""

    __tablename__ = "employee_user_links"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_employee_user_links_user"),
        UniqueConstraint("employee_id", name="uq_employee_user_links_employee"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RolePermissionGrant(Base):
    """Role grant at module/feature/action level with an explicit data scope."""

    __tablename__ = "role_permission_grants"
    __table_args__ = (
        UniqueConstraint(
            "role", "module", "feature", "action", "data_scope",
            name="uq_role_permission_grant",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    feature: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    data_scope: Mapped[str] = mapped_column(String(24), nullable=False, default="tenant")
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
