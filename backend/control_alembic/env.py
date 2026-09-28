from alembic import context
from sqlalchemy import engine_from_config, pool
from app.core.config import get_settings
from app.db.control_models import ControlBase

config = context.config
settings = get_settings()
target_metadata = ControlBase.metadata


def _database_url() -> str:
    return config.get_main_option("sqlalchemy.url") or settings.control_database_url or ""


def run_migrations_offline():
    url = _database_url()
    if not url:
        raise RuntimeError("CONTROL_DATABASE_URL is required")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    url = _database_url()
    if not url:
        raise RuntimeError("CONTROL_DATABASE_URL is required")
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_offline() if context.is_offline_mode() else run_migrations_online()
