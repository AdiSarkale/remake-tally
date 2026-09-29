"""Resolve tenant database credentials from runtime secret references.

The control database stores only a reference. The actual secret is supplied by
the deployment secret manager, typically injected into the process environment
or mounted through a secret provider. This adapter is deliberately provider-
neutral so the ERP is not coupled to one cloud vendor.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.core.config import get_settings
from app.services.secret_provider import get_secret_provider

_SECRET_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")

def resolve_tenant_database_url(secret_ref: str) -> str:
    """Resolve a tenant DB URL without storing it in the control database."""
    if not _SECRET_REF_RE.fullmatch(secret_ref):
        raise RuntimeError("Invalid tenant database secret reference")

    settings = get_settings()
    if secret_ref == "LOCAL_DEFAULT" and settings.environment.lower() != "production":
        return settings.database_url

    value = get_secret_provider().get_secret(secret_ref)
    return _enforce_postgres_tls(value)


def _enforce_postgres_tls(database_url: str) -> str:
    """Require encrypted PostgreSQL tenant connections in production."""
    settings = get_settings()
    if not settings.tenant_db_require_tls or settings.environment.lower() != "production":
        return database_url

    parts = urlsplit(database_url)
    if parts.scheme not in {"postgresql", "postgresql+psycopg"}:
        return database_url

    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    sslmode = query.get("sslmode", "").lower()
    if sslmode in {"require", "verify-ca", "verify-full"}:
        return database_url
    if sslmode and sslmode != "disable":
        raise RuntimeError("Unsupported PostgreSQL sslmode for production tenant connection")
    query["sslmode"] = "require"
    return urlunsplit(parts._replace(query=urlencode(query)))
