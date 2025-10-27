"""
User management API endpoints for profile and settings management.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Body, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, List
import asyncio
from datetime import datetime

from ..models.auth import (
    UserProfile, UserProfileUpdateRequest, UserSettingsUpdateRequest,
    UserSettings, UserResponse
)
from ..services.user_service import UserService
from ..database.config import get_db
from ..core.exceptions import (
    ValidationException, AuthenticationException, AuthorizationException,
    UserNotFoundException
)
from ..utils.response import success_response
from ..config.logging import get_logger

logger = get_logger(__name__)
security = HTTPBearer()

router = APIRouter(prefix="/users", tags=["User Management"])


def get_user_service():
    """Dependency to get user service instance"""
    return UserService()


@router.get("/", response_model=dict)
async def get_users(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """
    Get all users (Admin endpoint).

    Returns a list of all users in the system.
    """
    try:
        logger.info("API: Getting all users")

        token = credentials.credentials
        # TODO: Add admin role verification here
        users = await user_service.get_all_users(db)

        return success_response(
            data={"users": users},
            message="Users retrieved successfully"
        )

    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/profile", response_model=UserResponse)
async def get_user_profile(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """
    Get user profile information.
    
    Returns the authenticated user's complete profile.
    """
    try:
        logger.info("API: Getting user profile")
        
        token = credentials.credentials
        profile = await user_service.get_user_profile(token, db)
        
        return success_response(
            data={"user": profile},
            message="User profile retrieved successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/profile", response_model=UserResponse)
async def update_user_profile(
    request: UserProfileUpdateRequest = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """
    Update user profile information.
    
    Updates the authenticated user's profile with provided data.
    """
    try:
        logger.info("API: Updating user profile")
        
        token = credentials.credentials
        profile = await user_service.update_user_profile(token, request, db)
        
        return success_response(
            data={"user": profile},
            message="User profile updated successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/upload-avatar", response_model=dict)
async def upload_avatar(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """
    Upload user profile picture.
    
    Uploads and sets a new profile picture for the authenticated user.
    """
    try:
        logger.info(f"API: Uploading avatar - {file.filename}")
        
        token = credentials.credentials
        result = await user_service.upload_avatar(token, file, db)
        
        return success_response(
            data=result,
            message="Avatar uploaded successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading avatar: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/settings", response_model=dict)
async def get_user_settings(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """
    Get user settings.
    
    Returns the authenticated user's settings and preferences.
    """
    try:
        logger.info("API: Getting user settings")
        
        token = credentials.credentials
        settings = await user_service.get_user_settings(token, db)
        
        return success_response(
            data={"settings": settings},
            message="User settings retrieved successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting user settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/settings", response_model=dict)
async def update_user_settings(
    request: UserSettingsUpdateRequest = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """
    Update user settings.
    
    Updates the authenticated user's settings and preferences.
    """
    try:
        logger.info("API: Updating user settings")
        
        token = credentials.credentials
        settings = await user_service.update_user_settings(token, request, db)
        
        return success_response(
            data={"settings": settings},
            message="User settings updated successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating user settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/account", response_model=dict)
async def delete_user_account(
    password: str = Body(..., embed=True),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """
    Delete user account.
    
    Permanently deletes the authenticated user's account after password verification.
    """
    try:
        logger.info("API: Deleting user account")
        
        token = credentials.credentials
        result = await user_service.delete_user_account(token, password, db)
        
        return success_response(
            data=result,
            message="User account deleted successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting user account: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=dict)
async def user_service_health():
    """
    Health check endpoint for user service.
    
    Returns the operational status of the user management service.
    """
    try:
        # Simulate service checks
        await asyncio.sleep(0.01)  # Mock processing time
        
        return success_response(
            data={
                "service": "user_management_service",
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            },
            message="User management service is healthy"
        )
        
    except Exception as e:
        logger.error(f"User service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
