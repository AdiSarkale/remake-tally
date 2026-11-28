"""Add P0.1 shift definitions, break rules, assignments and roster snapshots.

Revision ID: p0_hr_shift_roster_016
Revises: p0_authz_exact_015
"""
from alembic import op
import sqlalchemy as sa

revision = "p0_hr_shift_roster_016"
down_revision = "p0_authz_exact_015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hr_workforce_policy_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version_code", sa.String(40), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("version_code", name="uq_hr_workforce_policy_version_code"),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_hr_workforce_policy_effective_dates",
        ),
    )
    op.create_index("ix_hr_workforce_policy_versions_effective_from", "hr_workforce_policy_versions", ["effective_from"])
    op.create_index("ix_hr_workforce_policy_versions_effective_to", "hr_workforce_policy_versions", ["effective_to"])

    op.create_table(
        "hr_shift_types",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("end_day_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_hr_shift_type_code"),
        sa.CheckConstraint("end_day_offset IN (0, 1)", name="ck_hr_shift_end_day_offset"),
        sa.CheckConstraint("end_day_offset = 1 OR end_time > start_time", name="ck_hr_shift_same_day_end_after_start"),
    )

    op.create_table(
        "hr_shift_break_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("shift_type_id", sa.String(36), sa.ForeignKey("hr_shift_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("planned_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("scheduled_start_time", sa.Time(), nullable=True),
        sa.Column("scheduled_end_time", sa.Time(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("shift_type_id", "code", name="uq_hr_shift_break_rule_code"),
        sa.CheckConstraint("planned_duration_minutes > 0", name="ck_hr_shift_break_duration_positive"),
        sa.CheckConstraint("sequence >= 0", name="ck_hr_shift_break_sequence_nonnegative"),
    )
    op.create_index("ix_hr_shift_break_rules_shift_type_id", "hr_shift_break_rules", ["shift_type_id"])

    op.create_table(
        "hr_shift_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scope_type", sa.String(16), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=True),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("hr_branches.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("department", sa.String(120), nullable=True),
        sa.Column("shift_type_id", sa.String(36), sa.ForeignKey("hr_shift_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("weekdays", sa.JSON(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("supersedes_assignment_id", sa.String(36), sa.ForeignKey("hr_shift_assignments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "(scope_type = 'employee' AND employee_id IS NOT NULL AND department IS NULL) OR "
            "(scope_type = 'department' AND employee_id IS NULL AND department IS NOT NULL AND length(trim(department)) > 0)",
            name="ck_hr_shift_assignment_scope_target",
        ),
        sa.CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="ck_hr_shift_assignment_effective_dates"),
    )
    for column in ("scope_type", "employee_id", "branch_id", "department", "shift_type_id", "valid_from", "valid_to"):
        op.create_index(f"ix_hr_shift_assignments_{column}", "hr_shift_assignments", [column])

    op.create_table(
        "hr_shift_roster_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("shift_type_id", sa.String(36), sa.ForeignKey("hr_shift_types.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("source_assignment_id", sa.String(36), sa.ForeignKey("hr_shift_assignments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_override", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("override_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("hr_branches.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("department_snapshot", sa.String(120), nullable=False, server_default=""),
        sa.Column("timezone_name", sa.String(64), nullable=False),
        sa.Column("scheduled_start_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_end_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shift_code_snapshot", sa.String(32), nullable=False, server_default=""),
        sa.Column("shift_name_snapshot", sa.String(120), nullable=False, server_default=""),
        sa.Column("break_rules_snapshot", sa.JSON(), nullable=False),
        sa.Column("policy_version_id", sa.String(36), sa.ForeignKey("hr_workforce_policy_versions.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("employee_id", "work_date", name="uq_hr_shift_roster_employee_day"),
        sa.CheckConstraint(
            "status IN ('scheduled', 'weekly_off', 'holiday', 'cancelled')",
            name="ck_hr_shift_roster_status",
        ),
        sa.CheckConstraint(
            "(status = 'scheduled' AND shift_type_id IS NOT NULL AND scheduled_start_at_utc IS NOT NULL "
            "AND scheduled_end_at_utc IS NOT NULL AND scheduled_end_at_utc > scheduled_start_at_utc) OR "
            "(status <> 'scheduled' AND shift_type_id IS NULL AND scheduled_start_at_utc IS NULL AND scheduled_end_at_utc IS NULL)",
            name="ck_hr_shift_roster_schedule_fields",
        ),
        sa.CheckConstraint(
            "is_override = false OR length(trim(override_reason)) > 0",
            name="ck_hr_shift_roster_override_reason",
        ),
    )
    for column in ("employee_id", "work_date", "source_assignment_id", "branch_id"):
        op.create_index(f"ix_hr_shift_roster_entries_{column}", "hr_shift_roster_entries", [column])


def downgrade() -> None:
    for column in ("branch_id", "source_assignment_id", "work_date", "employee_id"):
        op.drop_index(f"ix_hr_shift_roster_entries_{column}", table_name="hr_shift_roster_entries")
    op.drop_table("hr_shift_roster_entries")

    for column in ("valid_to", "valid_from", "shift_type_id", "department", "branch_id", "employee_id", "scope_type"):
        op.drop_index(f"ix_hr_shift_assignments_{column}", table_name="hr_shift_assignments")
    op.drop_table("hr_shift_assignments")

    op.drop_index("ix_hr_shift_break_rules_shift_type_id", table_name="hr_shift_break_rules")
    op.drop_table("hr_shift_break_rules")
    op.drop_table("hr_shift_types")

    op.drop_index("ix_hr_workforce_policy_versions_effective_to", table_name="hr_workforce_policy_versions")
    op.drop_index("ix_hr_workforce_policy_versions_effective_from", table_name="hr_workforce_policy_versions")
    op.drop_table("hr_workforce_policy_versions")
