"""P0.1-09 effective-dated overtime policy versions.

Revision ID: p0_hr_overtime_policy_022
Revises: p0_hr_att_summary_021
"""
from alembic import op
import sqlalchemy as sa

revision = "p0_hr_overtime_policy_022"
down_revision = "p0_hr_att_summary_021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hr_overtime_policy_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("version_code", sa.String(length=40), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("scope", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("configuration", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("published_by", sa.String(length=64), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("version_code", name="uq_hr_overtime_policy_version_code"),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="ck_hr_overtime_policy_effective_dates"),
        sa.CheckConstraint("status IN ('draft', 'published', 'retired')", name="ck_hr_overtime_policy_status"),
    )
    op.create_index("ix_hr_overtime_policy_versions_effective_from", "hr_overtime_policy_versions", ["effective_from"])
    op.create_index("ix_hr_overtime_policy_versions_effective_to", "hr_overtime_policy_versions", ["effective_to"])


def downgrade() -> None:
    op.drop_index("ix_hr_overtime_policy_versions_effective_to", table_name="hr_overtime_policy_versions")
    op.drop_index("ix_hr_overtime_policy_versions_effective_from", table_name="hr_overtime_policy_versions")
    op.drop_table("hr_overtime_policy_versions")
