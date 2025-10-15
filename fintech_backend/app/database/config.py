"""
Database configuration and session management.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool, QueuePool
from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)

def get_engine_config():
    """Get database engine configuration based on database type and environment."""
    config = {
        "pool_pre_ping": settings.database_pool_pre_ping,
        "echo": settings.database_echo or settings.debug,
        "pool_recycle": settings.database_pool_recycle,
    }

    if settings.database_url.startswith("sqlite"):
        # SQLite-specific configuration
        config.update({
            "poolclass": StaticPool,
            "connect_args": {
                "check_same_thread": False,
                "timeout": settings.database_connect_timeout
            }
        })
    elif settings.database_url.startswith("postgresql"):
        # PostgreSQL-specific configuration with enhanced SSL handling for Render
        # Use more permissive SSL settings for cloud databases
        ssl_mode = settings.database_ssl_mode if hasattr(settings, 'database_ssl_mode') else "prefer"

        # For Render PostgreSQL, we need to be more flexible with SSL
        connect_args = {
            "connect_timeout": 60,  # Longer timeout for cloud connections
            "application_name": f"{settings.app_name} v{settings.app_version}",
        }

        # Only add SSL settings if not disabled
        if ssl_mode != "disable":
            connect_args.update({
                "sslmode": ssl_mode,
                "sslcert": None,  # Don't use client certificates
                "sslkey": None,   # Don't use client keys
                "sslrootcert": None,  # Don't verify server certificate
            })

        # Add keepalive settings for stable connections
        connect_args.update({
            "keepalives_idle": 600,      # 10 minutes before sending keepalive
            "keepalives_interval": 30,   # Send keepalive every 30s
            "keepalives_count": 3,       # Max 3 failed keepalives before disconnect
        })

        config.update({
            "poolclass": QueuePool,
            "pool_size": settings.database_pool_size,
            "max_overflow": settings.database_max_overflow,
            "pool_timeout": settings.database_pool_timeout,
            "pool_pre_ping": True,  # Verify connections before use
            "pool_recycle": 3600,   # Recycle connections every hour
            "connect_args": connect_args
        })

    return config

# Create database engine with optimized configuration
engine = create_engine(settings.database_url, **get_engine_config())

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def create_tables():
    """Create all database tables."""
    try:
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
    Drop all tables in the database.
    """
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
            if settings.database_url.startswith("postgresql"):
                result = connection.execute(text("SELECT version()"))
                version = result.fetchone()[0]
            elif settings.database_url.startswith("sqlite"):
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
                "database_url": settings.database_url.split('@')[0] + '@***',  # Hide credentials
                "database_version": version,
                "pool_info": pool_info,
                "connection_healthy": True
            }
    except Exception as e:
        logger.error(f"Failed to get database info: {e}")
        return {
            "database_url": settings.database_url.split('@')[0] + '@***',
            "error": str(e),
            "connection_healthy": False
        }


def initialize_database():
    """
    Initialize database with tables and basic setup.
    """
    try:
        logger.info("Initializing database...")
        create_tables()
        logger.info("Database initialization completed successfully")
        return True
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False
