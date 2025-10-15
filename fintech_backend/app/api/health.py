"""
Health check endpoints for monitoring service status.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from datetime import datetime
import os
import sys
import psutil
from app.database.config import check_database_connection, get_database_info
from app.config.settings import get_settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/")
async def basic_health_check():
    """
    Basic health check endpoint with database connectivity.
    This is used by Render to determine if the service is ready.

    Returns:
        dict: Basic service health status including database
    """
    try:
        # Check database connection
        db_healthy = check_database_connection()

        # Always return 200 for basic health check - service is running
        # Database issues are reported but don't fail the health check
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "database": "connected" if db_healthy else "disconnected",
                "database_healthy": db_healthy,
                "timestamp": datetime.utcnow().isoformat(),
                "service": "hoardrun-backend",
                "message": "Service is running" + (" with database" if db_healthy else " (database connection issues)")
            }
        )
    except Exception as e:
        # Even with exceptions, return 200 - the service itself is healthy
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "database": "error",
                "database_healthy": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
                "service": "hoardrun-backend",
                "message": "Service is running (database connection error)"
            }
        )


@router.get("/detailed")
async def detailed_health_check():
    """
    Detailed health check with system information.
    
    Returns:
        dict: Comprehensive health status including system metrics
    """
    try:
        # Get system information
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "status": "healthy",
            "service": "fintech-backend",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "environment": os.getenv("ENVIRONMENT", "development"),
            "system": {
                "python_version": sys.version,
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent
                },
                "disk": {
                    "total": disk.total,
                    "free": disk.free,
                    "percent": (disk.used / disk.total) * 100
                }
            },
            "dependencies": {
                "external_services": "mocked",  # Will be updated when external services are implemented
                "database": check_database_connection()
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/database")
async def database_health_check():
    """
    Database-specific health check endpoint.

    Returns:
        dict: Database connection status and information
    """
    try:
        db_info = get_database_info()

        if db_info.get("connection_healthy", False):
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "database": db_info
            }
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "database": db_info
                }
            )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/readiness")
async def readiness_check():
    """
    Readiness check endpoint for Kubernetes/container orchestration.
    Checks if the service is ready to accept traffic.

    Returns:
        dict: Service readiness status
    """
    try:
        # Check database connection
        db_healthy = check_database_connection()

        if db_healthy:
            return {
                "status": "ready",
                "timestamp": datetime.utcnow().isoformat(),
                "checks": {
                    "database": "healthy"
                }
            }
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "timestamp": datetime.utcnow().isoformat(),
                    "checks": {
                        "database": "unhealthy"
                    }
                }
            )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/liveness")
async def liveness_check():
    """
    Liveness check endpoint for Kubernetes/container orchestration.
    Checks if the service is alive and should not be restarted.

    Returns:
        dict: Service liveness status
    """
    try:
        # Basic liveness check - just ensure the service is responding
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": datetime.utcnow().isoformat()  # In a real app, this would be actual uptime
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "dead",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )