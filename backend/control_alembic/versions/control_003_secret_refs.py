"""Move tenant DB credentials behind deployment secret references.

For existing control-plane rows, the migration derives a deterministic secret
reference from the normalized company code and verifies that the corresponding
runtime secret is available before removing database_url. The database URL is
never copied into database_secret_ref.
"""

from __future__ import annotations

import os
import re

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "control_003"
down_revision = "control_002"
branch_labels = None
depends_on = None

_SECRET_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_ENV_PREFIX = "TENANT_DB_URL_"


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column(
        "tenant_companies",
        sa.Column("database_secret_ref", sa.String(length=160), nullable=True),
    )

    # Existing companies receive a deterministic reference based on their
    # normalized company code. Only the reference is written; the plaintext
    # database_url remains untouched until all references are validated.
    bind.execute(
        text(
            "UPDATE tenant_companies "
            "SET database_secret_ref = upper(code) "
            "WHERE database_secret_ref IS NULL"
        )
    )

    rows = bind.execute(
        text("SELECT code, database_secret_ref FROM tenant_companies")
    ).all()

    invalid_refs: list[str] = []
    missing_secrets: list[str] = []

    for code, secret_ref in rows:
        if not isinstance(secret_ref, str) or not _SECRET_REF_RE.fullmatch(secret_ref):
            invalid_refs.append(str(code))
            continue
        if not os.getenv(f"{_ENV_PREFIX}{secret_ref}"):
            missing_secrets.append(secret_ref)

    if invalid_refs or missing_secrets:
        problems: list[str] = []
        if invalid_refs:
            problems.append(
                "invalid secret references for companies: "
                + ", ".join(sorted(invalid_refs))
            )
        if missing_secrets:
            problems.append(
                "missing tenant DB secrets: "
                + ", ".join(sorted(set(missing_secrets)))
            )
        raise RuntimeError(
            "control_003 cannot remove plaintext tenant DB URLs; "
            + "; ".join(problems)
        )

    op.alter_column(
        "tenant_companies",
        "database_secret_ref",
        existing_type=sa.String(length=160),
        nullable=False,
    )
    op.drop_column("tenant_companies", "database_url")


def downgrade() -> None:
    raise RuntimeError(
        "control_003 is irreversible: database credentials were intentionally "
        "removed from the control database"
    )
