"""
Admin authentication API endpoints for admin login and profile management.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
import asyncio
from datetime import datetime, timedelta

from ..models.auth import (
    UserLoginRequest, LoginResponse, UserResponse, TokenResponse,
    UserRole
)
from ..services.auth_service import AuthService
from ..database.config import get_db
from ..core.exceptions import (
    ValidationException, AuthenticationException, AuthorizationException,
    UserNotFoundException
)
from ..utils.response import success_response
from ..config.logging import get_logger
from ..config.settings import get_settings

logger = get_logger(__name__)
security = HTTPBearer()

router = APIRouter(prefix="/auth", tags=["Admin Authentication"])


def get_auth_service():
    """Dependency to get auth service instance"""
    return AuthService()


async def authenticate_admin_user(
    request: UserLoginRequest,
    db: Session,
    auth_service: AuthService
) -> dict:
    try:
        logger.info(f"Admin authentication attempt for email {request.email}")

        # Direct admin authentication without email verification check
        user = await auth_service._get_user_by_email(request.email, db)

        if not user:
            raise AuthenticationException("Invalid credentials")

        if user.get("role") != UserRole.ADMIN.value:
            raise AuthorizationException("Access denied. Admin privileges required.")

        # Verify password
        if not auth_service._verify_password(request.password, user.get("password_hash", "")):
            raise AuthenticationException("Invalid credentials")

        # Generate tokens
        access_token = auth_service._create_access_token(user)
        refresh_token = auth_service._create_refresh_token(user)

        # Calculate token expiration
        settings = get_settings()
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        expires_at = datetime.utcnow() + access_token_expires

        # Create user profile
        from ..models.auth import UserProfile, UserStatus
        user_profile = UserProfile(
            id=user["id"],
            email=user["email"],
            first_name=user["first_name"],
            last_name=user["last_name"],
            phone_number=user.get("phone_number"),
            date_of_birth=user.get("date_of_birth"),
            country=user.get("country"),
            id_number=user.get("id_number"),
            status=UserStatus(user["status"]),
            role=UserRole(user["role"]),
            email_verified=user["email_verified"],
            created_at=user["created_at"],
            updated_at=user["updated_at"],
            last_login_at=user.get("last_login_at")
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": int(access_token_expires.total_seconds()),
            "expires_at": expires_at,
            "user": user_profile
        }
    except Exception as e:
        logger.error(f"Error during admin authentication: {e}")
        raise


@router.post("/login", response_model=LoginResponse)
async def admin_login(
    request: UserLoginRequest = Body(...),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Admin login endpoint.

    Authenticates admin users and returns access tokens with user data.
    Only users with ADMIN role can access this endpoint.
    """
    try:
        logger.info(f"API: Admin login attempt for email {request.email}")

        # Authenticate admin user
        result = await authenticate_admin_user(request, db, auth_service)

        return success_response(
            data=result,
            message="Admin login successful"
        )

    except AuthenticationException as e:
        logger.error(f"Admin authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except AuthorizationException as e:
        logger.error(f"Admin authorization failed: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except UserNotFoundException as e:
        logger.error(f"Admin user not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        logger.error(f"Admin validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error during admin login: {error_msg}")

        # Check if it's a database connection issue
        if any(keyword in error_msg.lower() for keyword in [
            "connection", "database", "postgresql", "ssl", "timeout", "refused"
        ]):
            logger.error("Database connection issue detected during admin login")
            raise HTTPException(
                status_code=503,
                detail="Database service temporarily unavailable. Please try again in a moment."
            )
        else:
            raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/logout", response_model=dict)
async def admin_logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Admin logout endpoint.

    Invalidates the current admin access token and refresh token.
    """
    try:
        logger.info("API: Admin logout")

        token = credentials.credentials
        result = await auth_service.logout_user(token, db)

        return success_response(
            data=result,
            message="Admin logout successful"
        )

    except AuthorizationException as e:
        logger.error(f"Admin authorization error: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error during admin logout: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/refresh", response_model=TokenResponse)
async def admin_refresh_token(
    refresh_token: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Admin token refresh endpoint.

    Generates new access token from valid refresh token for admin users.
    """
    try:
        logger.info("API: Admin token refresh")

        result = await auth_service.refresh_access_token(refresh_token, db)

        # Verify the refreshed token belongs to an admin user
        user = await auth_service.get_current_user(result.access_token, db)
        if user.role != UserRole.ADMIN:
            logger.warning("Non-admin user attempted admin token refresh")
            raise AuthorizationException("Access denied. Admin privileges required.")

        return success_response(
            data=result,
            message="Admin token refreshed successfully"
        )

    except AuthenticationException as e:
        logger.error(f"Admin token refresh failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except AuthorizationException as e:
        logger.error(f"Admin authorization failed: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error refreshing admin token: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/me", response_model=UserResponse)
async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Get current admin user profile.

    Returns authenticated admin user's profile information.
    """
    try:
        logger.info("API: Getting current admin user profile")

        token = credentials.credentials
        user = await auth_service.get_current_user(token, db)

        # Verify admin role
        if user.role != UserRole.ADMIN:
            logger.warning("Non-admin user attempted to access admin profile")
            raise AuthorizationException("Access denied. Admin privileges required.")

        return success_response(
            data={"user": user},
            message="Admin profile retrieved successfully"
        )

    except AuthenticationException as e:
        logger.error(f"Admin authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except AuthorizationException as e:
        logger.error(f"Admin authorization failed: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting current admin: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=dict)
async def admin_auth_health():
    """
    Health check endpoint for admin authentication service.

    Returns the operational status of the admin authentication service.
    """
    try:
        # Simulate service checks
        await asyncio.sleep(0.01)  # Mock processing time

        return success_response(
            data={
                "service": "admin_authentication_service",
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            },
            message="Admin authentication service is healthy"
        )

    except Exception as e:
        logger.error(f"Admin auth service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
