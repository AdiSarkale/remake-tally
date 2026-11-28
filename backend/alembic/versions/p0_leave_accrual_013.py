"""Add effective-dated leave accrual policy and monthly ledger.

Revision ID: p0_leave_accrual_013
Revises: p0_granular_authz_012
"""
from alembic import op
import sqlalchemy as sa

revision = "p0_leave_accrual_013"
down_revision = "p0_granular_authz_012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("hr_leave_types") as batch:
        batch.add_column(sa.Column("accrual_method", sa.String(24), nullable=False, server_default="annual_upfront"))
        batch.add_column(sa.Column("accrual_effective_from", sa.Date(), nullable=False, server_default="2000-01-01"))
    op.create_table(
        "hr_leave_accrual_ledger",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("leave_type_id", sa.String(36), sa.ForeignKey("hr_leave_types.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("run_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("employee_id", "leave_type_id", "year", "month", name="uq_hr_leave_accrual_period"),
    )
    op.create_index("ix_hr_leave_accrual_ledger_employee_id", "hr_leave_accrual_ledger", ["employee_id"])
    op.create_index("ix_hr_leave_accrual_ledger_leave_type_id", "hr_leave_accrual_ledger", ["leave_type_id"])


def downgrade() -> None:
    op.drop_index("ix_hr_leave_accrual_ledger_leave_type_id", table_name="hr_leave_accrual_ledger")
    op.drop_index("ix_hr_leave_accrual_ledger_employee_id", table_name="hr_leave_accrual_ledger")
    op.drop_table("hr_leave_accrual_ledger")
    with op.batch_alter_table("hr_leave_types") as batch:
        batch.drop_column("accrual_effective_from")
        batch.drop_column("accrual_method")
