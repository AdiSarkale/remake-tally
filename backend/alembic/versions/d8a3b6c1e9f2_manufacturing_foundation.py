"""Add manufacturing workcenters, routings, employees and production orders.

Revision ID: d8a3b6c1e9f2
Revises: c7f1a2d4b8e0
"""

from alembic import op
import sqlalchemy as sa


revision = "d8a3b6c1e9f2"
down_revision = "c7f1a2d4b8e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workcenters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("department", sa.String(120), nullable=False, server_default=""),
        sa.Column("capacity_per_hour", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="Available"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("location", sa.String(160), nullable=False, server_default=""),
        sa.UniqueConstraint("code", name="uq_workcenter_code"),
    )
    op.create_index("ix_workcenters_code", "workcenters", ["code"], unique=True)

    op.create_table(
        "routings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("name", sa.String(120), nullable=False, server_default=""),
        sa.UniqueConstraint("product_id", "version", name="uq_routing_product_version"),
    )
    op.create_index("ix_routings_product_id", "routings", ["product_id"])

    op.create_table(
        "routing_operations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("routing_id", sa.String(36), sa.ForeignKey("routings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(32), nullable=False, server_default=""),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("workcenter_id", sa.String(36), sa.ForeignKey("workcenters.id"), nullable=False),
        sa.Column("required_skill", sa.String(120), nullable=False, server_default=""),
        sa.Column("setup_minutes", sa.Float(), nullable=False, server_default="0"),
        sa.Column("run_minutes_per_unit", sa.Float(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("routing_id", "sequence", name="uq_routing_operation_sequence"),
    )
    op.create_index("ix_routing_operations_routing_id", "routing_operations", ["routing_id"])
    op.create_index("ix_routing_operations_workcenter_id", "routing_operations", ["workcenter_id"])

    op.create_table(
        "workcenter_materials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workcenter_id", sa.String(36), sa.ForeignKey("workcenters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_kind", sa.String(8), nullable=False),
        sa.Column("item_id", sa.String(36), nullable=False),
        sa.Column("operation_id", sa.String(36), sa.ForeignKey("routing_operations.id"), nullable=True),
        sa.UniqueConstraint("workcenter_id", "item_kind", "item_id", name="uq_workcenter_item"),
    )
    op.create_index("ix_workcenter_materials_workcenter_id", "workcenter_materials", ["workcenter_id"])

    op.create_table(
        "employees",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("emp_code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("department", sa.String(120), nullable=False, server_default=""),
        sa.Column("designation", sa.String(120), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("emp_code", name="uq_employee_code"),
    )
    op.create_index("ix_employees_emp_code", "employees", ["emp_code"], unique=True)

    op.create_table(
        "employee_skills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill", sa.String(120), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("certified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("employee_id", "skill", name="uq_employee_skill"),
    )

    op.create_table(
        "production_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_no", sa.String(32), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("routing_id", sa.String(36), sa.ForeignKey("routings.id"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="Planned"),
        sa.Column("remarks", sa.Text(), nullable=False, server_default=""),
        sa.UniqueConstraint("order_no", name="uq_production_order_no"),
    )
    op.create_index("ix_production_orders_order_no", "production_orders", ["order_no"], unique=True)

    op.create_table(
        "production_order_operations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("production_order_id", sa.String(36), sa.ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation_id", sa.String(36), sa.ForeignKey("routing_operations.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("workcenter_id", sa.String(36), sa.ForeignKey("workcenters.id"), nullable=False),
        sa.Column("assigned_employee_id", sa.String(36), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="Pending"),
        sa.Column("planned_qty", sa.Float(), nullable=False),
        sa.Column("completed_qty", sa.Float(), nullable=False, server_default="0"),
        sa.UniqueConstraint("production_order_id", "sequence", name="uq_order_operation_sequence"),
    )

    for table, column, fk in [
        ("production_entries", "workcenter_id", "workcenters.id"),
        ("production_entries", "routing_id", "routings.id"),
        ("production_entries", "operation_id", "routing_operations.id"),
        ("production_entries", "production_order_id", "production_orders.id"),
        ("production_entries", "employee_id", "employees.id"),
    ]:
        op.add_column(table, sa.Column(column, sa.String(36), nullable=True))
        op.create_index(f"ix_{table}_{column}", table, [column])
        op.create_foreign_key(f"fk_{table}_{column}", table, [column], fk)


def downgrade() -> None:
    for column in ["employee_id", "production_order_id", "operation_id", "routing_id", "workcenter_id"]:
        op.drop_constraint(f"fk_production_entries_{column}", "production_entries", type_="foreignkey")
        op.drop_index(f"ix_production_entries_{column}", table_name="production_entries")
        op.drop_column("production_entries", column)
    op.drop_table("production_order_operations")
    op.drop_index("ix_production_orders_order_no", table_name="production_orders")
    op.drop_table("production_orders")
    op.drop_table("employee_skills")
    op.drop_index("ix_employees_emp_code", table_name="employees")
    op.drop_table("employees")
    op.drop_index("ix_workcenter_materials_workcenter_id", table_name="workcenter_materials")
    op.drop_table("workcenter_materials")
    op.drop_index("ix_routing_operations_workcenter_id", table_name="routing_operations")
    op.drop_index("ix_routing_operations_routing_id", table_name="routing_operations")
    op.drop_table("routing_operations")
    op.drop_index("ix_routings_product_id", table_name="routings")
    op.drop_table("routings")
    op.drop_index("ix_workcenters_code", table_name="workcenters")
    op.drop_table("workcenters")
