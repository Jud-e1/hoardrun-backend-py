"""
WSGI entry point for Render deployment.
This provides compatibility with Render's default Python web service behavior.
"""

import os
import sys
from pathlib import Path

# Add the fintech_backend directory to Python path
fintech_backend_path = Path(__file__).parent / "fintech_backend"
sys.path.insert(0, str(fintech_backend_path))

# Import the FastAPI app
from app.main import app

# WSGI application for gunicorn
application = app

# Also provide these aliases in case Render is looking for them
wsgi = app
your_application = app
