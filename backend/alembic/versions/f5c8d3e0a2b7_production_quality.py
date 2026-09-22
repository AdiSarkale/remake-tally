"""Add quality status fields to production entries.

Revision ID: f5c8d3e0a2b7
Revises: e4b7c2d9f1a6
"""
from alembic import op
import sqlalchemy as sa

revision = "f5c8d3e0a2b7"
down_revision = "e4b7c2d9f1a6"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("production_entries", sa.Column("quality_status", sa.String(32), nullable=True))
    op.add_column("production_entries", sa.Column("accepted_qty", sa.Float(), nullable=True))
    op.add_column("production_entries", sa.Column("rejected_qty", sa.Float(), nullable=True))
    op.add_column("production_entries", sa.Column("quality_remarks", sa.Text(), nullable=True))
    op.execute("UPDATE production_entries SET quality_status = 'Pending', accepted_qty = quantity, rejected_qty = 0, quality_remarks = ''")
    with op.batch_alter_table("production_entries") as batch:
        batch.alter_column("quality_status", nullable=False, server_default="Pending")
        batch.alter_column("accepted_qty", nullable=False, server_default="0")
        batch.alter_column("rejected_qty", nullable=False, server_default="0")
        batch.alter_column("quality_remarks", nullable=False, server_default="")

def downgrade() -> None:
    op.drop_column("production_entries", "quality_remarks")
    op.drop_column("production_entries", "rejected_qty")
    op.drop_column("production_entries", "accepted_qty")
    op.drop_column("production_entries", "quality_status")
