"""Read-only production preflight for registered tenant migration revisions."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow direct execution from the backend directory:
#   py scripts/audit_tenant_migrations.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.tenant_migration_audit import audit_ready_tenants


def main() -> int:
    results = audit_ready_tenants()
    if not results:
        print("No active/ready tenants found.")
        return 0

    failed = False
    for result in results:
        suffix = f" - {result.detail}" if result.detail else ""
        print(
            f"{result.company_code}: {result.status} "
            f"(revision={result.revision or 'none'}){suffix}"
        )
        failed |= result.status != "ready"

    if failed:
        print("Tenant migration preflight FAILED.", file=sys.stderr)
        return 1

    print("Tenant migration preflight PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
