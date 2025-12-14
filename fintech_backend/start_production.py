#!/usr/bin/env python3
"""
Production startup script for HoardRun Backend API.
This script ensures proper initialization before starting the server.
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from ..config.settings import get_settings
from ..config.logging import setup_logging, get_logger
from ..database.config import check_database_connection, initialize_database

def wait_for_database(max_retries=30, retry_delay=2):
    """
    Wait for database to become available.
    
    Args:
        max_retries (int): Maximum number of retry attempts
        retry_delay (int): Delay between retries in seconds
    
    Returns:
        bool: True if database is available, False otherwise
    """
    logger = get_logger("startup")
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Database connection attempt {attempt}/{max_retries}")
            
            if check_database_connection():
                logger.info("✅ Database connection successful!")
                return True
                
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt} failed: {e}")
        
        if attempt < max_retries:
            logger.info(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
    
    logger.error(f"❌ Failed to connect to database after {max_retries} attempts")
    return False


def initialize_application():
    """
    Initialize the application with proper error handling.

    Returns:
        bool: True if initialization successful, False otherwise
    """
    try:
        # Get settings
        settings = get_settings()

        # Setup logging
        setup_logging(settings)
        logger = get_logger("startup")

        logger.info("🚀 Initializing HoardRun Backend API...")
        logger.info(f"Environment: {settings.environment}")
        logger.info(f"Debug Mode: {settings.debug}")
        logger.info(f"Database URL: {settings.database_url.split('@')[0]}@***")

        # Try to wait for database, but don't fail if it's not available
        logger.info("🔍 Attempting to connect to database...")
        db_available = wait_for_database(max_retries=10, retry_delay=1)  # Reduced retries for faster startup

        if db_available:
            # Initialize database
            logger.info("🗄️ Initializing database...")
            if initialize_database():
                logger.info("✅ Database initialization completed successfully!")
            else:
                logger.warning("⚠️ Database initialization failed, but continuing...")
        else:
            logger.warning("⚠️ Database not immediately available, but continuing startup...")
            logger.info("💡 Application will handle database connections per-request")

        logger.info("✅ Application initialization completed successfully!")
        return True

    except Exception as e:
        logger.error(f"💥 Application initialization failed: {e}")
        logger.info("🔄 Continuing anyway - some features may be limited until database is available")
        return True  # Changed to True to allow startup even with database issues


def start_server():
    """Start the gunicorn server with uvicorn workers."""
    import subprocess
    
    # Get settings
    settings = get_settings()
    logger = get_logger("startup")
    
    # Get port from environment (Render sets this)
    port = int(os.getenv("PORT", 8000))
    host = "0.0.0.0"
    
    logger.info(f"🌐 Starting gunicorn server on {host}:{port}")
    logger.info("📚 API Documentation will be available at /docs")
    
    # Start the server using gunicorn with uvicorn workers
    cmd = [
        "gunicorn",
        "app.main:app",
        "-w", "4",  # 4 worker processes
        "-k", "uvicorn.workers.UvicornWorker",
        "--bind", f"{host}:{port}",
        "--timeout", "120",
        "--keep-alive", "5",
        "--max-requests", "1000",
        "--max-requests-jitter", "100",
        "--access-logfile", "-",
        "--error-logfile", "-",
        "--log-level", settings.log_level.lower()
    ]
    
    logger.info(f"🚀 Running: {' '.join(cmd)}")
    
    # Execute gunicorn
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"💥 Gunicorn failed to start: {e}")
        raise


def main():
    """Main entry point."""
    try:
        # Initialize application
        if not initialize_application():
            sys.exit(1)
        
        # Start server
        start_server()
        
    except KeyboardInterrupt:
        logger = get_logger("startup")
        logger.info("🛑 Server shutdown requested")
        sys.exit(0)
    except Exception as e:
        logger = get_logger("startup")
        logger.error(f"💥 Server startup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
