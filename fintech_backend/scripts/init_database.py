#!/usr/bin/env python3
"""
Database initialization script for the fintech backend.

This script handles:
- Database connection verification
- Running Alembic migrations
- Creating initial data if needed
- Database health checks

Usage:
    python scripts/init_database.py [options]

Options:
    --check-only    Only check database connection, don't run migrations
    --force-reset   Drop all tables and recreate (DANGEROUS - use with caution)
    --create-sample-data    Create sample data for development
    --verbose       Enable verbose logging
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# Add the parent directory to the path so we can import our app
sys.path.insert(0, str(Path(__file__).parent.parent))

from ..database import (
    check_database_connection, 
    get_database_info, 
    initialize_database,
    create_tables,
    drop_tables,
    engine
)
from ..config.settings import get_settings
from alembic.config import Config
from alembic import command
from sqlalchemy.exc import OperationalError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_database():
    """Check database connection and display information."""
    logger.info("Checking database connection...")
    
    if check_database_connection():
        logger.info("✓ Database connection successful")
        
        # Get and display database info
        db_info = get_database_info()
        logger.info(f"Database URL: {db_info.get('database_url', 'Unknown')}")
        logger.info(f"Database Version: {db_info.get('database_version', 'Unknown')}")
        
        pool_info = db_info.get('pool_info', {})
        if pool_info:
            logger.info(f"Connection Pool - Size: {pool_info.get('pool_size', 'N/A')}, "
                       f"Checked In: {pool_info.get('checked_in', 'N/A')}, "
                       f"Checked Out: {pool_info.get('checked_out', 'N/A')}")
        
        return True
    else:
        logger.error("✗ Database connection failed")
        return False


def run_migrations():
    """Run Alembic database migrations."""
    logger.info("Running database migrations...")
    
    try:
        # Get the directory where this script is located
        script_dir = Path(__file__).parent.parent
        alembic_cfg_path = script_dir / "alembic.ini"
        
        if not alembic_cfg_path.exists():
            logger.error(f"Alembic configuration file not found: {alembic_cfg_path}")
            return False
        
        # Configure Alembic
        alembic_cfg = Config(str(alembic_cfg_path))
        alembic_cfg.set_main_option("script_location", str(script_dir / "alembic"))
        
        # Run migrations
        command.upgrade(alembic_cfg, "head")
        logger.info("✓ Database migrations completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Database migration failed: {e}")
        return False


def create_sample_data():
    """Create sample data for development."""
    logger.info("Creating sample data...")
    
    try:
        from ..database.models import User, Account, AccountTypeEnum, AccountStatusEnum
        from ..database.config import SessionLocal
        from decimal import Decimal
        import uuid
        from datetime import datetime
        
        db = SessionLocal()
        
        try:
            # Check if sample data already exists
            existing_user = db.query(User).filter(User.email == "admin@hoardrun.com").first()
            if existing_user:
                logger.info("Sample data already exists, skipping creation")
                return True
            
            # Create sample user
            sample_user = User(
                id=str(uuid.uuid4()),
                email="admin@hoardrun.com",
                first_name="Admin",
                last_name="User",
                phone_number="+1234567890",
                is_active=True,
                is_verified=True,
                password_hash="$2b$12$dummy_hash_for_development",  # This should be properly hashed in real usage
                email_verified=True,
                status="active",
                role="admin",
                country="US",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(sample_user)
            db.flush()  # Get the user ID
            
            # Create sample account
            sample_account = Account(
                id=str(uuid.uuid4()),
                user_id=sample_user.id,
                account_number="ACC001234567890",
                account_name="Primary Checking Account",
                account_type=AccountTypeEnum.CHECKING,
                status=AccountStatusEnum.ACTIVE,
                current_balance=Decimal("1000.00"),
                available_balance=Decimal("1000.00"),
                pending_balance=Decimal("0.00"),
                reserved_balance=Decimal("0.00"),
                currency="USD",
                is_primary=True,
                is_overdraft_enabled=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(sample_account)
            db.commit()
            
            logger.info("✓ Sample data created successfully")
            logger.info(f"  - Sample user: {sample_user.email}")
            logger.info(f"  - Sample account: {sample_account.account_number}")
            
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"✗ Failed to create sample data: {e}")
        return False


def reset_database():
    """Reset the database by dropping and recreating all tables."""
    logger.warning("RESETTING DATABASE - This will delete all data!")
    
    try:
        logger.info("Dropping all tables...")
        drop_tables()
        
        logger.info("Creating tables...")
        create_tables()
        
        logger.info("✓ Database reset completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Database reset failed: {e}")
        return False


def main():
    """Main function to handle command line arguments and execute operations."""
    parser = argparse.ArgumentParser(description="Initialize the fintech backend database")
    parser.add_argument("--check-only", action="store_true", 
                       help="Only check database connection, don't run migrations")
    parser.add_argument("--force-reset", action="store_true",
                       help="Drop all tables and recreate (DANGEROUS)")
    parser.add_argument("--create-sample-data", action="store_true",
                       help="Create sample data for development")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    settings = get_settings()
    logger.info(f"Initializing database for environment: {settings.environment}")
    
    # Check database connection first
    if not check_database():
        logger.error("Cannot proceed without a valid database connection")
        sys.exit(1)
    
    if args.check_only:
        logger.info("Database check completed successfully")
        sys.exit(0)
    
    if args.force_reset:
        if settings.environment == "production":
            logger.error("Cannot reset database in production environment")
            sys.exit(1)
        
        confirm = input("Are you sure you want to reset the database? This will delete all data! (yes/no): ")
        if confirm.lower() != "yes":
            logger.info("Database reset cancelled")
            sys.exit(0)
        
        if not reset_database():
            sys.exit(1)
    
    # Run migrations
    if not run_migrations():
        sys.exit(1)
    
    # Create sample data if requested
    if args.create_sample_data:
        if not create_sample_data():
            logger.warning("Sample data creation failed, but continuing...")
    
    logger.info("Database initialization completed successfully!")


if __name__ == "__main__":
    main()
