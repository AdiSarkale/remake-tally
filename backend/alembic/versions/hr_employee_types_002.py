"""Create tenant-managed employee types and seed legacy types.

Revision ID: hr_employee_types_002
Revises: hr_role_001
"""

from alembic import op
import sqlalchemy as sa

revision = "hr_employee_types_002"
down_revision = "hr_role_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employee_types",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("payout_classification", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code", name="uq_employee_type_code"),
        sa.UniqueConstraint("name", name="uq_employee_type_name"),
    )
    op.create_index("ix_employee_types_code", "employee_types", ["code"])
    op.create_index("ix_employee_types_name", "employee_types", ["name"])
    bind = op.get_bind()
    # Preserve the existing fixed values as tenant-local managed types.
    bind.execute(sa.text(
        "INSERT INTO employee_types (id, code, name, payout_classification, active) "
        "VALUES ('legacy-shop-floor', 'shop_floor', 'Shop floor', 'shop_floor', TRUE)"
    ))
    bind.execute(sa.text(
        "INSERT INTO employee_types (id, code, name, payout_classification, active) "
        "VALUES ('legacy-staff', 'staff', 'Staff', 'staff', TRUE)"
    ))


def downgrade() -> None:
    op.drop_index("ix_employee_types_name", table_name="employee_types")
    op.drop_index("ix_employee_types_code", table_name="employee_types")
    op.drop_table("employee_types")
