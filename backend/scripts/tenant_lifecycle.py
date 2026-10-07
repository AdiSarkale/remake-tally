"""Command-line tenant lifecycle utility."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.tenant_lifecycle import decommission_company  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minitally tenant lifecycle utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    decommission = subparsers.add_parser(
        "decommission",
        help="Disable a tenant and require a verified database backup",
    )
    decommission.add_argument("--company-id", required=True)
    decommission.add_argument("--backup", required=True, type=Path)
    decommission.add_argument("--reason", required=True)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "decommission":
        decommission_company(
            args.company_id,
            args.backup,
            reason=args.reason,
        )
        print("Tenant decommissioned")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
