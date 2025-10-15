#!/usr/bin/env python3
"""
Main application entry point for Render deployment.
This file provides the ASGI application that Render expects.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the fintech_backend directory to Python path
fintech_backend_path = Path(__file__).parent / "fintech_backend"
sys.path.insert(0, str(fintech_backend_path))

# Import the FastAPI app
from app.main import app

# This is the ASGI application that Render will use
application = app

async def setup_database():
    """Setup database on startup if needed."""
    try:
        # Import here to avoid circular imports
        from app.database.config import check_database_connection

        print("🔍 Checking database connection...")
        if check_database_connection():
            print("✅ Database connection successful!")

            # Try to run migrations
            try:
                import subprocess
                result = subprocess.run(
                    ["alembic", "upgrade", "head"],
                    cwd=fintech_backend_path,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    print("✅ Database migrations completed!")
                else:
                    print(f"⚠️ Migration warning: {result.stderr}")
            except Exception as e:
                print(f"⚠️ Could not run migrations: {e}")

            # Try to create demo user
            try:
                from fintech_backend.setup_demo_user import check_and_create_demo_user
                await check_and_create_demo_user()
            except Exception as e:
                print(f"⚠️ Could not create demo user: {e}")
        else:
            print("⚠️ Database not immediately available, will retry per-request")
    except Exception as e:
        print(f"⚠️ Database setup error: {e}")

# Run database setup on import
try:
    asyncio.run(setup_database())
except Exception as e:
    print(f"⚠️ Startup database setup failed: {e}")

if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment (Render sets this)
    port = int(os.getenv("PORT", 8000))
    host = "0.0.0.0"
    
    print(f"🌐 Starting server on {host}:{port}")
    
    # Start the server
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=False,
        log_level="info",
        access_log=True
    )
