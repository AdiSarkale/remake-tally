"""Support subassembly components in BOM lines.
Revision ID: f4a7c0d3e690
Revises: e3f6a9b2d580
"""
from alembic import op
import sqlalchemy as sa
revision="f4a7c0d3e690"
down_revision="e3f6a9b2d580"
branch_labels=None
depends_on=None

def upgrade():
    op.alter_column("bom_lines","material_id",existing_type=sa.String(36),nullable=True)
    op.add_column("bom_lines",sa.Column("subassembly_product_id",sa.String(36),nullable=True))
    op.add_column("bom_lines",sa.Column("line_type",sa.String(8),nullable=False,server_default="RM"))
    op.create_foreign_key("fk_bom_lines_subassembly_product_id","bom_lines","products",["subassembly_product_id"],["id"])
    op.create_index("ix_bom_lines_subassembly_product_id","bom_lines",["subassembly_product_id"])

def downgrade():
    op.drop_index("ix_bom_lines_subassembly_product_id",table_name="bom_lines")
    op.drop_constraint("fk_bom_lines_subassembly_product_id","bom_lines",type_="foreignkey")
    op.drop_column("bom_lines","line_type");op.drop_column("bom_lines","subassembly_product_id")
    op.alter_column("bom_lines","material_id",existing_type=sa.String(36),nullable=False)
