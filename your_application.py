"""
This file exists because Render keeps looking for 'your_application' module.
We'll provide it and redirect to our actual application.
"""

import os
import sys
from pathlib import Path

# Add the fintech_backend directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "fintech_backend"))

# Import the FastAPI app
from app.main import app

# WSGI/ASGI application that Render is looking for
application = app
wsgi = app

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
