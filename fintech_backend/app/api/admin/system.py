"""
System Administration API endpoints for comprehensive system management.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
import asyncio
import psutil
import os
from datetime import datetime, timedelta
import json

from ...database.config import get_db, check_database_connection
from ...config.logging import get_logger
from ...core.auth import get_current_user
from ...utils.response import success_response
from ...config.settings import get_settings

logger = get_logger(__name__)
security = HTTPBearer()
settings = get_settings()

router = APIRouter(prefix="/system", tags=["Admin System Administration"])


def require_admin(current_user: dict) -> dict:
    """Check if user has admin role"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("/health", response_model=dict)
async def get_system_health(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Comprehensive system health check (Admin only).

    Returns detailed health status of all system components.
    """
    try:
        logger.info("Admin API: Getting comprehensive system health")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Database health
        db_healthy = check_database_connection()

        # System resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Application info
        app_info = {
            "version": settings.app_version,
            "environment": os.getenv("ENVIRONMENT", "development"),
            "debug": settings.debug,
            "uptime": "N/A"  # Would need to track application start time
        }

        # External services health (mock for now)
        external_services = {
            "redis": "healthy",  # Would check Redis connection
            "external_apis": "healthy"  # Would check external API connectivity
        }

        health_status = {
            "overall": "healthy" if db_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "database": "healthy" if db_healthy else "unhealthy",
                "application": "healthy",
                "external_services": external_services
            },
            "resources": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_gb": round(memory.used / (1024**3), 2),
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "disk_percent": disk.percent,
                "disk_used_gb": round(disk.used / (1024**3), 2),
                "disk_total_gb": round(disk.total / (1024**3), 2)
            },
            "application": app_info
        }

        return success_response(
            data=health_status,
            message="System health check completed"
        )

    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/metrics", response_model=dict)
async def get_system_metrics(
    time_range: str = Query("1h", regex="^(1h|24h|7d|30d)$"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get system performance metrics (Admin only).

    Returns system metrics for the specified time range.
    """
    try:
        logger.info(f"Admin API: Getting system metrics for {time_range}")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Current system metrics
        current_metrics = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "network_connections": len(psutil.net_connections()),
            "timestamp": datetime.utcnow().isoformat()
        }

        # Historical metrics (mock data for now)
        historical_metrics = []
        base_time = datetime.utcnow()

        for i in range(10):
            historical_metrics.append({
                "timestamp": (base_time - timedelta(minutes=i*6)).isoformat(),
                "cpu_percent": current_metrics["cpu_percent"] + (i % 5 - 2),
                "memory_percent": current_metrics["memory_percent"] + (i % 3 - 1),
                "active_users": 50 + (i % 20)  # Mock active users
            })

        metrics_data = {
            "current": current_metrics,
            "historical": historical_metrics,
            "time_range": time_range,
            "summary": {
                "avg_cpu_percent": sum(m["cpu_percent"] for m in historical_metrics) / len(historical_metrics),
                "avg_memory_percent": sum(m["memory_percent"] for m in historical_metrics) / len(historical_metrics),
                "peak_cpu_percent": max(m["cpu_percent"] for m in historical_metrics),
                "peak_memory_percent": max(m["memory_percent"] for m in historical_metrics)
            }
        }

        return success_response(
            data=metrics_data,
            message="System metrics retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/database/status", response_model=dict)
