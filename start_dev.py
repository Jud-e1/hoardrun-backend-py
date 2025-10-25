#!/usr/bin/env python3
"""
Development startup script for HoardRun backend.
"""

import os
import sys
import subprocess

# Add the fintech_backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fintech_backend'))

def main():
    """Start the development server."""
    print("🚀 Starting HoardRun Backend Development Server")
    print("=" * 50)
    
    # Change to the fintech_backend directory
    backend_dir = os.path.join(os.path.dirname(__file__), 'fintech_backend')
    os.chdir(backend_dir)
    
    # Set environment variables for development
    os.environ['PYTHONPATH'] = backend_dir
    
    try:
        # Test import first
        print("📦 Testing imports...")
        from ..config.settings import get_settings
        from ..database.config import check_database_connection, create_tables

        settings = get_settings()
        print(f"✅ Settings loaded successfully")
        print(f"   - App Name: {settings.app_name}")
        print(f"   - Environment: {settings.environment}")
        print(f"   - Database URL: {settings.database_url}")
        print(f"   - Debug Mode: {settings.debug}")

        # Create database tables
        print("\n🗄️  Creating database tables...")
        try:
            tables_created = create_tables()
            if tables_created:
                print("✅ Database tables created successfully!")
            else:
                print("❌ Failed to create database tables!")
        except Exception as table_error:
            print(f"❌ Database table creation error: {table_error}")

        # Test database connection
        print("\n🔍 Testing database connection...")
        try:
            is_healthy = check_database_connection()
            if is_healthy:
                print("✅ Database connection successful!")
            else:
                print("❌ Database connection failed!")
        except Exception as db_error:
            print(f"❌ Database connection error: {db_error}")
        
        # Start the server
        print(f"\n🌐 Starting server on http://{settings.host}:{settings.port}")
        print("📚 API Documentation: http://localhost:8000/docs")
        print("🔄 Press Ctrl+C to stop the server")
        print("-" * 50)
        
        # Use uvicorn to start the server
        import uvicorn
        uvicorn.run(
            "app.main:app",
            host=settings.host,
            port=settings.port,
            reload=settings.debug,
            log_level=settings.log_level.lower()
        )
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure all dependencies are installed:")
        print("pip install -r requirements.txt")
        return 1
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
