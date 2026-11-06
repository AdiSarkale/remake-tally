"""Add job cards, employee time logs, and production-entry linkage.

Revision ID: b8d4f1a6c920
Revises: a7c9e2f4b610
"""
from alembic import op
import sqlalchemy as sa
revision = "b8d4f1a6c920"
down_revision = "a7c9e2f4b610"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("job_cards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("production_order_id", sa.String(36), sa.ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("production_order_operation_id", sa.String(36), sa.ForeignKey("production_order_operations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation_id", sa.String(36), sa.ForeignKey("routing_operations.id"), nullable=False),
        sa.Column("workcenter_id", sa.String(36), sa.ForeignKey("workcenters.id"), nullable=False),
        sa.Column("assigned_employee_id", sa.String(36), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("planned_qty", sa.Float(), nullable=False),
        sa.Column("completed_qty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False, server_default="Pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_job_cards_production_order_id", "job_cards", ["production_order_id"])
    op.create_index("ix_job_cards_production_order_operation_id", "job_cards", ["production_order_operation_id"])
    op.create_index("ix_job_cards_operation_id", "job_cards", ["operation_id"])
    op.create_index("ix_job_cards_workcenter_id", "job_cards", ["workcenter_id"])
    op.create_index("ix_job_cards_assigned_employee_id", "job_cards", ["assigned_employee_id"])
    op.create_index("ix_job_cards_status", "job_cards", ["status"])
    op.create_table("job_card_time_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_card_id", sa.String(36), sa.ForeignKey("job_cards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Float(), nullable=False, server_default="0"),
        sa.Column("completed_qty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("remarks", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_job_card_time_logs_job_card_id", "job_card_time_logs", ["job_card_id"])
    op.create_index("ix_job_card_time_logs_employee_id", "job_card_time_logs", ["employee_id"])
    op.add_column("production_entries", sa.Column("job_card_id", sa.String(36), nullable=True))
    op.create_index("ix_production_entries_job_card_id", "production_entries", ["job_card_id"])
    op.create_foreign_key("fk_production_entries_job_card_id", "production_entries", "job_cards", ["job_card_id"], ["id"])

def downgrade() -> None:
    op.drop_constraint("fk_production_entries_job_card_id", "production_entries", type_="foreignkey")
    op.drop_index("ix_production_entries_job_card_id", table_name="production_entries")
    op.drop_column("production_entries", "job_card_id")
    op.drop_index("ix_job_card_time_logs_employee_id", table_name="job_card_time_logs")
    op.drop_index("ix_job_card_time_logs_job_card_id", table_name="job_card_time_logs")
    op.drop_table("job_card_time_logs")
    for name in ["status", "assigned_employee_id", "workcenter_id", "operation_id", "production_order_operation_id", "production_order_id"]:
        op.drop_index(f"ix_job_cards_{name}", table_name="job_cards")
    op.drop_table("job_cards")
