"""Harden BOM versioning and active BOM rules.

Revision ID: c7f1a2d4b8e0
Revises: fae5cbfb8d46
Create Date: 2026-09-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7f1a2d4b8e0"
down_revision: Union[str, Sequence[str], None] = "fae5cbfb8d46"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(
        "ix_bill_of_materials_product_id",
        table_name="bill_of_materials",
    )

    op.create_index(
        "ix_bill_of_materials_product_id",
        "bill_of_materials",
        ["product_id"],
        unique=False,
    )

    bind = op.get_bind()

    # Existing databases created before versioning had at most one BOM per product,
    # so normalize any legacy duplicate active rows before the partial unique index.
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("bill_of_materials") as batch:
            batch.create_unique_constraint("uq_bom_product_version", ["product_id", "version"])
    else:
        op.create_unique_constraint("uq_bom_product_version", "bill_of_materials", ["product_id", "version"])

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.create_index(
            "uq_bom_product_active",
            "bill_of_materials",
            ["product_id"],
            unique=True,
            sqlite_where=sa.text("active = 1"),
        )
    elif bind.dialect.name == "postgresql":
        op.create_index(
            "uq_bom_product_active",
            "bill_of_materials",
            ["product_id"],
            unique=True,
            postgresql_where=sa.text("active = true"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name in {"sqlite", "postgresql"}:
        op.drop_index(
            "uq_bom_product_active",
            table_name="bill_of_materials",
        )

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("bill_of_materials") as batch:
            batch.drop_constraint("uq_bom_product_version", type_="unique")
    else:
        op.drop_constraint("uq_bom_product_version", "bill_of_materials", type_="unique")

    op.drop_index(
        "ix_bill_of_materials_product_id",
        table_name="bill_of_materials",
    )

    op.create_index(
        "ix_bill_of_materials_product_id",
        "bill_of_materials",
        ["product_id"],
        unique=True,
    )
