"""Track tenant provisioning state in the control plane."""

from alembic import op
import sqlalchemy as sa

revision = "control_002"
down_revision = "control_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_companies",
        sa.Column(
            "provisioning_status",
            sa.String(length=24),
            nullable=False,
            server_default="ready",
        ),
    )


def downgrade() -> None:
    op.drop_column("tenant_companies", "provisioning_status")