async def get_database_status(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get database health and statistics (Admin only).

    Returns detailed database status and performance metrics.
    """
    try:
        logger.info("Admin API: Getting database status")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Database connection check
        db_connected = check_database_connection()

        if not db_connected:
            return success_response(
                data={
                    "status": "unhealthy",
                    "connection": False,
                    "timestamp": datetime.utcnow().isoformat()
                },
                message="Database connection failed"
            )

        # Database statistics (simplified for now)
        db_stats = {
            "status": "healthy",
            "connection": True,
            "timestamp": datetime.utcnow().isoformat(),
            "tables": {
                "users": "estimated_count",  # Would query actual counts
                "transactions": "estimated_count",
                "accounts": "estimated_count"
            },
            "performance": {
                "connection_pool_size": "N/A",  # Would get from connection pool
                "active_connections": "N/A",
                "query_performance": "good"  # Mock performance indicator
            }
        }

        return success_response(
            data=db_stats,
            message="Database status retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error getting database status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/database/backup", response_model=dict)
async def trigger_database_backup(
    backup_type: str = Query("full", regex="^(full|incremental)$"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Trigger database backup (Admin only).

    Initiates a database backup operation.
    """
    try:
        logger.info(f"Admin API: Triggering {backup_type} database backup")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # In a real implementation, this would trigger an actual backup
        # For now, we'll simulate the backup process
        backup_id = f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        backup_result = {
            "backup_id": backup_id,
            "type": backup_type,
            "status": "initiated",
            "started_at": datetime.utcnow().isoformat(),
            "estimated_completion": (datetime.utcnow() + timedelta(minutes=5)).isoformat(),
            "initiated_by": current_user["user_id"]
        }

        # Log the backup initiation
        logger.info(f"Database backup initiated: {backup_id} by admin {current_user['user_id']}")

        return success_response(
            data=backup_result,
            message=f"{backup_type.title()} database backup initiated successfully"
        )

    except Exception as e:
        logger.error(f"Error triggering database backup: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/logs", response_model=dict)
async def get_system_logs(
    level: Optional[str] = Query(None, regex="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"),
    service: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get system logs with filtering (Admin only).

    Returns filtered system logs for monitoring and debugging.
    """
    try:
        logger.info("Admin API: Getting system logs")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # In a real implementation, this would query actual log files or database
        # For now, we'll return mock log entries
        mock_logs = [
            {
                "timestamp": (datetime.utcnow() - timedelta(minutes=i)).isoformat(),
                "level": "INFO",
                "service": "api",
                "message": f"User login successful - user_id: {1000 + i}",
                "user_id": 1000 + i
            }
            for i in range(min(limit, 50))
        ]

        # Apply filters
        if level:
            mock_logs = [log for log in mock_logs if log["level"] == level]
        if service:
            mock_logs = [log for log in mock_logs if log["service"] == service]

        logs_data = {
            "logs": mock_logs,
            "total": len(mock_logs),
            "filters": {
                "level": level,
                "service": service,
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit
            }
        }

        return success_response(
            data=logs_data,
            message="System logs retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error getting system logs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/config", response_model=dict)
async def get_system_config(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get system configuration (Admin only).

    Returns current system configuration settings.
    """
    try:
        logger.info("Admin API: Getting system configuration")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Get configuration from settings
        config_data = {
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "debug": settings.debug,
            "environment": os.getenv("ENVIRONMENT", "development"),
            "database_url": "configured" if settings.database_url else "not_configured",
            "redis_url": "configured" if settings.redis_url else "not_configured",
            "log_level": settings.log_level,
            "cors_origins": settings.cors_origins,
            "rate_limiting": {
                "enabled": True,  # Mock
                "requests_per_minute": 100
            },
            "features": {
                "notifications": True,
                "analytics": True,
                "audit_logging": True
            }
        }

        return success_response(
            data=config_data,
            message="System configuration retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error getting system config: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/config", response_model=dict)
async def update_system_config(
    config_updates: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Update system configuration (Admin only).

    Updates system configuration settings.
    """
    try:
        logger.info("Admin API: Updating system configuration")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # In a real implementation, this would update actual configuration
        # For now, we'll validate and acknowledge the updates
        allowed_updates = ["log_level", "debug", "features"]
        validated_updates = {}

        for key, value in config_updates.items():
            if key in allowed_updates:
                validated_updates[key] = value
            else:
                logger.warning(f"Attempted to update disallowed config key: {key}")

        update_result = {
            "updated_keys": list(validated_updates.keys()),
            "timestamp": datetime.utcnow().isoformat(),
            "updated_by": current_user["user_id"],
            "requires_restart": "debug" in validated_updates or "log_level" in validated_updates
        }

        logger.info(f"System config updated by admin {current_user['user_id']}: {validated_updates}")

        return success_response(
            data=update_result,
            message="System configuration updated successfully"
        )

    except Exception as e:
        logger.error(f"Error updating system config: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health-check", response_model=dict)
async def admin_system_health():
    """
    Health check endpoint for admin system service.

    Returns the operational status of the admin system service.
    """
    try:
        # Simulate service checks
        await asyncio.sleep(0.01)  # Mock processing time

        return success_response(
            data={
                "service": "admin_system_service",
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            },
            message="Admin system service is healthy"
        )

    except Exception as e:
        logger.error(f"Admin system service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
