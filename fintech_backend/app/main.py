"""
FastAPI application entry point for the fintech backend service.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
from datetime import datetime
import os

from app.config.settings import get_settings
from app.config.logging import setup_logging, get_logger
from app.core.middleware import setup_middleware
from app.core.exception_handlers import register_exception_handlers
from app.api.health import router as health_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.cards import router as cards_router
from app.api.v1.accounts import router as accounts_router
from app.api.v1.transactions import router as transactions_router
from app.api.v1.transfers import router as transfers_router
from app.api.p2p import router as p2p_router
from app.api.investments import router as investments_router

# Get application settings
settings = get_settings()

# Setup logging
setup_logging(settings)
logger = get_logger("main")

# Create FastAPI application instance
app = FastAPI(
    title=settings.app_name,
    description="A comprehensive fintech backend service providing REST API endpoints for financial operations",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    debug=settings.debug
)

# Setup middleware stack
setup_middleware(app, settings)

# Register exception handlers
register_exception_handlers(app)

# Include routers
app.include_router(health_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(cards_router, prefix="/api/v1")
app.include_router(accounts_router, prefix="/api/v1")
app.include_router(transactions_router, prefix="/api/v1")
app.include_router(transfers_router, prefix="/api/v1")
app.include_router(p2p_router, prefix="/api/v1")
app.include_router(investments_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint to verify service availability.
    
    Returns:
        dict: Service health status and metadata
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "fintech-backend",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "environment": os.getenv("ENVIRONMENT", "development")
        }
    )


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint providing basic API information.
    
    Returns:
        dict: API welcome message and basic information
    """
    return {
        "message": "Welcome to Fintech Backend API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )