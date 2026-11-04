"""
Alembic environment for Hoardrun.

The database comes from DATABASE_URL (normalized in app/database/url.py), and the schema from
app/database/registry.py, which imports every module that defines a table.
"""

from logging.config import fileConfig
import os
import sys

from sqlalchemy import create_engine, pool

from alembic import context

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.database.registry import metadata  # noqa: E402
from app.database.url import database_url  # noqa: E402

config = context.config
url = database_url()

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = metadata


def options() -> dict:
    return {
        "target_metadata": target_metadata,
        # Notice column type and default changes, not just added tables and columns
        "compare_type": True,
        "compare_server_default": True,
        # SQLite can't ALTER most things; batch mode copies the table instead
        "render_as_batch": url.startswith("sqlite"),
    }


def run_migrations_offline() -> None:
    """Write the SQL instead of running it (alembic upgrade head --sql)."""
    context.configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"}, **options())
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # A caller (app/database/migrate.py) may hand over the connection to use
    handed = config.attributes.get("connection")
    if handed is not None:
        context.configure(connection=handed, **options())
        with context.begin_transaction():
            context.run_migrations()
        return
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, **options())
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
