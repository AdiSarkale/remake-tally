"""Add forced first-login password state to users.

Revision ID: 8d4f6a1b2c3e
Revises: 7c2d9e4f1a6
"""
from alembic import op
import sqlalchemy as sa

revision = "8d4f6a1b2c3e"
down_revision = "7c2d9e4f1a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("users", "must_change_password", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
