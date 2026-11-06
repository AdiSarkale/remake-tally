"""Add warehouse-level stock balances and production WIP transfers.
Revision ID: c1d4e7f9a250
Revises: b8d4f1a6c920
"""
from alembic import op
import sqlalchemy as sa
revision="c1d4e7f9a250"
down_revision="b8d4f1a6c920"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("inventory_movements",sa.Column("warehouse_id",sa.String(36),nullable=True));op.create_foreign_key("fk_inventory_movements_warehouse_id","inventory_movements","warehouses",["warehouse_id"],["id"]);op.create_index("ix_inventory_movements_warehouse_id","inventory_movements",["warehouse_id"])
    for name in ["source","wip","target"]:
        op.add_column("production_orders",sa.Column(f"{name}_warehouse_id",sa.String(36),nullable=True));op.create_foreign_key(f"fk_production_orders_{name}_warehouse","production_orders","warehouses",[f"{name}_warehouse_id"],["id"])
    op.create_table("warehouse_stock",sa.Column("id",sa.String(36),primary_key=True),sa.Column("warehouse_id",sa.String(36),sa.ForeignKey("warehouses.id",ondelete="CASCADE"),nullable=False),sa.Column("item_kind",sa.Enum("product","material","scrap",name="itemkind"),nullable=False),sa.Column("item_id",sa.String(36),nullable=False),sa.Column("item_name",sa.String(160),nullable=False),sa.Column("quantity",sa.Float(),nullable=False,server_default="0"),sa.Column("unit",sa.String(16),nullable=False),sa.UniqueConstraint("warehouse_id","item_kind","item_id",name="uq_warehouse_item_stock"))
    for name in ["warehouse_id","item_kind","item_id"]: op.create_index(f"ix_warehouse_stock_{name}","warehouse_stock",[name])
    op.create_table("production_material_transfers",sa.Column("id",sa.String(36),primary_key=True),sa.Column("production_order_id",sa.String(36),sa.ForeignKey("production_orders.id",ondelete="CASCADE"),nullable=False),sa.Column("material_id",sa.String(36),sa.ForeignKey("raw_materials.id"),nullable=False),sa.Column("source_warehouse_id",sa.String(36),sa.ForeignKey("warehouses.id"),nullable=False),sa.Column("target_warehouse_id",sa.String(36),sa.ForeignKey("warehouses.id"),nullable=False),sa.Column("quantity",sa.Float(),nullable=False),sa.Column("transferred_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_index("ix_production_material_transfers_production_order_id","production_material_transfers",["production_order_id"]);op.create_index("ix_production_material_transfers_material_id","production_material_transfers",["material_id"])

def downgrade():
    op.drop_index("ix_production_material_transfers_material_id",table_name="production_material_transfers");op.drop_index("ix_production_material_transfers_production_order_id",table_name="production_material_transfers");op.drop_table("production_material_transfers")
    for name in ["warehouse_id","item_kind","item_id"]: op.drop_index(f"ix_warehouse_stock_{name}",table_name="warehouse_stock")
    op.drop_table("warehouse_stock")
    for name in ["source","wip","target"]: op.drop_constraint(f"fk_production_orders_{name}_warehouse","production_orders",type_="foreignkey");op.drop_column("production_orders",f"{name}_warehouse_id")
    op.drop_index("ix_inventory_movements_warehouse_id",table_name="inventory_movements");op.drop_constraint("fk_inventory_movements_warehouse_id","inventory_movements",type_="foreignkey");op.drop_column("inventory_movements","warehouse_id")
