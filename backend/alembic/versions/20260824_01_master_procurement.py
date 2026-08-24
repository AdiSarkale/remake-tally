"""add database masters and purchasing workflow

Revision ID: 20260824_01
Revises: 8c6f2f87a123
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import uuid

revision: str = "20260824_01"
down_revision: Union[str, Sequence[str], None] = "8c6f2f87a123"
branch_labels = None
depends_on = None


def upgrade() -> None:
    purchase_order_status = sa.Enum(
        "draft", "sent", "partially_received", "received", "cancelled",
        name="purchaseorderstatus",
    )
    purchase_order_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "plants",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_plants_code", "plants", ["code"], unique=True)

    op.create_table(
        "warehouses",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("plant_id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["plant_id"], ["plants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_warehouses_plant_id", "warehouses", ["plant_id"], unique=False)
    op.create_index("ix_warehouses_code", "warehouses", ["code"], unique=True)

    op.create_table(
        "supplier_products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("supplier_id", sa.String(36), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("supplier_code", sa.String(64), nullable=False),
        sa.Column("purchase_rate", sa.Float(), nullable=False),
        sa.Column("minimum_order_qty", sa.Float(), nullable=False),
        sa.Column("lead_time_days", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["raw_materials.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["parties.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_supplier_products_supplier_id", "supplier_products", ["supplier_id"], unique=False)
    op.create_index("ix_supplier_products_product_id", "supplier_products", ["product_id"], unique=False)

    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("po_no", sa.String(32), nullable=False),
        sa.Column("po_date", sa.Date(), nullable=False),
        sa.Column("expected_date", sa.Date(), nullable=True),
        sa.Column("supplier_id", sa.String(36), nullable=False),
        sa.Column("supplier_name", sa.String(160), nullable=False),
        sa.Column("warehouse_id", sa.String(36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("status", purchase_order_status, nullable=False),
        sa.Column("sub_total", sa.Float(), nullable=False),
        sa.Column("gst_total", sa.Float(), nullable=False),
        sa.Column("grand_total", sa.Float(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("po_no"),
    )
    op.create_index("ix_purchase_orders_po_date", "purchase_orders", ["po_date"], unique=False)
    op.create_index("ix_purchase_orders_po_no", "purchase_orders", ["po_no"], unique=True)

    op.create_table(
        "purchase_order_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("purchase_order_id", sa.String(36), nullable=False),
        sa.Column("material_id", sa.String(36), nullable=False),
        sa.Column("material_name", sa.String(160), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("received_quantity", sa.Float(), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("gst_rate", sa.Float(), nullable=False),
        sa.Column("taxable", sa.Float(), nullable=False),
        sa.Column("tax", sa.Float(), nullable=False),
        sa.Column("total", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["material_id"], ["raw_materials.id"]),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "grns",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("grn_no", sa.String(32), nullable=False),
        sa.Column("grn_date", sa.Date(), nullable=False),
        sa.Column("purchase_order_id", sa.String(36), nullable=False),
        sa.Column("po_no", sa.String(32), nullable=False),
        sa.Column("supplier_id", sa.String(36), nullable=False),
        sa.Column("supplier_name", sa.String(160), nullable=False),
        sa.Column("warehouse_id", sa.String(36), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("grn_no"),
    )
    op.create_index("ix_grns_grn_date", "grns", ["grn_date"], unique=False)
    op.create_index("ix_grns_grn_no", "grns", ["grn_no"], unique=True)

    op.create_table(
        "grn_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("grn_id", sa.String(36), nullable=False),
        sa.Column("material_id", sa.String(36), nullable=False),
        sa.Column("material_name", sa.String(160), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("batch_no", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["grn_id"], ["grns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["raw_materials.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "customer_pos",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("po_no", sa.String(64), nullable=False),
        sa.Column("po_date", sa.Date(), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=False),
        sa.Column("customer_name", sa.String(160), nullable=False),
        sa.Column("delivery_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["parties.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("po_no"),
    )
    op.create_index("ix_customer_pos_po_no", "customer_pos", ["po_no"], unique=True)
    op.create_index("ix_customer_pos_customer_id", "customer_pos", ["customer_id"], unique=False)

    op.create_table(
        "customer_po_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_po_id", sa.String(36), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("product_name", sa.String(160), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("rate", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["customer_po_id"], ["customer_pos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    bind = op.get_bind()
    plants = [
        (str(uuid.uuid4()), "PLT-1", "Chakan Plant", "Chakan Industrial Area, Pune"),
        (str(uuid.uuid4()), "PLT-2", "Bhosari Unit", "Bhosari MIDC, Pune"),
    ]
    for pid, code, name, location in plants:
        bind.execute(
            sa.text(
                "INSERT INTO plants (id, code, name, location, active) VALUES (:id,:code,:name,:location,true)"
            ),
            {"id": pid, "code": code, "name": name, "location": location},
        )
    bind.execute(
        sa.text(
            "INSERT INTO warehouses (id, plant_id, code, name, location, active) "
            "SELECT :wid, id, 'WH-FG', 'Finished Goods Store', 'Chakan, Pune', true "
            "FROM plants WHERE code='PLT-1'"
        ),
        {"wid": str(uuid.uuid4())},
    )


def downgrade() -> None:
    op.drop_table("customer_po_lines")
    op.drop_index("ix_customer_pos_customer_id", table_name="customer_pos")
    op.drop_index("ix_customer_pos_po_no", table_name="customer_pos")
    op.drop_table("customer_pos")
    op.drop_table("grn_lines")
    op.drop_index("ix_grns_grn_no", table_name="grns")
    op.drop_index("ix_grns_grn_date", table_name="grns")
    op.drop_table("grns")
    op.drop_table("purchase_order_lines")
    op.drop_index("ix_purchase_orders_po_no", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_po_date", table_name="purchase_orders")
    op.drop_table("purchase_orders")
    op.drop_index("ix_supplier_products_product_id", table_name="supplier_products")
    op.drop_index("ix_supplier_products_supplier_id", table_name="supplier_products")
    op.drop_table("supplier_products")
    op.drop_index("ix_warehouses_code", table_name="warehouses")
    op.drop_index("ix_warehouses_plant_id", table_name="warehouses")
    op.drop_table("warehouses")
    op.drop_index("ix_plants_code", table_name="plants")
    op.drop_table("plants")
    sa.Enum(name="purchaseorderstatus").drop(op.get_bind(), checkfirst=True)
