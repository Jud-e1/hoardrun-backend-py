"""
Which database to use, read from DATABASE_URL.

- Postgres URLs are pinned to the psycopg2 driver (in requirements). SQLAlchemy 2.1 would
  otherwise pick psycopg 3, which isn't installed, and the first connection would fail.
- Production refuses to start without a database URL or on SQLite; development falls back
  to a local SQLite file.
- safe_url() is the only form that may be logged or shown: the password is never included.
"""

import os

from sqlalchemy.engine import make_url

from ..config.settings import settings

DEV_FALLBACK = "sqlite:///./hoardrun-local-dev.db"


class DatabaseUrlError(RuntimeError):
    pass


def _production() -> bool:
    return (os.getenv("ENVIRONMENT") or settings.environment or "").lower() == "production"


def database_url() -> str:
    raw = (os.getenv("DATABASE_URL") or settings.database_url or "").strip()
    if not raw:
        if _production():
            raise DatabaseUrlError("DATABASE_URL must be set in production")
        return DEV_FALLBACK
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://"):
        raw = "postgresql+psycopg2://" + raw[len("postgresql://"):]
    if _production() and raw.startswith("sqlite"):
        raise DatabaseUrlError("Production needs a PostgreSQL DATABASE_URL, not SQLite")
    return raw


def is_postgres(url: str) -> bool:
    return url.startswith("postgresql")


def safe_url(url: str) -> str:
    """The URL with any password replaced, for logs and health checks."""
    try:
        return make_url(url).render_as_string(hide_password=True)
    except Exception:
        return "unparseable database URL"
