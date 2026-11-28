"""Snapshot branch/timezone context on daily HR attendance.

Revision ID: p0_hr_branch_timezone_018
Revises: p0_hr_roster_history_017
"""
from alembic import op
import sqlalchemy as sa

revision = "p0_hr_branch_timezone_018"
down_revision = "p0_hr_roster_history_017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employee_attendance",
        sa.Column(
            "branch_id",
            sa.String(length=36),
            sa.ForeignKey("hr_branches.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column(
        "employee_attendance",
        sa.Column(
            "timezone_name",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_employee_attendance_branch_id",
        "employee_attendance",
        ["branch_id"],
    )
    # Existing rows intentionally remain NULL. Their historical branch/timezone
    # is not inferred from today's effective-dated employee assignment.


def downgrade() -> None:
    op.drop_index("ix_employee_attendance_branch_id", table_name="employee_attendance")
    op.drop_column("employee_attendance", "timezone_name")
    op.drop_column("employee_attendance", "branch_id")
