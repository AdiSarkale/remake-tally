"""Add warehouse association to material reservations.
Revision ID: d2e5f8a1c370
Revises: c1d4e7f9a250
"""
from alembic import op
import sqlalchemy as sa
revision="d2e5f8a1c370"
down_revision="c1d4e7f9a250"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("stock_reservations",sa.Column("warehouse_id",sa.String(36),nullable=True))
    op.create_foreign_key("fk_stock_reservations_warehouse_id","stock_reservations","warehouses",["warehouse_id"],["id"])
    op.create_index("ix_stock_reservations_warehouse_id","stock_reservations",["warehouse_id"])

def downgrade():
    op.drop_index("ix_stock_reservations_warehouse_id",table_name="stock_reservations")
    op.drop_constraint("fk_stock_reservations_warehouse_id","stock_reservations",type_="foreignkey")
    op.drop_column("stock_reservations","warehouse_id")
