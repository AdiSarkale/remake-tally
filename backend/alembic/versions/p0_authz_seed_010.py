"""Seed least-privilege role grants for initial HR leave workflows.

Revision ID: p0_authz_seed_010
Revises: p0_payroll_009
"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = "p0_authz_seed_010"
down_revision = "p0_payroll_009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = sa.table(
        "role_permission_grants",
        sa.column("id", sa.String(36)),
        sa.column("role", sa.String(64)),
        sa.column("module", sa.String(64)),
        sa.column("feature", sa.String(80)),
        sa.column("action", sa.String(32)),
        sa.column("data_scope", sa.String(24)),
        sa.column("allowed", sa.Boolean()),
        sa.column("updated_by", sa.String(64)),
    )
    grants = []
    for role in ("Admin", "HR"):
        for feature, action in (
            ("leave_types", "read"), ("leave_types", "write"),
            ("leave_balances", "read"), ("leave_balances", "write"),
            ("leave_requests", "read"), ("leave_requests", "approve"),
        ):
            grants.append({
                "id": str(uuid.uuid4()), "role": role, "module": "hr",
                "feature": feature, "action": action, "data_scope": "tenant",
                "allowed": True, "updated_by": "system",
            })
        for feature, action in (
            ("leave_types", "read"), ("leave_balances", "read"),
            ("leave_requests", "read"), ("leave_requests", "create"),
        ):
            grants.append({
                "id": str(uuid.uuid4()), "role": role, "module": "hr",
                "feature": feature, "action": action, "data_scope": "self",
                "allowed": True, "updated_by": "system",
            })
    for feature, action in (
        ("leave_types", "read"), ("leave_balances", "read"),
        ("leave_requests", "read"), ("leave_requests", "create"),
    ):
        grants.append({
            "id": str(uuid.uuid4()), "role": "Operator", "module": "hr",
            "feature": feature, "action": action, "data_scope": "self",
            "allowed": True, "updated_by": "system",
        })
    op.bulk_insert(table, grants)


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM role_permission_grants WHERE updated_by = 'system' "
        "AND module = 'hr' AND feature IN ('leave_types', 'leave_balances', 'leave_requests')"
    ))
