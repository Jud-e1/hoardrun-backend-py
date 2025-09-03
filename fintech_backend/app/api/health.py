"""
Health check endpoints for monitoring service status.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from datetime import datetime
import os
import sys
import psutil

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/")
async def basic_health_check():
    """
    Basic health check endpoint.
    
    Returns:
        dict: Basic service health status
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


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
                "database": "mocked"  # Will be updated when database is implemented
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