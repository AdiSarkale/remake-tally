"""Add departments and HOD-scoped approval requests."""

from alembic import op
import sqlalchemy as sa

revision = "7c2d9e4f1a6"
down_revision = "8c6bf6b64ea0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "departments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("hod_username", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_departments_code", "departments", ["code"])
    op.create_index("ix_departments_name", "departments", ["name"])
    op.create_index("ix_departments_hod_username", "departments", ["hod_username"])

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("department_id", sa.String(length=36), nullable=False),
        sa.Column("request_type", sa.String(length=48), nullable=False, server_default="General"),
        sa.Column("reference_id", sa.String(length=36), nullable=True),
        sa.Column("reference_no", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("requested_by", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="Pending"),
        sa.Column("remarks", sa.Text(), nullable=False, server_default=""),
        sa.Column("decided_by", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_requests_department_id", "approval_requests", ["department_id"])
    op.create_index("ix_approval_requests_reference_id", "approval_requests", ["reference_id"])
    op.create_index("ix_approval_requests_reference_no", "approval_requests", ["reference_no"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])


def downgrade():
    op.drop_index("ix_approval_requests_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_reference_no", table_name="approval_requests")
    op.drop_index("ix_approval_requests_reference_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_department_id", table_name="approval_requests")
    op.drop_table("approval_requests")
    op.drop_index("ix_departments_hod_username", table_name="departments")
    op.drop_index("ix_departments_name", table_name="departments")
    op.drop_index("ix_departments_code", table_name="departments")
    op.drop_table("departments")
