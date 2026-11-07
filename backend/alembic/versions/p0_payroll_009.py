"""Add revisioned, approved and reversible payroll lifecycle.

Revision ID: p0_payroll_009
Revises: p0_hr_leave_008
"""
from alembic import op
import sqlalchemy as sa

revision = "p0_payroll_009"
down_revision = "p0_hr_leave_008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("hr_payroll_runs") as batch:
        batch.drop_constraint("uq_hr_payroll_period", type_="unique")
        batch.add_column(sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("approved_by", sa.String(64), nullable=True))
        batch.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("reversal_reason", sa.Text(), nullable=False, server_default=""))
        batch.alter_column("finalized_at", existing_type=sa.DateTime(timezone=True), nullable=True)
        batch.create_unique_constraint(
            "uq_hr_payroll_period_revision", ["year", "month", "revision"]
        )


def downgrade() -> None:
    # Downgrade is intentionally guarded: multiple revisions for one period
    # cannot be represented by the legacy unique (year, month) constraint.
    connection = op.get_bind()
    duplicate = connection.execute(sa.text(
        "SELECT year, month FROM hr_payroll_runs GROUP BY year, month HAVING COUNT(*) > 1 LIMIT 1"
    )).first()
    if duplicate:
        raise RuntimeError("Cannot downgrade payroll revisions while multiple runs exist for one period")
    incomplete = connection.execute(sa.text(
        "SELECT id FROM hr_payroll_runs WHERE finalized_at IS NULL OR status != 'finalized' LIMIT 1"
    )).first()
    if incomplete:
        raise RuntimeError("Cannot downgrade payroll lifecycle while prepared, approved, locked, reversed or unfinalized runs exist")
    with op.batch_alter_table("hr_payroll_runs") as batch:
        batch.drop_constraint("uq_hr_payroll_period_revision", type_="unique")
        batch.drop_column("reversal_reason")
        batch.drop_column("reversed_at")
        batch.drop_column("locked_at")
        batch.drop_column("approved_at")
        batch.drop_column("approved_by")
        batch.drop_column("revision")
        batch.alter_column("finalized_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch.create_unique_constraint("uq_hr_payroll_period", ["year", "month"])
