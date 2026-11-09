"""Persist raw HR attendance events and import batch provenance.

Revision ID: p0_hr_attendance_events_019
Revises: p0_hr_branch_timezone_018
"""
from alembic import op
import sqlalchemy as sa

revision = "p0_hr_attendance_events_019"
down_revision = "p0_hr_branch_timezone_018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hr_attendance_import_batches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("branch_id", sa.String(length=36), sa.ForeignKey("hr_branches.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("import_timezone", sa.String(length=64), nullable=False),
        sa.Column("template_version", sa.String(length=32), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by", sa.String(length=64), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("rows_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint("status IN ('validated', 'imported', 'rejected')", name="ck_hr_attendance_import_batch_status"),
        sa.CheckConstraint("rows_total >= 0 AND rows_imported >= 0 AND rows_rejected >= 0", name="ck_hr_attendance_import_batch_counts"),
    )
    op.create_index("ix_hr_attendance_import_batches_branch_id", "hr_attendance_import_batches", ["branch_id"])
    op.create_index("ix_hr_attendance_import_batches_file_hash", "hr_attendance_import_batches", ["file_hash"])
    op.create_index("ix_hr_attendance_import_batches_uploaded_at", "hr_attendance_import_batches", ["uploaded_at"])

    op.create_table(
        "hr_attendance_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("employee_id", sa.String(length=36), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("roster_entry_id", sa.String(length=36), sa.ForeignKey("hr_shift_roster_entries.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("occurred_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone_name", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_reference", sa.String(length=160), nullable=False),
        sa.Column("import_batch_id", sa.String(length=36), sa.ForeignKey("hr_attendance_import_batches.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("break_rule_id", sa.String(length=36), sa.ForeignKey("hr_shift_break_rules.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("recorded_by", sa.String(length=64), nullable=False),
        sa.Column("supersedes_event_id", sa.String(length=36), sa.ForeignKey("hr_attendance_events.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by", sa.String(length=64), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_type", "source_reference", name="uq_hr_attendance_event_source_reference"),
        sa.CheckConstraint("event_type IN ('punch_in', 'punch_out', 'break_start', 'break_end')", name="ck_hr_attendance_event_type"),
        sa.CheckConstraint("source_type IN ('manual_hr', 'excel_import', 'employee')", name="ck_hr_attendance_event_source_type"),
    )
    op.create_index("ix_hr_attendance_events_employee_id", "hr_attendance_events", ["employee_id"])
    op.create_index("ix_hr_attendance_events_roster_entry_id", "hr_attendance_events", ["roster_entry_id"])
    op.create_index("ix_hr_attendance_events_work_date", "hr_attendance_events", ["work_date"])
    op.create_index("ix_hr_attendance_events_occurred_at_utc", "hr_attendance_events", ["occurred_at_utc"])
    op.create_index("ix_hr_attendance_events_import_batch_id", "hr_attendance_events", ["import_batch_id"])


def downgrade() -> None:
    op.drop_index("ix_hr_attendance_events_import_batch_id", table_name="hr_attendance_events")
    op.drop_index("ix_hr_attendance_events_occurred_at_utc", table_name="hr_attendance_events")
    op.drop_index("ix_hr_attendance_events_work_date", table_name="hr_attendance_events")
    op.drop_index("ix_hr_attendance_events_roster_entry_id", table_name="hr_attendance_events")
    op.drop_index("ix_hr_attendance_events_employee_id", table_name="hr_attendance_events")
    op.drop_table("hr_attendance_events")
    op.drop_index("ix_hr_attendance_import_batches_uploaded_at", table_name="hr_attendance_import_batches")
    op.drop_index("ix_hr_attendance_import_batches_file_hash", table_name="hr_attendance_import_batches")
    op.drop_index("ix_hr_attendance_import_batches_branch_id", table_name="hr_attendance_import_batches")
    op.drop_table("hr_attendance_import_batches")
