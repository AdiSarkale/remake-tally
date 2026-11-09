"""Payroll, attendance and HR calendar models."""
from __future__ import annotations

from datetime import date, datetime, time
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.modules._base import _uuid


class HRPayrollSettings(Base):
    __tablename__ = "hr_payroll_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    salary_count_mode: Mapped[str] = mapped_column(String(20), default="working_days", nullable=False)
    monthly_salary_days: Mapped[int] = mapped_column(Integer, default=26, nullable=False)
    week_off_days: Mapped[str] = mapped_column(String(20), default="5,6", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HRCalendarDay(Base):
    __tablename__ = "hr_calendar_days"
    __table_args__ = (UniqueConstraint("work_date", name="uq_hr_calendar_work_date"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    day_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class EmployeeSalaryProfile(Base):
    __tablename__ = "employee_salary_profiles"
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True)
    annual_salary: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    basic_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=50, nullable=False)
    hra_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=40, nullable=False)
    da_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    conveyance_monthly: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    medical_allowance_monthly: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    pf_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=12, nullable=False)
    professional_tax_monthly: Mapped[float] = mapped_column(Numeric(12, 2), default=200, nullable=False)
    tds_monthly: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class EmployeeAttendance(Base):
    __tablename__ = "employee_attendance"
    __table_args__ = (UniqueConstraint("employee_id", "work_date", name="uq_hr_employee_attendance_day"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True, nullable=False)
    work_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="present", nullable=False)
    # Work date and timezone are a snapshot of the local attendance context.
    # UTC punch instants remain canonical and are never recalculated on transfers.
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("hr_branches.id", ondelete="RESTRICT"), nullable=True, index=True)
    timezone_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    punch_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    punch_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    overtime_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HRAttendanceImportBatch(Base):
    """One immutable upload attempt and its interpretation context."""

    __tablename__ = "hr_attendance_import_batches"
    __table_args__ = (
        CheckConstraint("status IN ('validated', 'imported', 'rejected')", name="ck_hr_attendance_import_batch_status"),
        CheckConstraint("rows_total >= 0 AND rows_imported >= 0 AND rows_rejected >= 0", name="ck_hr_attendance_import_batch_counts"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("hr_branches.id", ondelete="RESTRICT"), nullable=True, index=True)
    import_timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    template_version: Mapped[str] = mapped_column(String(32), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    uploaded_by: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="validated")
    rows_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")


class HRAttendanceEvent(Base):
    """Append-only source attendance event; never use as the payroll daily summary."""

    __tablename__ = "hr_attendance_events"
    __table_args__ = (
        UniqueConstraint("source_type", "source_reference", name="uq_hr_attendance_event_source_reference"),
        CheckConstraint(
            "event_type IN ('punch_in', 'punch_out', 'break_start', 'break_end')",
            name="ck_hr_attendance_event_type",
        ),
        CheckConstraint(
            "source_type IN ('manual_hr', 'excel_import', 'employee')",
            name="ck_hr_attendance_event_source_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)
    roster_entry_id: Mapped[str | None] = mapped_column(ForeignKey("hr_shift_roster_entries.id", ondelete="RESTRICT"), nullable=True, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    occurred_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    timezone_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    import_batch_id: Mapped[str | None] = mapped_column(ForeignKey("hr_attendance_import_batches.id", ondelete="RESTRICT"), nullable=True, index=True)
    break_rule_id: Mapped[str | None] = mapped_column(ForeignKey("hr_shift_break_rules.id", ondelete="RESTRICT"), nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(64), nullable=False)
    supersedes_event_id: Mapped[str | None] = mapped_column(ForeignKey("hr_attendance_events.id", ondelete="RESTRICT"), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    void_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class HRAttendanceAnomaly(Base):
    """Auditable source discrepancy; never mutates the underlying raw events."""

    __tablename__ = "hr_attendance_anomalies"
    __table_args__ = (
        UniqueConstraint("comparison_key", name="uq_hr_attendance_anomaly_comparison"),
        CheckConstraint(
            "anomaly_type IN ('source_mismatch')",
            name="ck_hr_attendance_anomaly_type",
        ),
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved', 'false_positive')",
            name="ck_hr_attendance_anomaly_status",
        ),
        CheckConstraint("threshold_minutes >= 0", name="ck_hr_attendance_anomaly_threshold"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    comparison_key: Mapped[str] = mapped_column(String(64), nullable=False)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    roster_entry_id: Mapped[str | None] = mapped_column(ForeignKey("hr_shift_roster_entries.id", ondelete="RESTRICT"), nullable=True)
    anomaly_type: Mapped[str] = mapped_column(String(32), nullable=False, default="source_mismatch")
    source_event_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    observed_delta_minutes: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    threshold_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_version_id: Mapped[str] = mapped_column(ForeignKey("hr_workforce_policy_versions.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    resolution_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    resolution_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class HRPayrollRun(Base):
    __tablename__ = "hr_payroll_runs"
    __table_args__ = (UniqueConstraint("year", "month", "revision", name="uq_hr_payroll_period_revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversal_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)


class HRPayrollItem(Base):
    __tablename__ = "hr_payroll_items"
    __table_args__ = (UniqueConstraint("payroll_run_id", "employee_id", name="uq_hr_payroll_employee"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    payroll_run_id: Mapped[str] = mapped_column(ForeignKey("hr_payroll_runs.id", ondelete="CASCADE"), index=True, nullable=False)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), index=True, nullable=False)
    employee_code: Mapped[str] = mapped_column(String(32), nullable=False)
    employee_name: Mapped[str] = mapped_column(String(120), nullable=False)
    department: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    annual_salary: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    monthly_gross: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    basic: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    hra: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    da: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    conveyance: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    medical_allowance: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    special_allowance: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    employee_pf: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    professional_tax: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    tds: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    absence_deduction: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    overtime_pay: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    net_pay: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    present_days: Mapped[float] = mapped_column(Numeric(7, 2), default=0, nullable=False)
    half_days: Mapped[float] = mapped_column(Numeric(7, 2), default=0, nullable=False)
    absent_days: Mapped[float] = mapped_column(Numeric(7, 2), default=0, nullable=False)
    paid_leave_days: Mapped[float] = mapped_column(Numeric(7, 2), default=0, nullable=False)
    unpaid_leave_days: Mapped[float] = mapped_column(Numeric(7, 2), default=0, nullable=False)
    overtime_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class HRShiftRosterEntryHistory(Base):
    """Immutable prior roster snapshot captured before a controlled override."""

    __tablename__ = "hr_shift_roster_entry_history"
    __table_args__ = (
        UniqueConstraint("roster_entry_id", "version", name="uq_hr_shift_roster_history_version"),
        CheckConstraint("version > 0", name="ck_hr_shift_roster_history_version_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    roster_entry_id: Mapped[str] = mapped_column(
        ForeignKey("hr_shift_roster_entries.id", ondelete="RESTRICT"), nullable=False, index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(64), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class HRWorkforcePolicyVersion(Base):
    """Versioned tenant workforce policy snapshot used by roster generation."""

    __tablename__ = "hr_workforce_policy_versions"
    __table_args__ = (
        UniqueConstraint("version_code", name="uq_hr_workforce_policy_version_code"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_hr_workforce_policy_effective_dates",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    version_code: Mapped[str] = mapped_column(String(40), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    configuration: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class HRShiftType(Base):
    """Reusable local-time shift definition; roster rows retain immutable snapshots."""

    __tablename__ = "hr_shift_types"
    __table_args__ = (
        UniqueConstraint("code", name="uq_hr_shift_type_code"),
        CheckConstraint("end_day_offset IN (0, 1)", name="ck_hr_shift_end_day_offset"),
        CheckConstraint("end_day_offset = 1 OR end_time > start_time", name="ck_hr_shift_same_day_end_after_start"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_day_offset: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HRShiftBreakRule(Base):
    """Scheduled paid/unpaid break rule attached to a shift definition."""

    __tablename__ = "hr_shift_break_rules"
    __table_args__ = (
        UniqueConstraint("shift_type_id", "code", name="uq_hr_shift_break_rule_code"),
        CheckConstraint("planned_duration_minutes > 0", name="ck_hr_shift_break_duration_positive"),
        CheckConstraint("sequence >= 0", name="ck_hr_shift_break_sequence_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    shift_type_id: Mapped[str] = mapped_column(ForeignKey("hr_shift_types.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    planned_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    scheduled_end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HRShiftAssignment(Base):
    """Effective-dated employee assignment or department default shift."""

    __tablename__ = "hr_shift_assignments"
    __table_args__ = (
        CheckConstraint(
            "(scope_type = 'employee' AND employee_id IS NOT NULL AND department IS NULL) OR "
            "(scope_type = 'department' AND employee_id IS NULL AND department IS NOT NULL AND length(trim(department)) > 0)",
            name="ck_hr_shift_assignment_scope_target",
        ),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="ck_hr_shift_assignment_effective_dates"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    employee_id: Mapped[str | None] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=True, index=True)
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("hr_branches.id", ondelete="RESTRICT"), nullable=True, index=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    shift_type_id: Mapped[str] = mapped_column(ForeignKey("hr_shift_types.id", ondelete="RESTRICT"), nullable=False, index=True)
    weekdays: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    supersedes_assignment_id: Mapped[str | None] = mapped_column(ForeignKey("hr_shift_assignments.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HRShiftRosterEntry(Base):
    """One resolved schedule outcome per employee and local shift-start work date."""

    __tablename__ = "hr_shift_roster_entries"
    __table_args__ = (
        UniqueConstraint("employee_id", "work_date", name="uq_hr_shift_roster_employee_day"),
        CheckConstraint(
            "status IN ('scheduled', 'weekly_off', 'holiday', 'cancelled')",
            name="ck_hr_shift_roster_status",
        ),
        CheckConstraint(
            "(status = 'scheduled' AND shift_type_id IS NOT NULL AND scheduled_start_at_utc IS NOT NULL "
            "AND scheduled_end_at_utc IS NOT NULL AND scheduled_end_at_utc > scheduled_start_at_utc) OR "
            "(status <> 'scheduled' AND shift_type_id IS NULL AND scheduled_start_at_utc IS NULL AND scheduled_end_at_utc IS NULL)",
            name="ck_hr_shift_roster_schedule_fields",
        ),
        CheckConstraint(
            "is_override = false OR length(trim(override_reason)) > 0",
            name="ck_hr_shift_roster_override_reason",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    shift_type_id: Mapped[str | None] = mapped_column(ForeignKey("hr_shift_types.id", ondelete="RESTRICT"), nullable=True)
    source_assignment_id: Mapped[str | None] = mapped_column(ForeignKey("hr_shift_assignments.id", ondelete="SET NULL"), nullable=True, index=True)
    is_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    override_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("hr_branches.id", ondelete="RESTRICT"), nullable=True, index=True)
    department_snapshot: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    timezone_name: Mapped[str] = mapped_column(String(64), nullable=False)
    scheduled_start_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_end_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shift_code_snapshot: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    shift_name_snapshot: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    break_rules_snapshot: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    policy_version_id: Mapped[str | None] = mapped_column(ForeignKey("hr_workforce_policy_versions.id", ondelete="RESTRICT"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
