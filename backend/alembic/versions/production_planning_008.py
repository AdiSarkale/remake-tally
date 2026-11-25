"""Production WIP ledger, shift calendars and workcentre costing rates.

Revision ID: production_planning_008
Revises: production_planning_007
"""
from alembic import op
import sqlalchemy as sa

revision = "production_planning_008"
down_revision = "production_planning_007"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("workcenters", sa.Column("labor_hourly_rate", sa.Float(), nullable=False, server_default="0"))
    op.add_column("workcenters", sa.Column("overhead_hourly_rate", sa.Float(), nullable=False, server_default="0"))
    op.create_table(
        "production_wip_movements",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("wip_stock_id",sa.String(36),sa.ForeignKey("production_wip_stock.id",ondelete="CASCADE"),nullable=False),
        sa.Column("production_order_id",sa.String(36),sa.ForeignKey("production_orders.id",ondelete="SET NULL"),nullable=True),
        sa.Column("movement_type",sa.String(24),nullable=False),
        sa.Column("quantity",sa.Float(),nullable=False),
        sa.Column("balance_after",sa.Float(),nullable=False),
        sa.Column("unit_cost",sa.Float(),nullable=False,server_default="0"),
        sa.Column("reference",sa.String(120),nullable=False,server_default=""),
        sa.Column("reason",sa.Text(),nullable=False,server_default=""),
        sa.Column("created_by",sa.String(64),nullable=False,server_default=""),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
    )
    op.create_index("ix_production_wip_movements_stock","production_wip_movements",["wip_stock_id"])
    op.create_index("ix_production_wip_movements_order","production_wip_movements",["production_order_id"])
    op.create_index("ix_production_wip_movements_type","production_wip_movements",["movement_type"])
    op.create_index("ix_production_wip_movements_created","production_wip_movements",["created_at"])
    op.create_table(
        "workcenter_shifts",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("workcenter_id",sa.String(36),sa.ForeignKey("workcenters.id",ondelete="CASCADE"),nullable=False),
        sa.Column("weekday",sa.Integer(),nullable=False),
        sa.Column("shift_code",sa.String(16),nullable=False,server_default="A"),
        sa.Column("start_time",sa.String(5),nullable=False),
        sa.Column("end_time",sa.String(5),nullable=False),
        sa.Column("active",sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.UniqueConstraint("workcenter_id","weekday","shift_code",name="uq_workcenter_shift_day_code"),
    )
    op.create_index("ix_workcenter_shifts_workcenter","workcenter_shifts",["workcenter_id"])
    op.create_index("ix_workcenter_shifts_weekday","workcenter_shifts",["weekday"])

def downgrade() -> None:
    op.drop_table("workcenter_shifts")
    op.drop_table("production_wip_movements")
    op.drop_column("workcenters","overhead_hourly_rate")
    op.drop_column("workcenters","labor_hourly_rate")
