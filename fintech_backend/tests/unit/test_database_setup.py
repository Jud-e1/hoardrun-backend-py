"""
The production database setup: the URL, migrations, adopting an existing database, and the
startup check. Runs on SQLite files; scripts/postgres_smoke.py runs the same on PostgreSQL.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_database_setup.py --noconftest --import-mode=importlib
"""

import os

# Must be set before the app is imported, so these tests can never reach a real database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from alembic import command
from sqlalchemy import Column, String, create_engine, inspect, text

from app.database import migrate, url
from app.database.registry import metadata


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    return monkeypatch


def test_postgres_urls_use_the_installed_driver(monkeypatch):
    for given in ("postgres://u:p@db.example.com:5432/app", "postgresql://u:p@db.example.com:5432/app"):
        monkeypatch.setenv("DATABASE_URL", given)
        assert url.database_url() == "postgresql+psycopg2://u:p@db.example.com:5432/app"


def test_production_needs_a_real_postgres_url(production):
    production.delenv("DATABASE_URL", raising=False)
    production.setattr(url.settings, "database_url", "")
    with pytest.raises(url.DatabaseUrlError):
        url.database_url()
    production.setenv("DATABASE_URL", "sqlite:///./prod.db")
    with pytest.raises(url.DatabaseUrlError):
        url.database_url()


def test_development_falls_back_to_a_local_file(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setattr(url.settings, "database_url", "")
    monkeypatch.setattr(url.settings, "environment", "development")
    assert url.database_url() == url.DEV_FALLBACK


def test_the_password_never_shows():
    shown = url.safe_url("postgresql+psycopg2://app:s3cret-pass@db.example.com:5432/hoardrun")
    assert "s3cret-pass" not in shown and "db.example.com" in shown


def test_no_connection_string_is_written_into_the_code():
    from app.config.settings import Settings
    assert Settings.model_fields["database_url"].default == ""


def engine_for(tmp_path, name):
    database = f"sqlite:///{(tmp_path / name).as_posix()}"
    return database, create_engine(database)


def test_migrations_build_every_table_from_empty(tmp_path, monkeypatch):
    database, engine = engine_for(tmp_path, "fresh.db")
    monkeypatch.setenv("DATABASE_URL", database)
    config = migrate.alembic_config()
    command.upgrade(config, "head")
    assert migrate.schema_state(engine, config)["up_to_date"]
    assert set(metadata.tables) <= set(inspect(engine).get_table_names())


def test_a_create_all_database_is_adopted_without_losing_data(tmp_path, monkeypatch):
    database, engine = engine_for(tmp_path, "existing.db")
    monkeypatch.setenv("DATABASE_URL", database)
    # An older deployment: most tables, some data, no migration history
    missing = {"auth_codes", "issued_cards", "issuing_holds", "brokerage_accounts", "broker_orders"}
    metadata.create_all(engine, tables=[t for name, t in metadata.tables.items() if name not in missing])
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users (id, email, password_hash, first_name, last_name, status, role) "
                                "VALUES ('u1', 'kept@example.com', 'x', 'Kept', 'Person', 'active', 'user')"))
    config = migrate.alembic_config()
    assert migrate.adopt(engine, config).startswith("adopted at")
    assert migrate.schema_state(engine, config)["up_to_date"]
    assert missing <= set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert connection.execute(text("SELECT email FROM users")).scalar() == "kept@example.com"
    assert migrate.adopt(engine, config) == "already managed by migrations"


def test_adopting_stops_when_a_column_differs(tmp_path, monkeypatch):
    database, engine = engine_for(tmp_path, "drifted.db")
    monkeypatch.setenv("DATABASE_URL", database)
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN nickname VARCHAR(20)"))
    with pytest.raises(migrate.SchemaOutOfDate) as stopped:
        migrate.adopt(engine, migrate.alembic_config())
    assert "nickname" in str(stopped.value)
    assert migrate.current_revision(engine) is None


def test_production_refuses_to_start_on_an_old_schema(tmp_path, monkeypatch):
    database, engine = engine_for(tmp_path, "behind.db")
    monkeypatch.setenv("DATABASE_URL", database)
    command.upgrade(migrate.alembic_config(), "58a6d0554597")
    with pytest.raises(migrate.SchemaOutOfDate) as refused:
        migrate.require_up_to_date(engine)
    assert "58a6d0554597" in str(refused.value) and "migrate upgrade" in str(refused.value)
    command.upgrade(migrate.alembic_config(), "head")
    migrate.require_up_to_date(engine)
