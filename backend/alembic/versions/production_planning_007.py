"""Production planning, reservation and advanced manufacturing tables.

Revision ID: production_planning_007
Revises: hr_timezone_006
"""
from alembic import op
import sqlalchemy as sa

revision = "production_planning_007"
down_revision = "hr_timezone_006"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "production_material_reservations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("production_order_id", sa.String(36), sa.ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_id", sa.String(36), sa.ForeignKey("raw_materials.id"), nullable=False),
        sa.Column("required_quantity", sa.Float(), nullable=False),
        sa.Column("reserved_quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_production_material_reservations_order", "production_material_reservations", ["production_order_id"])
    op.create_index("ix_production_material_reservations_material", "production_material_reservations", ["material_id"])
    op.create_index("ix_production_material_reservations_status", "production_material_reservations", ["status"])

    op.create_table(
        "production_operation_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("operation_row_id", sa.String(36), sa.ForeignKey("production_order_operations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workcenter_id", sa.String(36), sa.ForeignKey("workcenters.id"), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("planned_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("planned_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Float(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="scheduled"),
        sa.Column("reschedule_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("operation_row_id", name="uq_production_schedule_operation"),
    )
    op.create_index("ix_production_operation_schedules_workcenter", "production_operation_schedules", ["workcenter_id"])
    op.create_index("ix_production_operation_schedules_employee", "production_operation_schedules", ["employee_id"])
    op.create_index("ix_production_operation_schedules_start", "production_operation_schedules", ["planned_start"])
    op.create_index("ix_production_operation_schedules_end", "production_operation_schedules", ["planned_end"])
    op.create_index("ix_production_operation_schedules_status", "production_operation_schedules", ["status"])

    op.create_table(
        "machine_resources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("workcenter_id", sa.String(36), sa.ForeignKey("workcenters.id"), nullable=False),
        sa.Column("capacity_per_hour", sa.Float(), nullable=False, server_default="0"),
        sa.Column("hourly_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False, server_default="available"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("maintenance_due", sa.Date(), nullable=True),
    )
    op.create_index("ix_machine_resources_code", "machine_resources", ["code"])
    op.create_index("ix_machine_resources_workcenter", "machine_resources", ["workcenter_id"])
    op.create_index("ix_machine_resources_status", "machine_resources", ["status"])
    op.create_index("ix_machine_resources_active", "machine_resources", ["active"])

    op.create_table(
        "machine_downtime",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("machine_id", sa.String(36), sa.ForeignKey("machine_resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason_code", sa.String(40), nullable=False, server_default=""),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("maintenance", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(64), nullable=False, server_default=""),
    )
    op.create_index("ix_machine_downtime_machine", "machine_downtime", ["machine_id"])
    op.create_index("ix_machine_downtime_start", "machine_downtime", ["start_at"])
    op.create_index("ix_machine_downtime_end", "machine_downtime", ["end_at"])

    op.create_table(
        "production_costs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("production_entry_id", sa.String(36), sa.ForeignKey("production_entries.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("material_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("labor_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("machine_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("overhead_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("accepted_quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_production_costs_entry", "production_costs", ["production_entry_id"])

    op.create_table(
        "production_wip_stock",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("production_order_id", sa.String(36), sa.ForeignKey("production_orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False, server_default="available"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("product_id", "production_order_id", name="uq_wip_product_order"),
    )
    op.create_index("ix_production_wip_stock_product", "production_wip_stock", ["product_id"])
    op.create_index("ix_production_wip_stock_order", "production_wip_stock", ["production_order_id"])
    op.create_index("ix_production_wip_stock_status", "production_wip_stock", ["status"])

def downgrade() -> None:
    op.drop_table("production_wip_stock")
    op.drop_table("production_costs")
    op.drop_table("machine_downtime")
    op.drop_table("machine_resources")
    op.drop_table("production_operation_schedules")
    op.drop_table("production_material_reservations")
