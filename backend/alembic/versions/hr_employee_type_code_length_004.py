"""Widen employee type codes to match tenant-managed type definitions.

Revision ID: hr_employee_type_code_length_004
Revises: hr_employee_codes_003
"""

from alembic import op
import sqlalchemy as sa

revision = "hr_employee_type_code_length_004"
down_revision = "hr_employee_codes_003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.alter_column(
            "employee_type",
            existing_type=sa.String(length=20),
            type_=sa.String(length=32),
            existing_nullable=False,
        )


def downgrade() -> None:
    # Downgrade can only succeed if no tenant-defined employee type code
    # longer than 20 characters is currently assigned to an employee.
    with op.batch_alter_table("employees") as batch_op:
        batch_op.alter_column(
            "employee_type",
            existing_type=sa.String(length=32),
            type_=sa.String(length=20),
            existing_nullable=False,
        )
