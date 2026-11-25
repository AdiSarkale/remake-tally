"""Production planning and advanced manufacturing.

Revision ID: prod_roadmap_007
Revises: hr_timezone_006
"""
from alembic import op
import sqlalchemy as sa

revision = "prod_roadmap_007"
down_revision = "hr_timezone_006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("production_orders", sa.Column("planning_status", sa.String(length=24), nullable=False, server_default="unplanned"))
    op.add_column("production_order_operations", sa.Column("planned_minutes", sa.Float(), nullable=False, server_default="0"))
    op.add_column("production_order_operations", sa.Column("scheduled_start", sa.DateTime(), nullable=True))
    op.add_column("production_order_operations", sa.Column("scheduled_end", sa.DateTime(), nullable=True))
    op.create_table(
        "production_material_reservations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("production_order_id", sa.String(length=36), sa.ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_id", sa.String(length=36), sa.ForeignKey("raw_materials.id"), nullable=False),
        sa.Column("required_quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reserved_quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="shortage"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("production_order_id", "material_id", name="uq_order_material_reservation"),
    )
    op.create_index("ix_production_material_reservations_production_order_id", "production_material_reservations", ["production_order_id"])
    op.create_index("ix_production_material_reservations_material_id", "production_material_reservations", ["material_id"])
    op.create_table(
        "production_machines",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("workcenter_id", sa.String(length=36), sa.ForeignKey("workcenters.id"), nullable=False),
        sa.Column("capacity_per_hour", sa.Float(), nullable=False, server_default="1"),
        sa.Column("hourly_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="available"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_production_machines_code", "production_machines", ["code"])
    op.create_index("ix_production_machines_workcenter_id", "production_machines", ["workcenter_id"])
    op.create_table(
        "production_machine_downtime",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("machine_id", sa.String(length=36), sa.ForeignKey("production_machines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workcenter_id", sa.String(length=36), sa.ForeignKey("workcenters.id"), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=True),
        sa.Column("reason", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_production_machine_downtime_machine_id", "production_machine_downtime", ["machine_id"])
    op.create_index("ix_production_machine_downtime_workcenter_id", "production_machine_downtime", ["workcenter_id"])
    op.create_index("ix_production_machine_downtime_start_at", "production_machine_downtime", ["start_at"])
    op.create_index("ix_production_machine_downtime_end_at", "production_machine_downtime", ["end_at"])
    op.create_table(
        "production_wip",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("production_order_id", sa.String(length=36), sa.ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation_id", sa.String(length=36), sa.ForeignKey("routing_operations.id"), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("stage", sa.String(length=24), nullable=False, server_default="semi_finished"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_production_wip_production_order_id", "production_wip", ["production_order_id"])
    op.create_index("ix_production_wip_operation_id", "production_wip", ["operation_id"])
    op.create_table(
        "production_costs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("production_order_id", sa.String(length=36), sa.ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("labour_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("machine_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("overhead_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("quantity_produced", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_production_costs_production_order_id", "production_costs", ["production_order_id"])


def downgrade() -> None:
    op.drop_index("ix_production_costs_production_order_id", table_name="production_costs")
    op.drop_table("production_costs")
    op.drop_index("ix_production_wip_operation_id", table_name="production_wip")
    op.drop_index("ix_production_wip_production_order_id", table_name="production_wip")
    op.drop_table("production_wip")
    op.drop_index("ix_production_machine_downtime_end_at", table_name="production_machine_downtime")
    op.drop_index("ix_production_machine_downtime_start_at", table_name="production_machine_downtime")
    op.drop_index("ix_production_machine_downtime_workcenter_id", table_name="production_machine_downtime")
    op.drop_index("ix_production_machine_downtime_machine_id", table_name="production_machine_downtime")
    op.drop_table("production_machine_downtime")
    op.drop_index("ix_production_machines_workcenter_id", table_name="production_machines")
    op.drop_index("ix_production_machines_code", table_name="production_machines")
    op.drop_table("production_machines")
    op.drop_index("ix_production_material_reservations_material_id", table_name="production_material_reservations")
    op.drop_index("ix_production_material_reservations_production_order_id", table_name="production_material_reservations")
    op.drop_table("production_material_reservations")
    op.drop_column("production_order_operations", "scheduled_end")
    op.drop_column("production_order_operations", "scheduled_start")
    op.drop_column("production_order_operations", "planned_minutes")
    op.drop_column("production_orders", "planning_status")
