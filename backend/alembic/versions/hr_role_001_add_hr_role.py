"""Add dedicated HR role for tenant user accounts.

Revision ID: hr_role_001
Revises: employee_type_001
"""

from alembic import op

revision = "hr_role_001"
down_revision = "employee_type_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLAlchemy persists Enum member names (admin/accountant/operator/hr).
    # SQLite stores the enum as a string, while PostgreSQL uses a native enum.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE role ADD VALUE IF NOT EXISTS 'hr'")


def downgrade() -> None:
    # PostgreSQL cannot safely remove an enum value while rows or prepared
    # statements may reference it. Keep the value; application code can stop
    # offering the role in a future downgrade if required.
    pass
