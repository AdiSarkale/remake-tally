"""Seed feature/action wildcard defaults preserving the legacy module role matrix.

Revision ID: p0_granular_authz_012
Revises: p0_org_structure_011
"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = "p0_granular_authz_012"
down_revision = "p0_org_structure_011"
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
    legacy_access = {
        "Admin": {"masters", "inventory", "production", "scrap", "sales", "finance", "settings", "reports", "approvals", "purchase_requests", "hr"},
        "Accountant": {"masters", "inventory", "sales", "reports", "approvals", "purchase_requests"},
        "Operator": {"production", "scrap", "inventory", "approvals", "purchase_requests"},
        "HR": {"hr"},
    }
    rows = []
    for role, modules in legacy_access.items():
        for module in modules:
            rows.append({
                "id": str(uuid.uuid4()), "role": role, "module": module,
                "feature": "*", "action": "*", "data_scope": "tenant",
                "allowed": True, "updated_by": "system",
            })
    op.bulk_insert(table, rows)


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM role_permission_grants WHERE updated_by = 'system' "
        "AND feature = '*' AND action = '*' AND data_scope = 'tenant'"
    ))
