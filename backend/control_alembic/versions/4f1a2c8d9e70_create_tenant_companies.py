"""create tenant company control-plane registry

Revision ID: 4f1a2c8d9e70
Revises:
Create Date: 2026-09-28

The control database contains routing/provisioning metadata only. Tenant ERP
schema migrations remain under backend/alembic.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4f1a2c8d9e70"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_companies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("database_secret_ref", sa.String(length=160), nullable=False),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "provisioning_status",
            sa.String(length=24),
            nullable=False,
            server_default="provisioning",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name="tenant_companies_pkey"),
        sa.UniqueConstraint("code", name="tenant_companies_code_key"),
    )
    op.create_index(
        "ix_tenant_companies_code",
        "tenant_companies",
        ["code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_companies_code", table_name="tenant_companies")
    op.drop_table("tenant_companies")
