"""Add employee type classification.

Revision ID: employee_type_001
Revises: 8d4f6a1b2c3e
"""

from alembic import op
import sqlalchemy as sa

revision = "employee_type_001"
down_revision = "8d4f6a1b2c3e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column(
            "employee_type",
            sa.String(length=20),
            nullable=False,
            server_default="staff",
        ),
    )
    op.create_index(
        "ix_employees_employee_type",
        "employees",
        ["employee_type"],
        unique=False,
    )
    # Existing employees in the production/work-centre model are shop-floor
    # employees. Staff remains the safe default for future/general HR records.
    op.execute(
        sa.text(
            "UPDATE employees "
            "SET employee_type = 'shop_floor' "
            "WHERE department = 'Production'"
        )
    )
    op.alter_column("employees", "employee_type", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_employees_employee_type", table_name="employees")
    op.drop_column("employees", "employee_type")
