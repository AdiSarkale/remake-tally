"""Add tenant-configurable employee code patterns and numbering.

Revision ID: hr_employee_codes_003
Revises: hr_employee_types_002
"""
import re

from alembic import op
import sqlalchemy as sa

revision = "hr_employee_codes_003"
down_revision = "hr_employee_types_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employee_code_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pattern", sa.String(length=120), nullable=False, server_default="EMP-{SEQ:03}"),
        sa.Column("sequence_start", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("next_sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("increment_by", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    bind = op.get_bind()
    codes = bind.execute(sa.text("SELECT emp_code FROM employees")).fetchall()
    highest = 0
    for (code,) in codes:
        match = re.fullmatch(r"EMP-(\d+)", code or "", flags=re.IGNORECASE)
        if match:
            highest = max(highest, int(match.group(1)))
    bind.execute(sa.text(
        "INSERT INTO employee_code_configs (id, pattern, sequence_start, next_sequence, increment_by) "
        "VALUES (1, 'EMP-{SEQ:03}', 1, :next_sequence, 1)"
    ), {"next_sequence": highest + 1})


def downgrade() -> None:
    op.drop_table("employee_code_configs")
