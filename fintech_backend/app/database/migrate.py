"""
Database migrations, run from fintech_backend:

    python -m app.database.migrate status   # where the database is, and where the code is
    python -m app.database.migrate upgrade  # apply migrations (the deploy's release step)
    python -m app.database.migrate adopt    # one-off: a database made by create_all joins migrations

Production never creates tables at startup: it refuses to start until the database is at the
code's migration head, so new code never runs against an old schema.
"""

import os
import sys
from typing import Optional

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from .url import database_url, safe_url, with_driver

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class SchemaOutOfDate(RuntimeError):
    pass


def alembic_config(script_location: Optional[str] = None) -> Config:
    config = Config(os.path.join(HERE, "alembic.ini"))
    config.set_main_option("script_location", script_location or os.getenv("HOARDRUN_MIGRATIONS_DIR") or os.path.join(HERE, "alembic"))
    return config


def head_revision(config: Optional[Config] = None) -> str:
    return ScriptDirectory.from_config(config or alembic_config()).get_current_head()


def current_revision(engine: Engine) -> Optional[str]:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def schema_state(engine: Engine, config: Optional[Config] = None) -> dict:
    current, head = current_revision(engine), head_revision(config)
    return {"current": current, "head": head, "up_to_date": current == head}


def require_up_to_date(engine: Engine) -> None:
    state = schema_state(engine)
    if not state["up_to_date"]:
        raise SchemaOutOfDate(
            f"The database is at migration {state['current'] or 'none'} but this code needs {state['head']}. "
            "Run `python -m app.database.migrate upgrade` before starting the app."
        )


def differences(engine: Engine) -> list:
    """What the database lacks or has different from the models."""
    from .registry import metadata
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        return compare_metadata(context, metadata)


def adopt(engine: Engine, config: Optional[Config] = None) -> str:
    """Bring a database built by create_all under migrations without touching its data.

    Missing tables are created; if the existing tables then match the models exactly, the
    database is stamped at head. Anything else (a changed column) stops for a person to review.
    """
    from .registry import metadata
    config = config or alembic_config()
    if current_revision(engine) is not None:
        return "already managed by migrations"
    if not inspect(engine).get_table_names():
        return "empty database: run `upgrade` instead"
    pending = differences(engine)
    if pending and all((d[0] if isinstance(d, tuple) else None) in ("add_table", "add_index") for d in pending):
        metadata.create_all(engine, checkfirst=True)
        pending = differences(engine)
    if pending:
        details = "\n".join(f"  {str(d)[:200]}" for d in pending[:30])
        raise SchemaOutOfDate(f"The database differs from the models in ways that need a person to look:\n{details}")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.stamp(config, "head")
    return f"adopted at {head_revision(config)}"


# Any fixed number: the Postgres advisory lock that lets one server at a time run migrations
MIGRATION_LOCK_ID = 74192026


def upgrade_on_start() -> Optional[str]:
    """Opt-in (MIGRATE_ON_START=1) for hosts with no release step, such as Vercel.

    Runs at startup before the schema check. It uses the direct (unpooled) connection, since
    migrations need a real session, and holds an advisory lock so servers starting together
    migrate one at a time; the others then find the database already at head.
    """
    if os.getenv("MIGRATE_ON_START", "").strip().lower() not in ("1", "true", "yes"):
        return None
    raw = os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL_UNPOOLED") or database_url()
    engine = create_engine(with_driver(raw), pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            postgres = connection.dialect.name == "postgresql"
            if postgres:
                connection.execute(text("SELECT pg_advisory_lock(:id)"), {"id": MIGRATION_LOCK_ID})
                connection.commit()
            try:
                config = alembic_config()
                config.attributes["connection"] = connection
                before = MigrationContext.configure(connection).get_current_revision()
                command.upgrade(config, "head")
                connection.commit()
                after = MigrationContext.configure(connection).get_current_revision()
            finally:
                if postgres:
                    connection.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": MIGRATION_LOCK_ID})
                    connection.commit()
        return "already at head" if before == after else f"upgraded {before or 'empty'} -> {after}"
    finally:
        engine.dispose()


def main(argv: list) -> int:
    # Migrations run as the database owner; the app itself connects as a user that can't change tables
    if os.getenv("MIGRATION_DATABASE_URL"):
        os.environ["DATABASE_URL"] = os.environ["MIGRATION_DATABASE_URL"]
    url = database_url()
    engine = create_engine(url)
    action = argv[1] if len(argv) > 1 else "status"
    print(f"Database: {safe_url(url)}")
    if action == "status":
        state = schema_state(engine)
        print(f"At {state['current'] or 'no migrations'}; code needs {state['head']}. {'Up to date.' if state['up_to_date'] else 'Run upgrade.'}")
        return 0 if state["up_to_date"] else 1
    if action == "upgrade":
        command.upgrade(alembic_config(), "head")
        print(f"Upgraded to {head_revision()}")
        return 0
    if action == "adopt":
        try:
            print(adopt(engine))
            return 0
        except SchemaOutOfDate as error:
            print(error)
            return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
