"""Replace stored tenant DB URLs with secret references.

Existing control-plane rows must be migrated before this revision is applied:
for each company, create a secret for its new database_secret_ref and update the
row. This migration deliberately refuses to guess or copy a database credential
into the new reference column.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "control_003"
down_revision = "control_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(text("SELECT COUNT(*) FROM tenant_companies")).scalar_one()
    if existing:
        raise RuntimeError(
            "control_003 requires tenant DB secrets to be provisioned before "
            "migration; do not copy database URLs into the secret reference column"
        )

    op.add_column(
        "tenant_companies",
        sa.Column("database_secret_ref", sa.String(length=160), nullable=False),
    )
    op.drop_column("tenant_companies", "database_url")


def downgrade() -> None:
    raise RuntimeError(
        "control_003 is irreversible: database credentials were intentionally "
        "removed from the control database"
    )
