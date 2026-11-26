"""P0.1-08 daily attendance summary revisions and correction requests.

Revision ID: p0_hr_attendance_summary_021
Revises: p0_hr_attendance_reconciliation_020
"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = "p0_hr_att_summary_021"
down_revision = "p0_hr_att_reconcile_020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hr_attendance_summary_revisions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("employee_id", sa.String(length=36), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("roster_entry_id", sa.String(length=36), sa.ForeignKey("hr_shift_roster_entries.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("timezone_name", sa.String(length=64), nullable=False),
        sa.Column("source_event_ids", sa.JSON(), nullable=False),
        sa.Column("first_punch_in_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_punch_out_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("elapsed_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("paired_break_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("classification", sa.String(length=24), nullable=False),
        sa.Column("exception_codes", sa.JSON(), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("calculated_by", sa.String(length=64), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("employee_id", "work_date", "revision", name="uq_hr_attendance_summary_revision"),
        sa.CheckConstraint("revision > 0", name="ck_hr_attendance_summary_revision_positive"),
    )
    op.create_index("ix_hr_attendance_summary_revisions_employee_id", "hr_attendance_summary_revisions", ["employee_id"])
    op.create_index("ix_hr_attendance_summary_revisions_work_date", "hr_attendance_summary_revisions", ["work_date"])

    op.create_table(
        "hr_attendance_daily_summaries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("employee_id", sa.String(length=36), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("current_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("roster_entry_id", sa.String(length=36), sa.ForeignKey("hr_shift_roster_entries.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("timezone_name", sa.String(length=64), nullable=False),
        sa.Column("source_event_ids", sa.JSON(), nullable=False),
        sa.Column("first_punch_in_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_punch_out_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("elapsed_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("paired_break_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("classification", sa.String(length=24), nullable=False),
        sa.Column("exception_codes", sa.JSON(), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("calculated_by", sa.String(length=64), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("employee_id", "work_date", name="uq_hr_attendance_summary_employee_day"),
    )
    op.create_index("ix_hr_attendance_daily_summaries_employee_id", "hr_attendance_daily_summaries", ["employee_id"])
    op.create_index("ix_hr_attendance_daily_summaries_work_date", "hr_attendance_daily_summaries", ["work_date"])

    op.create_table(
        "hr_attendance_correction_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("employee_id", sa.String(length=36), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("correction_kind", sa.String(length=12), nullable=False),
        sa.Column("target_event_id", sa.String(length=36), sa.ForeignKey("hr_attendance_events.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("proposed_event_type", sa.String(length=20), nullable=False),
        sa.Column("proposed_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone_name", sa.String(length=64), nullable=False),
        sa.Column("break_rule_id", sa.String(length=36), sa.ForeignKey("hr_shift_break_rules.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_reference", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="submitted"),
        sa.Column("requested_by", sa.String(length=64), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewer", sa.String(length=64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("applied_event_id", sa.String(length=36), sa.ForeignKey("hr_attendance_events.id", ondelete="RESTRICT"), nullable=True),
        sa.CheckConstraint("correction_kind IN ('add', 'replace')", name="ck_hr_attendance_correction_kind"),
        sa.CheckConstraint("status IN ('submitted', 'approved', 'rejected', 'returned', 'applied')", name="ck_hr_attendance_correction_status"),
        sa.CheckConstraint("(correction_kind = 'add' AND target_event_id IS NULL) OR (correction_kind = 'replace' AND target_event_id IS NOT NULL)", name="ck_hr_attendance_correction_target"),
        sa.CheckConstraint("proposed_event_type IN ('punch_in', 'punch_out', 'break_start', 'break_end')", name="ck_hr_attendance_correction_event_type"),
    )
    op.create_index("ix_hr_attendance_correction_requests_employee_id", "hr_attendance_correction_requests", ["employee_id"])
    op.create_index("ix_hr_attendance_correction_requests_work_date", "hr_attendance_correction_requests", ["work_date"])
    op.create_index("ix_hr_attendance_correction_requests_status", "hr_attendance_correction_requests", ["status"])

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
        ("Admin", "attendance_summaries", "view", "tenant"),
        ("Admin", "attendance_summaries", "calculate", "tenant"),
        ("HR", "attendance_summaries", "view", "tenant"),
        ("HR", "attendance_summaries", "calculate", "tenant"),
        ("Admin", "attendance_corrections", "view", "tenant"),
        ("Admin", "attendance_corrections", "create", "tenant"),
        ("Admin", "attendance_corrections", "review", "tenant"),
        ("HR", "attendance_corrections", "view", "tenant"),
        ("HR", "attendance_corrections", "create", "tenant"),
        ("HR", "attendance_corrections", "review", "tenant"),
        ("Operator", "attendance_summaries", "view", "self"),
        ("Operator", "attendance_corrections", "view", "self"),
        ("Operator", "attendance_corrections", "create", "self"),
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
            "updated_by": "migration:p0_hr_att_summary_021",
        })
    if rows:
        op.bulk_insert(grants, rows)


def downgrade() -> None:
    bind = op.get_bind()
    grants = sa.Table("role_permission_grants", sa.MetaData(), autoload_with=bind)
    op.execute(sa.delete(grants).where(
        grants.c.updated_by == "migration:p0_hr_att_summary_021",
    ))
    op.drop_index("ix_hr_attendance_correction_requests_status", table_name="hr_attendance_correction_requests")
    op.drop_index("ix_hr_attendance_correction_requests_work_date", table_name="hr_attendance_correction_requests")
    op.drop_index("ix_hr_attendance_correction_requests_employee_id", table_name="hr_attendance_correction_requests")
    op.drop_table("hr_attendance_correction_requests")
    op.drop_index("ix_hr_attendance_daily_summaries_work_date", table_name="hr_attendance_daily_summaries")
    op.drop_index("ix_hr_attendance_daily_summaries_employee_id", table_name="hr_attendance_daily_summaries")
    op.drop_table("hr_attendance_daily_summaries")
    op.drop_index("ix_hr_attendance_summary_revisions_work_date", table_name="hr_attendance_summary_revisions")
    op.drop_index("ix_hr_attendance_summary_revisions_employee_id", table_name="hr_attendance_summary_revisions")
    op.drop_table("hr_attendance_summary_revisions")
