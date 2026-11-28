"""Replace legacy module wildcard grants with explicit route feature/action grants.

Revision ID: p0_authz_exact_015
Revises: p0_finance_journal_014
"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = "p0_authz_exact_015"
down_revision = "p0_finance_journal_014"
branch_labels = None
depends_on = None

# Preserve the existing role-to-module access boundary while making every
# module-guarded route require an exact feature/action grant. This is a
# compatibility migration, not a claim that the business has approved a
# narrower job-description matrix for every customer.
ROLE_MODULES = {
    "Admin": {"masters", "inventory", "production", "scrap", "sales", "finance", "settings", "reports", "approvals", "purchase_requests", "hr"},
    "Accountant": {"masters", "inventory", "sales", "reports", "approvals", "purchase_requests"},
    "Operator": {"production", "scrap", "inventory", "approvals", "purchase_requests"},
    "HR": {"hr"},
}

# Feature names/actions are the normalized values produced by
# app.api.deps._route_feature_action for routes protected by require_area or
# require_any_area. Only actual route actions are seeded.
MODULE_FEATURE_ACTIONS = {
    "masters": {
        "bom": {"read", "create", "update", "delete"},
        "customers": {"read", "create", "update", "delete"},
        "suppliers": {"read", "create", "update", "delete"},
        "products": {"read", "create", "update"},
        "materials": {"read", "create"},
        "scrap_types": {"read", "create"},
        "plants": {"read", "create", "update", "delete"},
        "warehouses": {"read", "create", "update", "delete"},
        "supplier_products": {"read", "create", "update", "delete"},
        "orders": {"read", "create", "update", "delete"},
        "grns": {"read", "create", "update", "delete"},
        "movements": {"create"},
        "requisitions": {"update"},
    },
    "inventory": {
        "movements": {"read"},
        "valuation": {"read"},
    },
    "production": {
        "employees": {"read"},
        "employee_types": {"read"},
        "workcenters": {"read", "create", "update"},
        "routings": {"read", "create"},
        "production_orders": {"read", "create", "update"},
        "production": {"update"},
        "reports": {"read"},
    },
    "scrap": {"scrap": {"read", "create"}},
    "sales": {
        "customer_pos": {"read", "create", "update", "delete"},
        "delivery": {"read"},
        "deliveries": {"read"},
        "dispatches": {"read", "create", "update"},
        "quotations": {"read", "update"},
        "sales_orders": {"read", "create", "update"},
        "invoices": {"read", "create", "update"},
    },
    "finance": {
        "customer_payments": {"read", "create"},
        "supplier_payments": {"read", "create"},
        "receivables": {"read"},
        "payables": {"read"},
        "accounts": {"read", "create"},
        "payroll_account_mapping": {"read", "update"},
        "journals": {"read"},
    },
    "settings": {
        "settings": {"read", "update"},
        "audit": {"read"},
        "users": {"update", "create"},
    },
    "hr": {
        "employee_code_config": {"read", "update"},
        "employee_duplicates": {"read"},
        "employees": {"read", "create", "update"},
        "employee_types": {"read", "create", "update", "delete"},
    },
    "purchase_requests": {
        "requisitions": {"read", "create"},
    },
}

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
    for role, modules in ROLE_MODULES.items():
        for module in modules:
            for feature, actions in MODULE_FEATURE_ACTIONS.get(module, {}).items():
                for action in actions:
                    key = (role, module, feature, action, "tenant")
                    if key in existing:
                        continue  # retain any previously explicit Admin decision
                    rows.append({
                        "id": str(uuid.uuid4()), "role": role, "module": module,
                        "feature": feature, "action": action, "data_scope": "tenant",
                        "allowed": True, "updated_by": "migration:p0_authz_exact_015",
                    })
    if rows:
        op.bulk_insert(grants, rows)

    # The route guard no longer consults wildcard grants. Remove them so the
    # database state matches the enforced policy and cannot mask missing grants.
    op.execute(sa.delete(grants).where(
        grants.c.feature == "*",
        grants.c.action == "*",
        grants.c.data_scope == "tenant",
    ))


def downgrade() -> None:
    bind = op.get_bind()
    grants = sa.Table("role_permission_grants", sa.MetaData(), autoload_with=bind)
    op.execute(sa.delete(grants).where(
        grants.c.updated_by == "migration:p0_authz_exact_015",
    ))
    rows = []
    for role, modules in ROLE_MODULES.items():
        for module in modules:
            rows.append({
                "id": str(uuid.uuid4()), "role": role, "module": module,
                "feature": "*", "action": "*", "data_scope": "tenant",
                "allowed": True, "updated_by": "system",
            })
    op.bulk_insert(grants, rows)
