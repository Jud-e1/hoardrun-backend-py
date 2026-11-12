"""
Vercel entry point: Vercel runs this file as a Python function and serves the FastAPI app.
vercel.json sends every path here, so the API's own routes (/health, /api/v1/...) work as usual.
See docs/vercel.md.
"""
import os
import sys

# Make the `app` package importable (this file lives in fintech_backend/api/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402,F401
