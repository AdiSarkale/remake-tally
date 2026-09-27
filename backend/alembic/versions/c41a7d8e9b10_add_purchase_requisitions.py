"""add purchase requisitions

Revision ID: c41a7d8e9b10
Revises: b10b63f2a9fb
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c41a7d8e9b10"
down_revision: Union[str, Sequence[str], None] = "b10b63f2a9fb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pr_status = sa.Enum(
        "draft",
        "submitted",
        "approved",
        "rejected",
        "converted",
        name="purchaserequisitionstatus",
    )
    pr_source = sa.Enum(
        "manual",
        "mrp",
        name="purchaserequisitionsource",
    )
    bind = op.get_bind()
    pr_status.create(bind, checkfirst=True)
    pr_source.create(bind, checkfirst=True)

    op.create_table(
        "purchase_requisitions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("pr_no", sa.String(length=32), nullable=False),
        sa.Column("pr_date", sa.Date(), nullable=False),
        sa.Column("required_date", sa.Date(), nullable=True),
        sa.Column("requested_by", sa.String(length=120), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("warehouse_id", sa.String(length=36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("source", pr_source, nullable=False),
        sa.Column("source_reference", sa.String(length=120), nullable=False),
        sa.Column("status", pr_status, nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pr_no"),
    )
    op.create_index(
        "ix_purchase_requisitions_pr_no",
        "purchase_requisitions",
        ["pr_no"],
        unique=True,
    )
    op.create_index(
        "ix_purchase_requisitions_pr_date",
        "purchase_requisitions",
        ["pr_date"],
        unique=False,
    )
    op.create_index(
        "ix_purchase_requisitions_required_date",
        "purchase_requisitions",
        ["required_date"],
        unique=False,
    )

    op.create_table(
        "purchase_requisition_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("purchase_requisition_id", sa.String(length=36), nullable=False),
        sa.Column("material_id", sa.String(length=36), nullable=False),
        sa.Column("material_name", sa.String(length=160), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("required_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["material_id"],
            ["raw_materials.id"],
        ),
        sa.ForeignKeyConstraint(
            ["purchase_requisition_id"],
            ["purchase_requisitions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("purchase_requisition_lines")
    op.drop_index("ix_purchase_requisitions_required_date", table_name="purchase_requisitions")
    op.drop_index("ix_purchase_requisitions_pr_date", table_name="purchase_requisitions")
    op.drop_index("ix_purchase_requisitions_pr_no", table_name="purchase_requisitions")
    op.drop_table("purchase_requisitions")
    bind = op.get_bind()
    sa.Enum(name="purchaserequisitionsource").drop(bind, checkfirst=True)
    sa.Enum(name="purchaserequisitionstatus").drop(bind, checkfirst=True)
