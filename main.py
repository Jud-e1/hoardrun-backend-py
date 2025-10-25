import os
import sys
from pathlib import Path

# Add the fintech_backend directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "fintech_backend"))

# Import the FastAPI app
from fintech_backend.app.main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
