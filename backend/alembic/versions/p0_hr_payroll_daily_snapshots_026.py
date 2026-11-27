"""Add immutable payroll daily provenance and readiness exceptions.
Revision ID: p0_hr_payroll_daily_snapshots_026
Revises: p0_hr_overtime_core_approval_025
"""
from alembic import op
import sqlalchemy as sa

revision = "p0_hr_payroll_daily_snapshots_026"
down_revision = "p0_hr_overtime_core_approval_025"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hr_payroll_daily_snapshots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("payroll_run_id", sa.String(length=36), sa.ForeignKey("hr_payroll_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.String(length=36), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("payroll_run_id", "employee_id", "work_date", name="uq_hr_payroll_daily_snapshot"),
    )
    op.create_index("ix_hr_payroll_daily_snapshots_payroll_run_id", "hr_payroll_daily_snapshots", ["payroll_run_id"])
    op.create_index("ix_hr_payroll_daily_snapshots_employee_id", "hr_payroll_daily_snapshots", ["employee_id"])
    op.create_index("ix_hr_payroll_daily_snapshots_work_date", "hr_payroll_daily_snapshots", ["work_date"])

    op.create_table(
        "hr_payroll_exceptions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("payroll_run_id", sa.String(length=36), sa.ForeignKey("hr_payroll_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.String(length=36), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("work_date", sa.Date(), nullable=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("source_reference", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("resolved_by", sa.String(length=64), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("payroll_run_id", "employee_id", "work_date", "code", name="uq_hr_payroll_exception_scope"),
        sa.CheckConstraint("severity IN ('blocking', 'warning')", name="ck_hr_payroll_exception_severity"),
        sa.CheckConstraint("status IN ('open', 'resolved', 'acknowledged')", name="ck_hr_payroll_exception_status"),
    )
    op.create_index("ix_hr_payroll_exceptions_payroll_run_id", "hr_payroll_exceptions", ["payroll_run_id"])
    op.create_index("ix_hr_payroll_exceptions_employee_id", "hr_payroll_exceptions", ["employee_id"])
    op.create_index("ix_hr_payroll_exceptions_work_date", "hr_payroll_exceptions", ["work_date"])


def downgrade():
    op.drop_index("ix_hr_payroll_exceptions_work_date", table_name="hr_payroll_exceptions")
    op.drop_index("ix_hr_payroll_exceptions_employee_id", table_name="hr_payroll_exceptions")
    op.drop_index("ix_hr_payroll_exceptions_payroll_run_id", table_name="hr_payroll_exceptions")
    op.drop_table("hr_payroll_exceptions")
    op.drop_index("ix_hr_payroll_daily_snapshots_work_date", table_name="hr_payroll_daily_snapshots")
    op.drop_index("ix_hr_payroll_daily_snapshots_employee_id", table_name="hr_payroll_daily_snapshots")
    op.drop_index("ix_hr_payroll_daily_snapshots_payroll_run_id", table_name="hr_payroll_daily_snapshots")
    op.drop_table("hr_payroll_daily_snapshots")
