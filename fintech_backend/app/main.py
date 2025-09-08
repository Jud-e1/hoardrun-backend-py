"""
FastAPI application entry point for the fintech backend service.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
from datetime import datetime
import os
import json

from app.config.settings import get_settings
from app.config.logging import setup_logging, get_logger
from app.core.middleware import setup_middleware
from app.core.exception_handlers import register_exception_handlers
from app.utils.json_encoder import CustomJSONEncoder
from app.api.health import router as health_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.beneficiaries import router as beneficiaries_router
from app.api.v1.mobile_money import router as mobile_money_router
from app.api.v1.payment_methods import router as payment_methods_router
from app.api.v1.kyc import router as kyc_router
from app.api.v1.savings import router as savings_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.market_data import router as market_data_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.support import router as support_router
from app.api.v1.audit import router as audit_router
from app.api.v1.cards import router as cards_router
from app.api.v1.accounts import router as accounts_router
from app.api.v1.transactions import router as transactions_router
from app.api.v1.transfers import router as transfers_router
from app.api.p2p import router as p2p_router
from app.api.investments import router as investments_router
from app.api.websocket import router as websocket_router

# Get application settings
settings = get_settings()

# Setup logging
setup_logging(settings)
logger = get_logger("main")

# Create FastAPI application instance with custom JSON encoder
app = FastAPI(
    title=settings.app_name,
    description="A comprehensive fintech backend service providing REST API endpoints for financial operations",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    debug=settings.debug
)

# Override the default JSON encoder
app.json_encoder = CustomJSONEncoder

# Setup middleware stack
setup_middleware(app, settings)

# Register exception handlers
register_exception_handlers(app)

# Include routers
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(beneficiaries_router, prefix="/api/v1")
app.include_router(mobile_money_router, prefix="/api/v1")
app.include_router(payment_methods_router, prefix="/api/v1")
app.include_router(kyc_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(market_data_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(support_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(cards_router, prefix="/api/v1")
app.include_router(accounts_router, prefix="/api/v1")
app.include_router(transactions_router, prefix="/api/v1")
app.include_router(transfers_router, prefix="/api/v1")
app.include_router(p2p_router, prefix="/api/v1")
app.include_router(investments_router, prefix="/api/v1")
app.include_router(websocket_router)


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
