"""Record tenant schema migration lifecycle events."""

from alembic import op
import sqlalchemy as sa

revision = "control_004"
down_revision = "control_003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_migration_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("company_code", sa.String(length=32), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("from_revision", sa.String(length=128), nullable=True),
        sa.Column("to_revision", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("triggered_by", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_tenant_migration_events_company_id",
        "tenant_migration_events",
        ["company_id"],
    )
    op.create_index(
        "ix_tenant_migration_events_company_code",
        "tenant_migration_events",
        ["company_code"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tenant_migration_events_company_code",
        table_name="tenant_migration_events",
    )
    op.drop_index(
        "ix_tenant_migration_events_company_id",
        table_name="tenant_migration_events",
    )
    op.drop_table("tenant_migration_events")
