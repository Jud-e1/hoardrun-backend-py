"""
Admin User Management API endpoints for comprehensive user administration.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Body, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import asyncio
from datetime import datetime
from pydantic import BaseModel, EmailStr

from ..models.auth import (
    UserProfile, UserProfileUpdateRequest, UserResponse
)
from ..services.user_service import UserService
from ..database.config import get_db
from ..core.exceptions import (
    ValidationException, AuthenticationException, AuthorizationException,
    UserNotFoundException
)
from ..utils.response import success_response
from ..config.logging import get_logger
from ..core.auth import get_current_user

logger = get_logger(__name__)
security = HTTPBearer()

router = APIRouter(prefix="/users", tags=["Admin User Management"])


def get_user_service():
    """Dependency to get user service instance"""
    return UserService()


# Pydantic models for admin operations
class AdminUserCreateRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone_number: Optional[str] = None
    date_of_birth: Optional[str] = None
    country: Optional[str] = None
    bio: Optional[str] = None
    role: str = "user"
    is_active: bool = True
    email_verified: bool = False


class AdminUserUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    date_of_birth: Optional[str] = None
    country: Optional[str] = None
    bio: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    email_verified: Optional[bool] = None


class UserStatusUpdateRequest(BaseModel):
    is_active: bool
    reason: Optional[str] = None


class BulkUserActionRequest(BaseModel):
    user_ids: List[str]
    action: str  # 'activate', 'deactivate', 'delete', 'verify_email'
    reason: Optional[str] = None


class UserSearchFilters(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    email_verified: Optional[bool] = None
    country: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None


def require_admin(current_user: dict) -> dict:
    """Check if user has admin role"""
    if not current_user or current_user.get("role") != "admin":
        raise AuthorizationException("Admin access required")
    return current_user


@router.get("/", response_model=dict)
async def get_all_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    sort_by: str = Query("created_at", regex="^(created_at|email|first_name|last_name)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """
    Get all users with pagination, search, and filtering (Admin only).

    Returns paginated list of all users with optional search and sorting.
    """
    try:
        logger.info(f"Admin API: Getting users - page {page}, limit {limit}")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Get users with pagination and filters
        result = await user_service.get_all_users_paginated(
            db=db,
            page=page,
            limit=limit,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order
        )

        return success_response(
            data={
                "users": result["users"],
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": result["total"],
                    "pages": result["pages"]
                }
            },
            message="Users retrieved successfully"
        )

    except AuthorizationException as e:
        logger.error(f"Authorization failed: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/search", response_model=dict)
async def search_users(
    filters: UserSearchFilters = Depends(),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """
    Advanced search and filter users (Admin only).

    Search users by various criteria with pagination.
    """
    try:
        logger.info("Admin API: Advanced user search")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Convert filters to dict
        filter_dict = filters.dict(exclude_unset=True)

        result = await user_service.search_users_advanced(
            db=db,
            filters=filter_dict,
            page=page,
            limit=limit
        )

        return success_response(
            data={
                "users": result["users"],
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": result["total"],
                    "pages": result["pages"]
                },
                "filters": filter_dict
            },
            message="User search completed successfully"
        )

    except AuthorizationException as e:
        logger.error(f"Authorization failed: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching users: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{user_id}", response_model=dict)
async def get_user_by_id(
    user_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """
    Get specific user details by ID (Admin only).

    Returns complete user information including sensitive data.
    """
    try:
        logger.info(f"Admin API: Getting user {user_id}")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        user = await user_service.get_user_by_id_admin(user_id, db)

        return success_response(
            data={"user": user},
            message="User details retrieved successfully"
        )

    except AuthorizationException as e:
        logger.error(f"Authorization failed: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except UserNotFoundException as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/", response_model=dict)
async def create_user(
    user_data: AdminUserCreateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """
    Create a new user (Admin only).

    Creates a new user account with admin-specified parameters.
    """
    try:
        logger.info("Admin API: Creating new user")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Create user
        new_user = await user_service.create_user_admin(
            user_data.dict(),
            created_by=current_user["user_id"],
            db=db
        )

        return success_response(
            data={"user": new_user},
            message="User created successfully",
            status_code=201
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
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{user_id}", response_model=dict)
async def update_user(
    user_id: str,
    user_data: AdminUserUpdateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """
    Update user details (Admin only).

    Updates any user information including sensitive admin-only fields.
    """
    try:
        logger.info(f"Admin API: Updating user {user_id}")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Update user
        update_data = user_data.dict(exclude_unset=True)
        updated_user = await user_service.update_user_admin(
            user_id=user_id,
            update_data=update_data,
            updated_by=current_user["user_id"],
            db=db
        )

        return success_response(
            data={"user": updated_user},
            message="User updated successfully"
        )

    except AuthorizationException as e:
        logger.error(f"Authorization failed: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except UserNotFoundException as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{user_id}/status", response_model=dict)
async def update_user_status(
    user_id: str,
    status_data: UserStatusUpdateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """
    Update user active status (Admin only).

    Activate or deactivate a user account.
    """
    try:
        logger.info(f"Admin API: Updating user {user_id} status to {status_data.is_active}")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Update user status
        updated_user = await user_service.update_user_status_admin(
            user_id=user_id,
            is_active=status_data.is_active,
            reason=status_data.reason,
            updated_by=current_user["user_id"],
            db=db
        )

        return success_response(
            data={"user": updated_user},
            message=f"User {'activated' if status_data.is_active else 'deactivated'} successfully"
        )

    except AuthorizationException as e:
        logger.error(f"Authorization failed: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except UserNotFoundException as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating user {user_id} status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{user_id}", response_model=dict)
async def delete_user(
    user_id: str,
    reason: Optional[str] = Query(None, description="Reason for deletion"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """
    Delete user account (Admin only).

    Permanently deletes a user account. This action cannot be undone.
    """
    try:
        logger.info(f"Admin API: Deleting user {user_id}")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Prevent admin from deleting themselves
        if user_id == current_user["user_id"]:
            raise ValidationException("Cannot delete your own admin account")

        # Delete user
        result = await user_service.delete_user_admin(
            user_id=user_id,
            reason=reason,
            deleted_by=current_user["user_id"],
            db=db
        )

        return success_response(
            data=result,
            message="User deleted successfully"
        )

    except AuthorizationException as e:
        logger.error(f"Authorization failed: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except UserNotFoundException as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/bulk-action", response_model=dict)
async def bulk_user_action(
    action_data: BulkUserActionRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """
    Perform bulk actions on multiple users (Admin only).

    Actions: activate, deactivate, delete, verify_email
    """
    try:
        logger.info(f"Admin API: Bulk {action_data.action} on {len(action_data.user_ids)} users")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Validate action
        valid_actions = ['activate', 'deactivate', 'delete', 'verify_email']
        if action_data.action not in valid_actions:
            raise ValidationException(f"Invalid action. Must be one of: {', '.join(valid_actions)}")

        # Prevent admin from bulk deleting themselves
        if action_data.action == 'delete' and current_user["user_id"] in action_data.user_ids:
            raise ValidationException("Cannot include your own admin account in bulk delete")

        # Perform bulk action
        result = await user_service.bulk_user_action_admin(
            user_ids=action_data.user_ids,
            action=action_data.action,
            reason=action_data.reason,
            performed_by=current_user["user_id"],
            db=db
        )

        return success_response(
            data=result,
            message=f"Bulk {action_data.action} completed successfully"
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
        logger.error(f"Error performing bulk action: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/overview", response_model=dict)
async def get_user_statistics(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
):
    """
    Get user statistics overview (Admin only).

    Returns comprehensive statistics about user accounts.
    """
    try:
        logger.info("Admin API: Getting user statistics")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        stats = await user_service.get_user_statistics_admin(db)

        return success_response(
            data={"statistics": stats},
            message="User statistics retrieved successfully"
        )

    except AuthorizationException as e:
        logger.error(f"Authorization failed: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting user statistics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=dict)
async def admin_users_health():
    """
    Health check endpoint for admin users service.

    Returns the operational status of the admin users service.
    """
    try:
        # Simulate service checks
        await asyncio.sleep(0.01)  # Mock processing time

        return success_response(
            data={
                "service": "admin_users_service",
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            },
            message="Admin users service is healthy"
        )

    except Exception as e:
        logger.error(f"Admin users service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
