"""Add tenant HR salary profiles, monthly attendance, calendar and payroll.

Revision ID: hr_payroll_005
Revises: hr_employee_type_code_length_004
"""
from alembic import op
import sqlalchemy as sa

revision = "hr_payroll_005"
down_revision = "hr_employee_type_code_length_004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hr_payroll_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("salary_count_mode", sa.String(20), nullable=False, server_default="working_days"),
        sa.Column("monthly_salary_days", sa.Integer(), nullable=False, server_default="26"),
        sa.Column("week_off_days", sa.String(20), nullable=False, server_default="5,6"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "hr_calendar_days",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("day_type", sa.String(20), nullable=False),
        sa.Column("description", sa.String(240), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("work_date", name="uq_hr_calendar_work_date"),
    )
    op.create_index("ix_hr_calendar_days_work_date", "hr_calendar_days", ["work_date"], unique=False)
    op.create_table(
        "employee_salary_profiles",
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("annual_salary", sa.Numeric(14, 2), nullable=False),
        sa.Column("basic_pct", sa.Numeric(5, 2), nullable=False, server_default="50"),
        sa.Column("hra_pct", sa.Numeric(5, 2), nullable=False, server_default="40"),
        sa.Column("da_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("conveyance_monthly", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("medical_allowance_monthly", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("pf_pct", sa.Numeric(5, 2), nullable=False, server_default="12"),
        sa.Column("professional_tax_monthly", sa.Numeric(12, 2), nullable=False, server_default="200"),
        sa.Column("tds_monthly", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "employee_attendance",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="present"),
        sa.Column("punch_in", sa.DateTime(timezone=True), nullable=True),
        sa.Column("punch_out", sa.DateTime(timezone=True), nullable=True),
        sa.Column("overtime_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("employee_id", "work_date", name="uq_hr_employee_attendance_day"),
    )
    op.create_index("ix_employee_attendance_employee_id", "employee_attendance", ["employee_id"], unique=False)
    op.create_index("ix_employee_attendance_work_date", "employee_attendance", ["work_date"], unique=False)
    op.create_table(
        "hr_payroll_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="finalized"),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("year", "month", name="uq_hr_payroll_period"),
    )
    op.create_table(
        "hr_payroll_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("payroll_run_id", sa.String(36), sa.ForeignKey("hr_payroll_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("employee_code", sa.String(32), nullable=False),
        sa.Column("employee_name", sa.String(120), nullable=False),
        sa.Column("department", sa.String(120), nullable=False, server_default=""),
        sa.Column("annual_salary", sa.Numeric(14, 2), nullable=False),
        sa.Column("monthly_gross", sa.Numeric(14, 2), nullable=False),
        sa.Column("basic", sa.Numeric(14, 2), nullable=False),
        sa.Column("hra", sa.Numeric(14, 2), nullable=False),
        sa.Column("da", sa.Numeric(14, 2), nullable=False),
        sa.Column("conveyance", sa.Numeric(14, 2), nullable=False),
        sa.Column("medical_allowance", sa.Numeric(14, 2), nullable=False),
        sa.Column("special_allowance", sa.Numeric(14, 2), nullable=False),
        sa.Column("employee_pf", sa.Numeric(14, 2), nullable=False),
        sa.Column("professional_tax", sa.Numeric(14, 2), nullable=False),
        sa.Column("tds", sa.Numeric(14, 2), nullable=False),
        sa.Column("absence_deduction", sa.Numeric(14, 2), nullable=False),
        sa.Column("overtime_pay", sa.Numeric(14, 2), nullable=False),
        sa.Column("net_pay", sa.Numeric(14, 2), nullable=False),
        sa.Column("present_days", sa.Numeric(7, 2), nullable=False, server_default="0"),
        sa.Column("half_days", sa.Numeric(7, 2), nullable=False, server_default="0"),
        sa.Column("absent_days", sa.Numeric(7, 2), nullable=False, server_default="0"),
        sa.Column("paid_leave_days", sa.Numeric(7, 2), nullable=False, server_default="0"),
        sa.Column("unpaid_leave_days", sa.Numeric(7, 2), nullable=False, server_default="0"),
        sa.Column("overtime_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("payroll_run_id", "employee_id", name="uq_hr_payroll_employee"),
    )
    op.create_index("ix_hr_payroll_items_payroll_run_id", "hr_payroll_items", ["payroll_run_id"], unique=False)
    op.create_index("ix_hr_payroll_items_employee_id", "hr_payroll_items", ["employee_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_hr_payroll_items_employee_id", table_name="hr_payroll_items")
    op.drop_index("ix_hr_payroll_items_payroll_run_id", table_name="hr_payroll_items")
    op.drop_table("hr_payroll_items")
    op.drop_table("hr_payroll_runs")
    op.drop_index("ix_employee_attendance_work_date", table_name="employee_attendance")
    op.drop_index("ix_employee_attendance_employee_id", table_name="employee_attendance")
    op.drop_table("employee_attendance")
    op.drop_table("employee_salary_profiles")
    op.drop_index("ix_hr_calendar_days_work_date", table_name="hr_calendar_days")
    op.drop_table("hr_calendar_days")
    op.drop_table("hr_payroll_settings")
