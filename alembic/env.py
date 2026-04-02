"""Alembic environment configuration for async SQLAlchemy."""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# Alembic Config object — provides access to values in alembic.ini.
# ---------------------------------------------------------------------------
config = context.config

# Interpret alembic.ini's logging config section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Import app models so that Base.metadata is populated for autogenerate.
# ---------------------------------------------------------------------------
import sys
import os

# Ensure the backend/ directory is on sys.path so `app` can be imported.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base  # noqa: E402
import app.models  # noqa: F401, E402  — registers all ORM classes on Base

# Override the sqlalchemy.url with the value from the application settings so
# there is a single source of truth.
from app.config import settings  # noqa: E402

config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Run migrations
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL without a live connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using an async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
