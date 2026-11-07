"""Add branch and effective-dated employee organization assignments.

Revision ID: p0_org_structure_011
Revises: p0_authz_seed_010
"""
from alembic import op
import sqlalchemy as sa

revision = "p0_org_structure_011"
down_revision = "p0_authz_seed_010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hr_branches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("address", sa.Text(), nullable=False, server_default=""),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_hr_branch_code"),
    )
    op.create_index("ix_hr_branches_code", "hr_branches", ["code"])
    op.create_table(
        "employee_org_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("hr_branches.id"), nullable=True),
        sa.Column("manager_employee_id", sa.String(36), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("department", sa.String(120), nullable=False, server_default=""),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("employee_id", "valid_from", name="uq_employee_org_assignment_start"),
    )
    for col in ("employee_id", "branch_id", "manager_employee_id", "valid_from", "valid_to"):
        op.create_index(f"ix_employee_org_assignments_{col}", "employee_org_assignments", [col])


def downgrade() -> None:
    for col in ("valid_to", "valid_from", "manager_employee_id", "branch_id", "employee_id"):
        op.drop_index(f"ix_employee_org_assignments_{col}", table_name="employee_org_assignments")
    op.drop_table("employee_org_assignments")
    op.drop_index("ix_hr_branches_code", table_name="hr_branches")
    op.drop_table("hr_branches")
