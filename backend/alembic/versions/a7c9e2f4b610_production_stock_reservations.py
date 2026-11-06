"""Add production-order raw material reservations.

Revision ID: a7c9e2f4b610
Revises: f5c8d3e0a2b7
"""
from alembic import op
import sqlalchemy as sa

revision = "a7c9e2f4b610"
down_revision = "f5c8d3e0a2b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_reservations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("production_order_id", sa.String(36), sa.ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_id", sa.String(36), sa.ForeignKey("raw_materials.id"), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("consumed_quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="Reserved"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("production_order_id", "material_id", name="uq_stock_reservation_order_material"),
    )
    op.create_index("ix_stock_reservations_production_order_id", "stock_reservations", ["production_order_id"])
    op.create_index("ix_stock_reservations_material_id", "stock_reservations", ["material_id"])
    op.create_index("ix_stock_reservations_status", "stock_reservations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_stock_reservations_status", table_name="stock_reservations")
    op.drop_index("ix_stock_reservations_material_id", table_name="stock_reservations")
    op.drop_index("ix_stock_reservations_production_order_id", table_name="stock_reservations")
    op.drop_table("stock_reservations")
