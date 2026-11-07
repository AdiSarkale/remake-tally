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
    # Existing rows are demo records. Give them a stable seed date so demo
    # payroll can run; preserve any date already populated. End dates remain
    # unknown (NULL) unless the demo data explicitly supplies one.
    op.execute(
        sa.text("UPDATE employees SET joining_date = '2025-01-01' WHERE joining_date IS NULL")
    )
    op.add_column(
        "hr_payroll_settings",
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Asia/Kolkata"),
    )


def downgrade() -> None:
    op.drop_column("hr_payroll_settings", "timezone")
    op.drop_column("employees", "end_date")
    op.drop_column("employees", "joining_date")
