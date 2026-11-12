"""
Database configuration and session management.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool, QueuePool
from ..config.settings import settings
from .url import database_url, is_postgres, safe_url
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = database_url()


def get_engine_config():
    """Engine settings for the database in use."""
    config = {
        "pool_pre_ping": settings.database_pool_pre_ping,
        "echo": settings.database_echo,
        "pool_recycle": settings.database_pool_recycle,
    }

    if DATABASE_URL.startswith("sqlite"):
        config.update({
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False, "timeout": settings.database_connect_timeout},
        })
    elif is_postgres(DATABASE_URL):
        config.update({
            "poolclass": QueuePool,
            # Kept small: every server process holds its own pool, and hosted Postgres plans cap connections
            "pool_size": settings.database_pool_size,
            "max_overflow": settings.database_max_overflow,
            "pool_timeout": settings.database_pool_timeout,
            "pool_pre_ping": True,
            # Below the ~30 minute idle cut-off of most hosted poolers
            "pool_recycle": min(settings.database_pool_recycle, 1800),
            "connect_args": {
                "connect_timeout": settings.database_connect_timeout,
                "application_name": "hoardrun-api",
                # verify-full in production when the provider's CA certificate is installed; require at least
                "sslmode": settings.database_ssl_mode or "require",
                "keepalives_idle": 600,
                "keepalives_interval": 30,
                "keepalives_count": 3,
            },
        })

    return config

# Create database engine with optimized configuration
engine = create_engine(DATABASE_URL, **get_engine_config())

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def create_tables():
    """Create any missing tables (development and tests only; production uses migrations)."""
    try:
        from . import registry  # noqa: F401 - every table module, so none is missed
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        return False


def get_db():
    """
    Dependency to get database session.
    """
    db = None
    try:
        db = SessionLocal()
        # Test the connection by executing a simple query
        db.execute(text("SELECT 1"))
        yield db
    except Exception as e:
        logger.error(f"Database session creation failed: {e}")
        if db:
            db.close()
        # Re-raise the exception to be handled by the endpoint
        raise
    finally:
        if db:
            db.close()


def drop_tables():
    """
    Drop all tables in the database. Never in production, whoever calls it.
    """
    from ..auth.signing_key import is_production
    if is_production():
        raise RuntimeError("Refusing to drop tables in production")
    Base.metadata.drop_all(bind=engine)


def check_database_connection():
    """
    Check if database connection is healthy.
    Returns True if connection is successful, False otherwise.
    """
    try:
        # Use a shorter timeout for health checks
        with engine.connect() as connection:
            # Simple query to test connection
            result = connection.execute(text("SELECT 1"))
            result.fetchone()  # Ensure we actually get the result
        logger.info("Database connection check successful")
        return True
    except Exception as e:
        # Log the error but don't make it critical
        error_msg = str(e)
        if "SSL connection has been closed unexpectedly" in error_msg:
            logger.warning("Database SSL connection issue (common during startup)")
        elif "connection to server" in error_msg and "failed" in error_msg:
            logger.warning("Database server connection failed (may be temporary)")
        else:
            logger.warning(f"Database connection check failed: {error_msg}")
        return False


def get_database_info():
    """
    Get database connection information and statistics.
    """
    try:
        with engine.connect() as connection:
            # Get database version
            if is_postgres(DATABASE_URL):
                result = connection.execute(text("SHOW server_version"))
                version = f"PostgreSQL {result.fetchone()[0]}"
            elif DATABASE_URL.startswith("sqlite"):
                result = connection.execute(text("SELECT sqlite_version()"))
                version = f"SQLite {result.fetchone()[0]}"
            else:
                version = "Unknown"

            # Get pool statistics
            pool_info = {
                "pool_size": getattr(engine.pool, 'size', 'N/A'),
                "checked_in": getattr(engine.pool, 'checkedin', 'N/A'),
                "checked_out": getattr(engine.pool, 'checkedout', 'N/A'),
                "overflow": getattr(engine.pool, 'overflow', 'N/A'),
            }

            return {
                # Host and database name only; the password is never shown
                "database_url": safe_url(DATABASE_URL),
                "database_version": version,
                "pool_info": pool_info,
                "connection_healthy": True
            }
    except Exception as e:
        logger.error(f"Failed to get database info: {e}")
        # The error text can carry connection details, so it stays in the server log
        return {"database_url": safe_url(DATABASE_URL), "error": "Database unavailable", "connection_healthy": False}


def initialize_database():
    """
    Development creates missing tables. Production changes nothing: it checks the database is at
    the code's migration head and raises SchemaOutOfDate if not, so the app refuses to start.
    """
    from ..auth.signing_key import is_production
    if is_production():
        from .migrate import SchemaOutOfDate, require_up_to_date, upgrade_on_start
        try:
            # Hosts without a release step (Vercel) migrate here, when MIGRATE_ON_START=1
            migrated = upgrade_on_start()
            if migrated:
                logger.info("Migrations at startup: %s", migrated)
            require_up_to_date(engine)
        except SchemaOutOfDate:
            raise
        except Exception as error:
            # Not being able to check is as unsafe as being behind
            logger.error("Couldn't check the database schema: %s", type(error).__name__)
            raise SchemaOutOfDate(f"Couldn't confirm the database schema ({type(error).__name__}). "
                                  "Check DATABASE_URL and that the app's database user can read alembic_version.") from error
        logger.info("Database schema is at the current migration")
        return True
    try:
        logger.info("Initializing database...")
        create_tables()
        logger.info("Database initialization completed successfully")
        return True
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False
