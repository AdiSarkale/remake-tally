"""Persist controlled payroll supersession attribution.
Revision ID: p0_hr_payroll_supersede_027
Revises: p0_hr_payroll_daily_snapshots_026
"""
from alembic import op
import sqlalchemy as sa

revision = "p0_hr_payroll_supersede_027"
down_revision = "p0_hr_payroll_daily_snapshots_026"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("hr_payroll_runs", sa.Column("superseded_by", sa.String(length=64), nullable=True))
    op.add_column("hr_payroll_runs", sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("hr_payroll_runs", sa.Column("superseded_reason", sa.Text(), nullable=False, server_default=""))
    op.alter_column("hr_payroll_runs", "superseded_reason", server_default=None)


def downgrade():
    op.drop_column("hr_payroll_runs", "superseded_reason")
    op.drop_column("hr_payroll_runs", "superseded_at")
    op.drop_column("hr_payroll_runs", "superseded_by")
