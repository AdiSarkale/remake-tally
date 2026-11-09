"""Add tenant-configured attendance source reconciliation and anomalies.

Revision ID: p0_hr_attendance_reconciliation_020
Revises: p0_hr_attendance_events_019
"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = "p0_hr_attendance_reconciliation_020"
down_revision = "p0_hr_attendance_events_019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hr_attendance_anomalies",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("comparison_key", sa.String(length=64), nullable=False),
        sa.Column("employee_id", sa.String(length=36), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("roster_entry_id", sa.String(length=36), sa.ForeignKey("hr_shift_roster_entries.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("anomaly_type", sa.String(length=32), nullable=False),
        sa.Column("source_event_ids", sa.JSON(), nullable=False),
        sa.Column("observed_delta_minutes", sa.Numeric(10, 2), nullable=False),
        sa.Column("threshold_minutes", sa.Integer(), nullable=False),
        sa.Column("policy_version_id", sa.String(length=36), sa.ForeignKey("hr_workforce_policy_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("resolution_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("resolution_result", sa.JSON(), nullable=True),
        sa.Column("resolved_by", sa.String(length=64), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("comparison_key", name="uq_hr_attendance_anomaly_comparison"),
        sa.CheckConstraint("anomaly_type IN ('source_mismatch')", name="ck_hr_attendance_anomaly_type"),
        sa.CheckConstraint("status IN ('open', 'acknowledged', 'resolved', 'false_positive')", name="ck_hr_attendance_anomaly_status"),
        sa.CheckConstraint("threshold_minutes >= 0", name="ck_hr_attendance_anomaly_threshold"),
    )
    op.create_index("ix_hr_attendance_anomalies_employee_id", "hr_attendance_anomalies", ["employee_id"])
    op.create_index("ix_hr_attendance_anomalies_work_date", "hr_attendance_anomalies", ["work_date"])
    op.create_index("ix_hr_attendance_anomalies_status", "hr_attendance_anomalies", ["status"])
    op.create_index("ix_hr_attendance_anomalies_policy_version_id", "hr_attendance_anomalies", ["policy_version_id"])

    bind = op.get_bind()
    grants = sa.Table("role_permission_grants", sa.MetaData(), autoload_with=bind)
    existing = {
        (row.role, row.module, row.feature, row.action, row.data_scope)
        for row in bind.execute(sa.select(
            grants.c.role, grants.c.module, grants.c.feature,
            grants.c.action, grants.c.data_scope,
        ))
    }
    grant_specs = [
        ("Admin", "attendance_anomalies", "view", "tenant"),
        ("Admin", "attendance_anomalies", "resolve", "tenant"),
        ("Admin", "attendance_anomalies", "false_positive", "tenant"),
        ("HR", "attendance_anomalies", "view", "tenant"),
        ("HR", "attendance_anomalies", "resolve", "tenant"),
        ("HR", "attendance_anomalies", "false_positive", "tenant"),
        ("Admin", "workforce_settings", "view", "tenant"),
        ("Admin", "workforce_settings", "edit", "tenant"),
        ("HR", "workforce_settings", "view", "tenant"),
        ("HR", "workforce_settings", "edit", "tenant"),
    ]
    rows = []
    for role, feature, action, scope in grant_specs:
        key = (role, "hr", feature, action, scope)
        if key in existing:
            continue
        rows.append({
            "id": str(uuid.uuid4()),
            "role": role,
            "module": "hr",
            "feature": feature,
            "action": action,
            "data_scope": scope,
            "allowed": True,
            "updated_by": "migration:p0_hr_attendance_reconciliation_020",
        })
    if rows:
        op.bulk_insert(grants, rows)


def downgrade() -> None:
    bind = op.get_bind()
    grants = sa.Table("role_permission_grants", sa.MetaData(), autoload_with=bind)
    op.execute(sa.delete(grants).where(
        grants.c.updated_by == "migration:p0_hr_attendance_reconciliation_020",
    ))
    op.drop_index("ix_hr_attendance_anomalies_policy_version_id", table_name="hr_attendance_anomalies")
    op.drop_index("ix_hr_attendance_anomalies_status", table_name="hr_attendance_anomalies")
    op.drop_index("ix_hr_attendance_anomalies_work_date", table_name="hr_attendance_anomalies")
    op.drop_index("ix_hr_attendance_anomalies_employee_id", table_name="hr_attendance_anomalies")
    op.drop_table("hr_attendance_anomalies")
