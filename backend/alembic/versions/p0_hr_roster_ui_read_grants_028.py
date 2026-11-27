"""Seed exact roster read grants for the P0.1-11 attendance workspace.

Revision ID: p0_hr_roster_ui_read_028
Revises: p0_hr_payroll_supersede_027
"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = "p0_hr_roster_ui_read_028"
down_revision = "p0_hr_payroll_supersede_027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    grants = sa.Table("role_permission_grants", sa.MetaData(), autoload_with=bind)
    existing = {
        (row.role, row.module, row.feature, row.action, row.data_scope)
        for row in bind.execute(sa.select(
            grants.c.role, grants.c.module, grants.c.feature,
            grants.c.action, grants.c.data_scope,
        ))
    }
    rows = []
    for role in ("Admin", "HR"):
        key = (role, "hr", "shift_rosters", "read", "tenant")
        if key not in existing:
            rows.append({
                "id": str(uuid.uuid4()),
                "role": role,
                "module": "hr",
                "feature": "shift_rosters",
                "action": "read",
                "data_scope": "tenant",
                "allowed": True,
                "updated_by": "migration:p0_hr_roster_ui_read_028",
            })
    if rows:
        op.bulk_insert(grants, rows)


def downgrade() -> None:
    bind = op.get_bind()
    grants = sa.Table("role_permission_grants", sa.MetaData(), autoload_with=bind)
    op.execute(sa.delete(grants).where(
        grants.c.updated_by == "migration:p0_hr_roster_ui_read_028",
    ))
