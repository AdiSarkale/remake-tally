"""Add immutable version history for controlled roster overrides.

Revision ID: p0_hr_roster_history_017
Revises: p0_hr_shift_roster_016
"""
from alembic import op
import sqlalchemy as sa

revision = "p0_hr_roster_history_017"
down_revision = "p0_hr_shift_roster_016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "hr_shift_roster_entries",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "hr_shift_roster_entry_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "roster_entry_id",
            sa.String(36),
            sa.ForeignKey("hr_shift_roster_entries.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("changed_by", sa.String(64), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("roster_entry_id", "version", name="uq_hr_shift_roster_history_version"),
        sa.CheckConstraint("version > 0", name="ck_hr_shift_roster_history_version_positive"),
    )
    op.create_index(
        "ix_hr_shift_roster_entry_history_roster_entry_id",
        "hr_shift_roster_entry_history",
        ["roster_entry_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hr_shift_roster_entry_history_roster_entry_id",
        table_name="hr_shift_roster_entry_history",
    )
    op.drop_table("hr_shift_roster_entry_history")
    op.drop_column("hr_shift_roster_entries", "version")
