"""
FastAPI application entry point for the fintech backend service.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from datetime import datetime
import os
import json
from contextlib import asynccontextmanager

from .config.settings import get_settings
from .config.logging import setup_logging, get_logger
from .core.middleware import setup_middleware
from .services.email_service import finish_request_emails
from .core.exception_handlers import register_exception_handlers
from .utils.json_encoder import CustomJSONEncoder
from .database.config import check_database_connection, create_tables, initialize_database
from .database.migrate import SchemaOutOfDate
from .api.health import router as health_router
from .api.v1.dashboard import router as dashboard_router
from .api.v1.auth import router as auth_router
from .api.v1.users import router as users_router
from .api.v1.beneficiaries import router as beneficiaries_router
from .api.v1.mobile_money import router as mobile_money_router
# Saved cards and their settings, stored in the database
from .api.v1.cards_store import router as payment_methods_router
from .api.v1.kyc import router as kyc_router
# Savings goals, fixed deposits and auto-save, stored in the database
from .api.v1.savings_store import router as savings_router
# Notifications stored per user and raised by real money events
from .api.v1.notifications_store import router as notifications_router
from .api.v1.smart_notifications import router as smart_notifications_router
from .api.v1.ai_guidance import router as ai_guidance_router
from .api.v1.market_data import router as market_data_router
from .api.v1.analytics import router as analytics_router
from .api.v1.support import router as support_router
from .api.v1.audit import router as audit_router
from .api.v1.cards import router as cards_router
from .api.v1.accounts import router as accounts_router
from .api.v1.transactions import router as transactions_router
from .api.v1.transfers import router as transfers_router
from .api.p2p import router as p2p_router
from .api.v1.investments import router as investments_router
from .api.v1.mastercard import router as mastercard_router
from .api.v1.collective_capital import router as collective_capital_router
from .api.v1.paystack import router as paystack_router
# Linked US banks through Plaid, and ACH to and from Hoardrun cash (stored in the database)
from .api.v1.bank_links import router as plaid_router
from .api.v1.opportunities import router as opportunities_router
from .api.v1.venture import router as venture_router
from .api.v1.circles import router as circles_router
from .api.v1.markets import router as markets_router
from .api.v1.cash import router as cash_router
from .api.v1.assistant import router as assistant_router
# Monthly budgets per spending category, measured against real transactions
from .api.v1.budgets_store import router as budgets_router
# Download your data, and close your account
from .api.v1.account_lifecycle import router as account_router
# Card deposits through Stripe Checkout (US)
from .api.v1.stripe_payments import router as stripe_router
# Sign in with Google (OpenID Connect, code flow with PKCE)
from .api.v1.google_auth import router as google_auth_router
# Sign in with Apple (web flow; required in the App Store next to Google sign-in)
from .api.v1.apple_auth import router as apple_auth_router
# Identity checks with Persona (hosted flow, signed webhook)
from .api.v1.identity import router as identity_router
# Hoardrun cards: virtual cards from Stripe Issuing, approved in real time against Hoardrun cash
from .api.v1.issued_cards import router as issuing_router
# Investing accounts at Alpaca (the broker behind ETF and crypto orders)
from .api.v1.brokerage import router as brokerage_router
from .auth.signing_key import is_production, jwt_secret
from .api.v1.settings import router as settings_router
from .api.websocket import router as websocket_router
from .api.admin.auth import router as admin_auth_router
from .api.admin.users import router as admin_users_router
from .api.admin.system import router as admin_system_router
from .api.admin.financial import router as admin_financial_router
from .api.admin.security import router as admin_security_router
from .api.admin.analytics import router as admin_analytics_router
from .api.public import router as public_router

# Get application settings
settings = get_settings()
# Stop here, before serving anything, if production has no real token-signing secret
jwt_secret()

# Setup logging
setup_logging(settings)
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("🚀 Starting Hoardrun Backend API...")

    try:
        # Check database connection (non-blocking)
        logger.info("🔍 Checking database connection...")
        db_connected = check_database_connection()

        # Production always checks the schema, so an unreachable database stops startup (the host retries)
        if db_connected or is_production():
            logger.info("✅ Database connection successful!")

            # Initialize database (create tables if they don't exist)
            logger.info("🗄️ Initializing database...")
            if initialize_database():
                logger.info("✅ Database initialization successful!")
            else:
                logger.warning("⚠️ Database initialization failed, but continuing startup...")
        else:
            logger.warning("⚠️ Database connection failed during startup, but continuing...")
            logger.info("💡 Database connection will be retried on first request")

        logger.info("🎉 Application startup completed successfully!")

    except SchemaOutOfDate:
        # Never serve new code against an old schema
        logger.error("💥 The database schema is behind this code; run the migrations first")
        raise
    except Exception as e:
        logger.error(f"💥 Application startup failed: {e}")
        logger.info("🔄 Continuing startup anyway - database issues will be handled per-request")

    yield

    # Shutdown
    logger.info("🛑 Shutting down Hoardrun Backend API...")
    logger.info("👋 Application shutdown completed!")


# Create FastAPI application instance with custom JSON encoder and lifespan
app = FastAPI(
    title=settings.app_name,
    description="A comprehensive fintech backend service providing REST API endpoints for financial operations",
    version=settings.app_version,
    # The API map stays private in production
    docs_url=None if is_production() else "/docs",
    redoc_url=None if is_production() else "/redoc",
    openapi_url=None if is_production() else "/openapi.json",
    debug=settings.debug,
    lifespan=lifespan
)

# Override the default JSON encoder
app.json_encoder = CustomJSONEncoder

# Setup middleware stack
setup_middleware(app, settings)
# Reply only after the emails a request started have gone out (Cloud Run slows a container once it replies)
app.middleware("http")(finish_request_emails)

# Register exception handlers
register_exception_handlers(app)

# Include routers
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(beneficiaries_router, prefix="/api/v1")
app.include_router(mobile_money_router, prefix="/api/v1")
app.include_router(payment_methods_router, prefix="/api/v1")
app.include_router(savings_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(smart_notifications_router, prefix="/api/v1")
app.include_router(ai_guidance_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(support_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(cards_router, prefix="/api/v1")
app.include_router(accounts_router, prefix="/api/v1")
app.include_router(transactions_router, prefix="/api/v1")
app.include_router(transfers_router, prefix="/api/v1")
app.include_router(investments_router, prefix="/api/v1")
app.include_router(paystack_router, prefix="/api/v1")
app.include_router(plaid_router, prefix="/api/v1")
app.include_router(opportunities_router, prefix="/api/v1")
app.include_router(venture_router, prefix="/api/v1")
app.include_router(circles_router, prefix="/api/v1")
app.include_router(markets_router, prefix="/api/v1")
app.include_router(cash_router, prefix="/api/v1")
app.include_router(assistant_router, prefix="/api/v1")
app.include_router(budgets_router, prefix="/api/v1")
app.include_router(account_router, prefix="/api/v1")
app.include_router(stripe_router, prefix="/api/v1")
app.include_router(google_auth_router, prefix="/api/v1")
app.include_router(apple_auth_router, prefix="/api/v1")
app.include_router(identity_router, prefix="/api/v1")
app.include_router(issuing_router, prefix="/api/v1")
app.include_router(brokerage_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
# Older routes the app no longer calls (mock KYC, P2P, Mastercard, collective capital, market data):
# kept for development, never served in production
if not is_production():
    app.include_router(kyc_router, prefix="/api/v1")
    app.include_router(p2p_router, prefix="/api/v1")
    app.include_router(mastercard_router, prefix="/api/v1")
    app.include_router(collective_capital_router, prefix="/api/v1")
    app.include_router(market_data_router, prefix="/api/v1")
app.include_router(websocket_router)
app.include_router(admin_auth_router, prefix="/api/v1/admin")
app.include_router(admin_users_router, prefix="/api/v1/admin")
app.include_router(admin_system_router, prefix="/api/v1/admin")
app.include_router(admin_financial_router, prefix="/api/v1/admin")
app.include_router(admin_security_router, prefix="/api/v1/admin")
app.include_router(admin_analytics_router, prefix="/api/v1/admin")
app.include_router(public_router, prefix="/api/public")


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


@app.get("/welcome", tags=["Root"])
async def welcome_endpoint(request: Request):
    """
    Welcome endpoint that logs request metadata and returns a welcome message.

    Returns a JSON response with a welcome message.
    Request metadata (method and path) is logged for monitoring.
    """
    # Log request metadata
    logger.info(
        f"Welcome endpoint accessed: {request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "user_agent": request.headers.get("user-agent", "unknown"),
            "client_ip": request.client.host if request.client else "unknown"
        }
    )

    return {
        "message": "Welcome to the FastAPI Service!",
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    # Get port from environment variable (for Render deployment) or default to 8000
    port = int(os.getenv("PORT", 8000))

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
