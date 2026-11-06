"""Add quality inspection records and finished-goods hold balances.
Revision ID: e3f6a9b2d580
Revises: d2e5f8a1c370
"""
from alembic import op
import sqlalchemy as sa
revision="e3f6a9b2d580"
down_revision="d2e5f8a1c370"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("products",sa.Column("quality_hold_stock",sa.Float(),nullable=False,server_default="0"))
    op.add_column("warehouse_stock",sa.Column("quality_hold_quantity",sa.Float(),nullable=False,server_default="0"))
    op.create_table("quality_inspections",sa.Column("id",sa.String(36),primary_key=True),sa.Column("production_entry_id",sa.String(36),sa.ForeignKey("production_entries.id",ondelete="CASCADE"),nullable=False),sa.Column("status",sa.String(32),nullable=False,server_default="Pending"),sa.Column("inspected_quantity",sa.Float(),nullable=False),sa.Column("accepted_quantity",sa.Float(),nullable=False,server_default="0"),sa.Column("rejected_quantity",sa.Float(),nullable=False,server_default="0"),sa.Column("inspector_user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=True),sa.Column("inspected_at",sa.DateTime(timezone=True),nullable=True),sa.Column("remarks",sa.Text(),nullable=False,server_default=""),sa.UniqueConstraint("production_entry_id",name="uq_quality_inspection_production_entry"))
    op.create_index("ix_quality_inspections_production_entry_id","quality_inspections",["production_entry_id"]);op.create_index("ix_quality_inspections_status","quality_inspections",["status"])
    op.create_table("quality_inspection_lines",sa.Column("id",sa.Integer(),primary_key=True,autoincrement=True),sa.Column("inspection_id",sa.String(36),sa.ForeignKey("quality_inspections.id",ondelete="CASCADE"),nullable=False),sa.Column("test_name",sa.String(120),nullable=False),sa.Column("expected_value",sa.String(160),nullable=False,server_default=""),sa.Column("actual_value",sa.String(160),nullable=False,server_default=""),sa.Column("passed",sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column("remarks",sa.Text(),nullable=False,server_default=""))
    op.create_index("ix_quality_inspection_lines_inspection_id","quality_inspection_lines",["inspection_id"])

def downgrade():
    op.drop_index("ix_quality_inspection_lines_inspection_id",table_name="quality_inspection_lines");op.drop_table("quality_inspection_lines")
    op.drop_index("ix_quality_inspections_status",table_name="quality_inspections");op.drop_index("ix_quality_inspections_production_entry_id",table_name="quality_inspections");op.drop_table("quality_inspections")
    op.drop_column("warehouse_stock","quality_hold_quantity");op.drop_column("products","quality_hold_stock")
