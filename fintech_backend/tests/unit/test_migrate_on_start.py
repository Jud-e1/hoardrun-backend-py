"""
MIGRATE_ON_START: hosts without a release step (Vercel) bring the database to the migration head
at startup; without the setting nothing is migrated.

Run from fintech_backend with (HOARDRUN_MIGRATIONS_DIR set to a short copy of alembic/ on Windows):
PYTHONPATH=. python -m pytest tests/unit/test_migrate_on_start.py --noconftest --import-mode=importlib
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine, inspect

from app.database import migrate


def test_off_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("MIGRATE_ON_START", raising=False)
    assert migrate.upgrade_on_start() is None


def test_migrates_an_empty_database_once(monkeypatch, tmp_path):
    db = tmp_path / "fresh.db"
    monkeypatch.setenv("MIGRATE_ON_START", "1")
    monkeypatch.setenv("MIGRATION_DATABASE_URL", f"sqlite:///{db}")
    first = migrate.upgrade_on_start()
    assert first.startswith("upgraded empty ->")
    engine = create_engine(f"sqlite:///{db}")
    assert migrate.schema_state(engine)["up_to_date"]
    assert {"users", "login_throttle", "auth_tickets"} <= set(inspect(engine).get_table_names())
    # A second server starting later finds nothing to do
    assert migrate.upgrade_on_start() == "already at head"


def test_prefers_the_unpooled_url(monkeypatch, tmp_path):
    db = tmp_path / "direct.db"
    monkeypatch.setenv("MIGRATE_ON_START", "true")
    monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL_UNPOOLED", f"sqlite:///{db}")
    assert migrate.upgrade_on_start().startswith("upgraded")
    assert db.exists()
