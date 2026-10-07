"""Add explicit tenant decommission lifecycle state and audit events."""

from alembic import op
import sqlalchemy as sa

revision = "control_005"
down_revision = "control_004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_companies",
        sa.Column("decommissioned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenant_companies",
        sa.Column("decommission_reason", sa.Text(), nullable=True),
    )

    op.create_table(
        "tenant_admin_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("company_code", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_tenant_admin_events_company_id",
        "tenant_admin_events",
        ["company_id"],
    )
    op.create_index(
        "ix_tenant_admin_events_company_code",
        "tenant_admin_events",
        ["company_code"],
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_admin_events_company_code", table_name="tenant_admin_events")
    op.drop_index("ix_tenant_admin_events_company_id", table_name="tenant_admin_events")
    op.drop_table("tenant_admin_events")
    op.drop_column("tenant_companies", "decommission_reason")
    op.drop_column("tenant_companies", "decommissioned_at")
