"""Seed exact grants for HR Admin overtime policy configuration.

Revision ID: p0_hr_overtime_policy_auth_023
Revises: p0_hr_overtime_policy_022
"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = "p0_hr_overtime_policy_auth_023"
down_revision = "p0_hr_overtime_policy_022"
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
        for action in ("view", "manage", "publish"):
            key = (role, "hr", "overtime_policies", action, "tenant")
            if key in existing:
                continue
            rows.append({
                "id": str(uuid.uuid4()), "role": role, "module": "hr",
                "feature": "overtime_policies", "action": action,
                "data_scope": "tenant", "allowed": True,
                "updated_by": "migration:p0_hr_overtime_policy_auth_023",
            })
    if rows:
        bind.execute(sa.insert(grants), rows)


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permission_grants "
        "WHERE module = 'hr' AND feature = 'overtime_policies' "
        "AND action IN ('view', 'manage', 'publish') "
        "AND updated_by = 'migration:p0_hr_overtime_policy_auth_023'"
    )
