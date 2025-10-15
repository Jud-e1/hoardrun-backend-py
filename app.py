#!/usr/bin/env python3
"""
Main application entry point for Render deployment.
This file provides the ASGI application that Render expects.
"""

import os
import sys
from pathlib import Path

# Add the fintech_backend directory to Python path
fintech_backend_path = Path(__file__).parent / "fintech_backend"
sys.path.insert(0, str(fintech_backend_path))

# Import the FastAPI app
from app.main import app

# This is the ASGI application that Render will use
application = app

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
