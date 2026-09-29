"""Create control-plane tenant registry.

Run this migration against CONTROL_DATABASE_URL only.
"""

from alembic import op
import sqlalchemy as sa

revision = "control_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_companies",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("database_url", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_tenant_companies_code", "tenant_companies", ["code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_tenant_companies_code", table_name="tenant_companies")
    op.drop_table("tenant_companies")
