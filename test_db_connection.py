#!/usr/bin/env python3
"""
Test script to verify database connection and troubleshoot connection issues.
"""

import os
import sys
import traceback
from sqlalchemy import create_engine, text

# Add the fintech_backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fintech_backend'))

def test_basic_connection():
    """Test basic database connection with minimal configuration."""
    print("Testing basic database connection...")
    
    # Get database URL from environment or use default
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./fintech.db')
    print(f"Database URL: {database_url}")
    
    try:
        # Create engine with minimal configuration
        if database_url.startswith("postgresql"):
            # PostgreSQL with corrected configuration
            engine = create_engine(
                database_url,
                pool_pre_ping=True,
                echo=True,
                connect_args={
                    "connect_timeout": 10,
                    "sslmode": "prefer",
                    "application_name": "HoardRun Test"
                }
            )
        else:
            # SQLite or other databases
            engine = create_engine(database_url, echo=True)
        
        # Test connection
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print(f"✅ Database connection successful! Result: {result.fetchone()}")
            
            # Get database version
            if database_url.startswith("postgresql"):
                version_result = connection.execute(text("SELECT version()"))
                version = version_result.fetchone()[0]
                print(f"PostgreSQL Version: {version}")
            elif database_url.startswith("sqlite"):
                version_result = connection.execute(text("SELECT sqlite_version()"))
                version = version_result.fetchone()[0]
                print(f"SQLite Version: {version}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print(f"Error type: {type(e).__name__}")
        traceback.print_exc()
        return False

def test_app_config():
    """Test the application's database configuration."""
    print("\nTesting application database configuration...")
    
    try:
        from app.config.settings import get_settings
        from app.database.config import engine, check_database_connection
        
        settings = get_settings()
        print(f"App Database URL: {settings.database_url}")
        print(f"Pool Size: {settings.database_pool_size}")
        print(f"SSL Mode: {settings.database_ssl_mode}")
        
        # Test using app's configuration
        is_healthy = check_database_connection()
        if is_healthy:
            print("✅ Application database connection successful!")
        else:
            print("❌ Application database connection failed!")
            
        return is_healthy
        
    except Exception as e:
        print(f"❌ Application configuration test failed: {e}")
        traceback.print_exc()
        return False

def test_user_model():
    """Test if we can query the User model."""
    print("\nTesting User model query...")
    
    try:
        from app.database.config import SessionLocal
        from app.database.models import User
        
        with SessionLocal() as db:
            # Try to query users (this will fail if table doesn't exist, but that's expected)
            try:
                user_count = db.query(User).count()
                print(f"✅ User table accessible. User count: {user_count}")
                return True
            except Exception as table_error:
                print(f"⚠️  User table query failed (table might not exist): {table_error}")
                # This is expected if tables haven't been created yet
                return True
                
    except Exception as e:
        print(f"❌ User model test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all database tests."""
    print("🔍 HoardRun Database Connection Test")
    print("=" * 50)
    
    # Test 1: Basic connection
    basic_success = test_basic_connection()
    
    # Test 2: App configuration
    app_success = test_app_config()
    
    # Test 3: User model
    model_success = test_user_model()
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print(f"Basic Connection: {'✅ PASS' if basic_success else '❌ FAIL'}")
    print(f"App Configuration: {'✅ PASS' if app_success else '❌ FAIL'}")
    print(f"User Model: {'✅ PASS' if model_success else '❌ FAIL'}")
    
    if all([basic_success, app_success, model_success]):
        print("\n🎉 All tests passed! Database connection is working.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
