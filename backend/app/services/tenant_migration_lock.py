"""PostgreSQL advisory locks for tenant schema operations.

Locks live in the control database, so concurrent application processes coordinate
without adding lock rows or relying on in-process state.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import text

from app.db.control import get_control_engine


def build_lock_key(*parts: str) -> str:
    values = [part.strip() for part in parts if part and part.strip()]
    if not values:
        raise ValueError("At least one lock-key component is required")
    return "minitally:" + "|".join(values)


@contextmanager
def advisory_lock(lock_key: str) -> Iterator[None]:
    """Hold a transaction-independent PostgreSQL advisory lock."""
    if not lock_key.strip():
        raise ValueError("Lock key is required")

    connection = get_control_engine().connect().execution_options(
        isolation_level="AUTOCOMMIT"
    )
    try:
        connection.execute(
            text("SELECT pg_advisory_lock(hashtextextended(:lock_key, 0))"),
            {"lock_key": lock_key},
        )
        yield
    finally:
        connection.execute(
            text("SELECT pg_advisory_unlock(hashtextextended(:lock_key, 0))"),
            {"lock_key": lock_key},
        )
        connection.close()


@contextmanager
def fleet_migration_lock() -> Iterator[None]:
    with advisory_lock(build_lock_key("tenant-migration", "fleet")):
        yield


@contextmanager
def company_migration_lock(company_id: str) -> Iterator[None]:
    with advisory_lock(build_lock_key("tenant-migration", "company", company_id)):
        yield
