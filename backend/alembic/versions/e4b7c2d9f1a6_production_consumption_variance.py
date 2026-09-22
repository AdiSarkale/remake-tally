"""Add planned quantity to production consumption.

Revision ID: e4b7c2d9f1a6
Revises: d8a3b6c1e9f2
"""
from alembic import op
import sqlalchemy as sa

revision = "e4b7c2d9f1a6"
down_revision = "d8a3b6c1e9f2"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("production_consumption", sa.Column("planned_quantity", sa.Float(), nullable=True))
    op.execute("UPDATE production_consumption SET planned_quantity = quantity")
    with op.batch_alter_table("production_consumption") as batch:
        batch.alter_column("planned_quantity", nullable=False, server_default="0")

def downgrade() -> None:
    op.drop_column("production_consumption", "planned_quantity")
