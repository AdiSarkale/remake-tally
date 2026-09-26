"""add customer and supplier payment records

Revision ID: 4f7b2d9c8a11
Revises: ed5ebdbcf47d
"""

from alembic import op
import sqlalchemy as sa


revision = "4f7b2d9c8a11"
down_revision = "ed5ebdbcf47d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_payments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("payment_no", sa.String(length=32), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("customer_name", sa.String(length=160), nullable=False),
        sa.Column("invoice_id", sa.String(length=36), nullable=True),
        sa.Column("invoice_no", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("reference", sa.String(length=64), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_no"),
    )
    op.create_index("ix_customer_payments_payment_no", "customer_payments", ["payment_no"], unique=True)
    op.create_index("ix_customer_payments_payment_date", "customer_payments", ["payment_date"], unique=False)
    op.create_index("ix_customer_payments_customer_id", "customer_payments", ["customer_id"], unique=False)
    op.create_index("ix_customer_payments_invoice_id", "customer_payments", ["invoice_id"], unique=False)

    op.create_table(
        "supplier_payments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("payment_no", sa.String(length=32), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("supplier_id", sa.String(length=36), nullable=False),
        sa.Column("supplier_name", sa.String(length=160), nullable=False),
        sa.Column("purchase_order_id", sa.String(length=36), nullable=True),
        sa.Column("po_no", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("reference", sa.String(length=64), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_no"),
    )
    op.create_index("ix_supplier_payments_payment_no", "supplier_payments", ["payment_no"], unique=True)
    op.create_index("ix_supplier_payments_payment_date", "supplier_payments", ["payment_date"], unique=False)
    op.create_index("ix_supplier_payments_supplier_id", "supplier_payments", ["supplier_id"], unique=False)
    op.create_index("ix_supplier_payments_purchase_order_id", "supplier_payments", ["purchase_order_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_supplier_payments_purchase_order_id", table_name="supplier_payments")
    op.drop_index("ix_supplier_payments_supplier_id", table_name="supplier_payments")
    op.drop_index("ix_supplier_payments_payment_date", table_name="supplier_payments")
    op.drop_index("ix_supplier_payments_payment_no", table_name="supplier_payments")
    op.drop_table("supplier_payments")

    op.drop_index("ix_customer_payments_invoice_id", table_name="customer_payments")
    op.drop_index("ix_customer_payments_customer_id", table_name="customer_payments")
    op.drop_index("ix_customer_payments_payment_date", table_name="customer_payments")
    op.drop_index("ix_customer_payments_payment_no", table_name="customer_payments")
    op.drop_table("customer_payments")
