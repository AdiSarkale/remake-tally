"""Add employment dates and tenant timezone configuration.

Revision ID: hr_timezone_006
Revises: hr_payroll_005
"""
from alembic import op
import sqlalchemy as sa

revision = "hr_timezone_006"
down_revision = "hr_payroll_005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column("joining_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "employees",
        sa.Column("end_date", sa.Date(), nullable=True),
    )
    # Existing records predate employment dates. Backfill a conservative date
    # so historical payroll eligibility is not silently shortened.
    op.execute("UPDATE employees SET joining_date = CURRENT_DATE WHERE joining_date IS NULL")
    with op.batch_alter_table("employees") as batch_op:
        batch_op.alter_column(
            "joining_date",
            existing_type=sa.Date(),
            nullable=False,
        )
    op.add_column(
        "hr_payroll_settings",
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Asia/Kolkata"),
    )


def downgrade() -> None:
    op.drop_column("hr_payroll_settings", "timezone")
    op.drop_column("employees", "end_date")
    op.drop_column("employees", "joining_date")
