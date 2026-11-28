"""Add HR leave types, balances and requests.

Revision ID: p0_hr_leave_008
Revises: p0_authorization_007
"""
from alembic import op
import sqlalchemy as sa

revision = "p0_hr_leave_008"
down_revision = "p0_authorization_007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hr_leave_types",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("annual_entitlement", sa.Float(), nullable=False, server_default="0"),
        sa.Column("carry_forward_limit", sa.Float(), nullable=False, server_default="0"),
        sa.Column("count_week_offs", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("count_holidays", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_half_day", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_hr_leave_type_code"),
    )
    op.create_index("ix_hr_leave_types_code", "hr_leave_types", ["code"])
    op.create_table(
        "hr_leave_balances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("leave_type_id", sa.String(36), sa.ForeignKey("hr_leave_types.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("opening_balance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("accrued", sa.Float(), nullable=False, server_default="0"),
        sa.Column("adjusted", sa.Float(), nullable=False, server_default="0"),
        sa.Column("used", sa.Float(), nullable=False, server_default="0"),
        sa.Column("updated_by", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("employee_id", "leave_type_id", "year", name="uq_hr_leave_balance_period"),
    )
    op.create_index("ix_hr_leave_balances_employee_id", "hr_leave_balances", ["employee_id"])
    op.create_index("ix_hr_leave_balances_leave_type_id", "hr_leave_balances", ["leave_type_id"])
    op.create_table(
        "hr_leave_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("leave_type_id", sa.String(36), sa.ForeignKey("hr_leave_types.id"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("total_days", sa.Float(), nullable=False),
        sa.Column("half_day", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.String(64), nullable=False),
        sa.Column("approver_username", sa.String(64), nullable=False),
        sa.Column("decided_by", sa.String(64), nullable=False, server_default=""),
        sa.Column("decision_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_hr_leave_requests_employee_id", "hr_leave_requests", ["employee_id"])
    op.create_index("ix_hr_leave_requests_leave_type_id", "hr_leave_requests", ["leave_type_id"])
    op.create_index("ix_hr_leave_requests_start_date", "hr_leave_requests", ["start_date"])
    op.create_index("ix_hr_leave_requests_end_date", "hr_leave_requests", ["end_date"])
    op.create_index("ix_hr_leave_requests_status", "hr_leave_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_hr_leave_requests_status", table_name="hr_leave_requests")
    op.drop_index("ix_hr_leave_requests_end_date", table_name="hr_leave_requests")
    op.drop_index("ix_hr_leave_requests_start_date", table_name="hr_leave_requests")
    op.drop_index("ix_hr_leave_requests_leave_type_id", table_name="hr_leave_requests")
    op.drop_index("ix_hr_leave_requests_employee_id", table_name="hr_leave_requests")
    op.drop_table("hr_leave_requests")
    op.drop_index("ix_hr_leave_balances_leave_type_id", table_name="hr_leave_balances")
    op.drop_index("ix_hr_leave_balances_employee_id", table_name="hr_leave_balances")
    op.drop_table("hr_leave_balances")
    op.drop_index("ix_hr_leave_types_code", table_name="hr_leave_types")
    op.drop_table("hr_leave_types")
