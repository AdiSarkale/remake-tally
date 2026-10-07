"""Command-line tenant backup/restore utility.

Run from backend:
    python scripts/tenant_backup.py backup --company DEMO --output backups/demo.dump
    python scripts/tenant_backup.py restore --company DEMO --backup backups/demo.dump \
        --target-url postgresql+psycopg://user:pass@host/replacement
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.tenant_backup import (  # noqa: E402
    TenantBackupError,
    backup_registered_tenant,
    restore_registered_tenant,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minitally tenant DR utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup = subparsers.add_parser("backup", help="Back up an active tenant")
    backup.add_argument("--company", required=True)
    backup.add_argument("--output", required=True, type=Path)

    restore = subparsers.add_parser("restore", help="Restore into a replacement database")
    restore.add_argument("--company", required=True)
    restore.add_argument("--backup", required=True, type=Path)
    restore.add_argument("--target-url", required=True)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "backup":
            path = backup_registered_tenant(args.company, args.output)
            print(f"Backup created: {path}")
        else:
            restore_registered_tenant(
                args.company,
                args.backup,
                args.target_url,
            )
            print("Restore completed")
        return 0
    except TenantBackupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
