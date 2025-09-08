"""
Database configuration and session management.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.config.settings import settings

# Create database engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.debug,  # Log SQL queries in debug mode
    # For SQLite compatibility (if needed for testing)
    poolclass=StaticPool if settings.database_url.startswith("sqlite") else None,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def get_db():
    """
    Dependency to get database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """
    Create all tables in the database.
    """
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """
    Drop all tables in the database.
    """
    Base.metadata.drop_all(bind=engine)
