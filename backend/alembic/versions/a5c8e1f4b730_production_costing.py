"""Add production material, labour, overhead and scrap costing.
Revision ID: a5c8e1f4b730
Revises: f4a7c0d3e690
"""
from alembic import op
import sqlalchemy as sa
revision="a5c8e1f4b730"
down_revision="f4a7c0d3e690"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("employees",sa.Column("hourly_rate",sa.Float(),nullable=False,server_default="0"))
    op.add_column("workcenters",sa.Column("overhead_rate_per_hour",sa.Float(),nullable=False,server_default="0"))
    for name in ["planned_material_cost","actual_material_cost","material_variance_cost","scrap_recovery_value","total_cost","unit_cost"]:
        op.add_column("production_entries",sa.Column(name,sa.Float(),nullable=False,server_default="0"))
    for name in ["unit_cost","planned_cost","actual_cost","variance_cost"]:
        op.add_column("production_consumption",sa.Column(name,sa.Float(),nullable=False,server_default="0"))
    op.add_column("scrap_entries",sa.Column("production_entry_id",sa.String(36),nullable=True))
    op.add_column("scrap_entries",sa.Column("unit_recovery_rate",sa.Float(),nullable=False,server_default="0"))
    op.add_column("scrap_entries",sa.Column("recovery_value",sa.Float(),nullable=False,server_default="0"))
    op.create_foreign_key("fk_scrap_entries_production_entry_id","scrap_entries","production_entries",["production_entry_id"],["id"])
    op.create_index("ix_scrap_entries_production_entry_id","scrap_entries",["production_entry_id"])

def downgrade():
    op.drop_index("ix_scrap_entries_production_entry_id",table_name="scrap_entries")
    op.drop_constraint("fk_scrap_entries_production_entry_id","scrap_entries",type_="foreignkey")
    for name in ["recovery_value","unit_recovery_rate","production_entry_id"]: op.drop_column("scrap_entries",name)
    for name in ["variance_cost","actual_cost","planned_cost","unit_cost"]: op.drop_column("production_consumption",name)
    for name in ["unit_cost","total_cost","scrap_recovery_value","material_variance_cost","actual_material_cost","planned_material_cost"]: op.drop_column("production_entries",name)
    op.drop_column("workcenters","overhead_rate_per_hour");op.drop_column("employees","hourly_rate")
