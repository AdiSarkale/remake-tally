"""Add employee-account links and explicit role permission grants.

Revision ID: p0_authorization_007
Revises: hr_timezone_006
"""
from alembic import op
import sqlalchemy as sa

revision = "p0_authorization_007"
down_revision = "hr_timezone_006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employee_user_links",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.String(length=36), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_employee_user_links_user"),
        sa.UniqueConstraint("employee_id", name="uq_employee_user_links_employee"),
    )
    op.create_index("ix_employee_user_links_user_id", "employee_user_links", ["user_id"])
    op.create_index("ix_employee_user_links_employee_id", "employee_user_links", ["employee_id"])
    op.create_table(
        "role_permission_grants",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column("feature", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("data_scope", sa.String(length=24), nullable=False, server_default="tenant"),
        sa.Column("allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("role", "module", "feature", "action", "data_scope", name="uq_role_permission_grant"),
    )
    op.create_index("ix_role_permission_grants_role", "role_permission_grants", ["role"])
    op.create_index("ix_role_permission_grants_module", "role_permission_grants", ["module"])


def downgrade() -> None:
    op.drop_index("ix_role_permission_grants_module", table_name="role_permission_grants")
    op.drop_index("ix_role_permission_grants_role", table_name="role_permission_grants")
    op.drop_table("role_permission_grants")
    op.drop_index("ix_employee_user_links_employee_id", table_name="employee_user_links")
    op.drop_index("ix_employee_user_links_user_id", table_name="employee_user_links")
    op.drop_table("employee_user_links")
