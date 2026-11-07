"""Regression tests for database URL normalization.

PostgreSQL-specific URL handling must not rewrite SQLite URLs used by tests.
"""

import sys
from pathlib import Path

# Match the backend test-suite import setup used by existing integration tests.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings


def test_sqlite_url_is_preserved():
    assert Settings(database_url="sqlite://").database_url == "sqlite://"


def test_sqlite_memory_url_is_preserved():
    url = "sqlite+pysqlite:///:memory:"
    assert Settings(database_url=url).database_url == url


def test_legacy_postgres_url_uses_psycopg_and_normalizes_ssl_mode():
    settings = Settings(
        database_url="postgres://user:password@db.example.test/app?ssl_mode=require"
    )
    assert settings.database_url == (
        "postgresql+psycopg://user:password@db.example.test/app?sslmode=require"
    )


def test_control_postgres_url_normalizes_ssl_mode():
    settings = Settings(
        control_database_url="postgresql://user:password@db.example.test/control?ssl_mode=verify-full"
    )
    assert settings.control_database_url == (
        "postgresql+psycopg://user:password@db.example.test/control?sslmode=verify-full"
    )
