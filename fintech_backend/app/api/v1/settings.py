"""
System settings API endpoints for managing system-wide configuration.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
import asyncio
from datetime import datetime

from ..models.system_settings import (
    SystemSettingsResponse, SystemSettingsUpdateRequest, SystemSettingsUpdateResponse
)
from ..services.system_settings_service import SystemSettingsService
from ..database.config import get_db
from ..core.exceptions import (
    ValidationException, AuthenticationException, AuthorizationException
)
from ..utils.response import success_response
from ..config.logging import get_logger
from ..core.auth import get_current_user

logger = get_logger(__name__)
security = HTTPBearer()

router = APIRouter(prefix="/settings", tags=["System Settings"])


def get_system_settings_service():
    """Dependency to get system settings service instance"""
    return SystemSettingsService()


@router.get(
    "",
    response_model=SystemSettingsResponse,
    summary="Get System Settings",
    description="Retrieve current system-wide settings (Admin only)"
)
async def get_system_settings(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    settings_service: SystemSettingsService = Depends(get_system_settings_service)
):
    """
    Get current system settings.

    Returns the current system-wide configuration settings.
    Requires admin privileges.
    """
    try:
        logger.info("API: Getting system settings")

        token = credentials.credentials

        # Verify admin access (mock implementation)
        current_user = await get_current_user(token, db)
        if current_user.get("role") != "admin":
            raise AuthorizationException("Admin access required")

        # Get system settings
        settings = await settings_service.get_system_settings(db)

        return success_response(
            data={"settings": settings},
            message="System settings retrieved successfully"
        )

    except AuthorizationException as e:
        logger.error(f"Authorization failed: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting system settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put(
    "",
    response_model=SystemSettingsUpdateResponse,
    summary="Update System Settings",
    description="Update system-wide settings (Admin only)"
)
async def update_system_settings(
    request: SystemSettingsUpdateRequest = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    settings_service: SystemSettingsService = Depends(get_system_settings_service)
):
    """
    Update system settings.

    Updates the system-wide configuration with provided values.
    Requires admin privileges.

    - **maintenance_mode**: Enable/disable maintenance mode
    - **max_users**: Maximum number of users allowed (1-1000000)
    - **email_notifications**: Enable/disable system email notifications
    - **backup_frequency**: Backup frequency (hourly, daily, weekly)
    """
    try:
        logger.info("API: Updating system settings")

        token = credentials.credentials

        # Verify admin access (mock implementation)
        current_user = await get_current_user(token, db)
        if current_user.get("role") != "admin":
            raise AuthorizationException("Admin access required")

        # Update system settings
        updated_settings = await settings_service.update_system_settings(
            request, current_user["user_id"], db
        )

        return success_response(
            data={"settings": updated_settings},
            message="System settings updated successfully"
        )

    except AuthorizationException as e:
        logger.error(f"Authorization failed: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating system settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/health",
    summary="System Settings Service Health Check",
    description="Check the health of system settings service"
)
async def system_settings_health_check():
    """
    Health check endpoint for system settings service.

    Returns the operational status of the system settings service.
    """
    try:
        # Simulate service checks
        await asyncio.sleep(0.01)  # Mock processing time

        return success_response(
            data={
                "service": "system_settings_service",
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            },
            message="System settings service is healthy"
        )

    except Exception as e:
        logger.error(f"System settings service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")


@router.get(
    "/maintenance-mode",
    summary="Check Maintenance Mode",
    description="Check if the system is currently in maintenance mode"
)
async def check_maintenance_mode(
    db: Session = Depends(get_db),
    settings_service: SystemSettingsService = Depends(get_system_settings_service)
):
    """
    Check maintenance mode status.

    Returns whether the system is currently in maintenance mode.
    This endpoint is publicly accessible.
    """
    try:
        logger.info("API: Checking maintenance mode status")

        is_maintenance = await settings_service.is_maintenance_mode_enabled(db)

        return success_response(
            data={"maintenance_mode": is_maintenance},
            message="Maintenance mode status retrieved"
        )

    except Exception as e:
        logger.error(f"Error checking maintenance mode: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
