"""
Authentication API endpoints for user registration, login, and profile management.
"""

from urllib.parse import quote

from ...config.settings import get_settings
from fastapi import APIRouter, HTTPException, Depends, status, Body, Request, Query, BackgroundTasks
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
import asyncio
from datetime import datetime, timedelta

from ...models.auth import (
    UserRegisterRequest, UserLoginRequest, UserResponse, TokenResponse, LoginResponse,
    PasswordResetRequest, PasswordChangeRequest, EmailVerificationRequest,
    UserProfileUpdateRequest, UserSettingsUpdateRequest
)
from ...services.auth_service import AuthService
from ...database.config import get_db
from ...core.exceptions import (
    ValidationException, AuthenticationException, AuthorizationException,
    UserNotFoundException, EmailAlreadyExistsException
)
from ...utils.response import success_response
from ...config.logging import get_logger

logger = get_logger(__name__)
security = HTTPBearer()

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_auth_service():
    """Dependency to get auth service instance"""
    return AuthService()


@router.post("/register", response_model=UserResponse)
async def register_user(
    request: UserRegisterRequest = Body(...),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Register a new user account.

    Creates a new user account with email verification.
    """
    try:
        logger.info(f"API: Registering new user with email {request.email}")

        user = await auth_service.register_user(request, db)

        return success_response(
            data={"user": user},
            message="User registered successfully. Please check your email for verification."
        )

    except EmailAlreadyExistsException as e:
        logger.error(f"Email already exists: {e}")
        raise HTTPException(status_code=409, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/login", response_model=LoginResponse)
async def login_user(
    request: UserLoginRequest = Body(...),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Authenticate user and return access tokens with user data.

    Validates credentials and returns JWT tokens and user profile for API access.
    """
    try:
        logger.info(f"API: Login attempt for email {request.email}")

        # The database connection will be tested when we try to use it
        # No need for explicit pre-check as it can cause unnecessary failures
        result = await auth_service.authenticate_user(request, db)

        return success_response(
            data=result,
            message="Login successful"
        )

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
        error_msg = str(e)
        logger.error(f"Error during login: {error_msg}")

        # Check if it's a database connection issue
        if any(keyword in error_msg.lower() for keyword in [
            "connection", "database", "postgresql", "ssl", "timeout", "refused"
        ]):
            logger.error("Database connection issue detected during login")
            raise HTTPException(
                status_code=503,
                detail="Database service temporarily unavailable. Please try again in a moment."
            )
        else:
            raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/logout", response_model=dict)
async def logout_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Logout user and invalidate tokens.

    Invalidates the current access token and refresh token.
    """
    try:
        logger.info("API: User logout")

        token = credentials.credentials
        result = await auth_service.logout_user(token, db)

        return success_response(
            data=result,
            message="Logout successful"
        )

    except AuthorizationException as e:
        logger.error(f"Authorization error: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Refresh access token using refresh token.

    Generates new access token from valid refresh token.
    """
    try:
        logger.info("API: Token refresh")

        result = await auth_service.refresh_access_token(refresh_token, db)

        return success_response(
            data=result,
            message="Token refreshed successfully"
        )

    except AuthenticationException as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error refreshing token: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/verify-email")
async def verify_email_get(
    token: str = Query(..., description="Email verification code"),
    email: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """A verification link: confirms the email and sends the person on to the app."""
    base = get_settings().app_url.rstrip("/")
    try:
        await auth_service.verify_email(token, db, email)
        return RedirectResponse(url=f"{base}/signin?verified=true", status_code=302)
    except ValidationException:
        target = f"{base}/check-email?email={quote(email)}&error=invalid" if email else f"{base}/signup"
        return RedirectResponse(url=target, status_code=302)


@router.post("/verify-email", response_model=dict)
async def verify_email_post(
    request: EmailVerificationRequest = Body(...),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Confirm an email with the 6-digit code sent to it (the code and the email together)."""
    try:
        result = await auth_service.verify_email(request.token, db, request.email)
        return success_response(data=result, message="Email verified successfully")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/resend-verification", response_model=dict)
async def resend_verification_email(
    email: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Send a new code. The answer never says whether the email has an account."""
    await auth_service.resend_verification_email(email.strip(), db)
    return success_response(data={"sent": True}, message="If that email is waiting to be confirmed, a new code is on its way.")


@router.post("/forgot-password", response_model=dict)
async def forgot_password(
    request: PasswordResetRequest = Body(...),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Email a reset link. The answer never says whether the email has an account."""
    await auth_service.request_password_reset(str(request.email), db)
    return success_response(data={"sent": True}, message="If there's an account for that email, a reset link is on its way.")


@router.get("/reset-password/check", response_model=dict)
async def check_reset_link(
    token: str = Query(..., min_length=10, max_length=200),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Whether a reset link still works, so the page can say so before a new password is typed."""
    return success_response(data={"valid": auth_service.reset_link_is_live(token, db)})


@router.post("/reset-password", response_model=dict)
async def reset_password(
    token: str = Body(..., min_length=10, max_length=200),
    new_password: str = Body(..., max_length=200),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Set a new password with a one-time reset link."""
    try:
        result = await auth_service.reset_password(token, new_password, db)
        return success_response(data=result, message="Password reset successfully")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Get current user profile.

    Returns authenticated user's profile information.
    """
    try:
        logger.info("API: Getting current user profile")

        token = credentials.credentials
        user = await auth_service.get_current_user(token, db)

        return success_response(
            data={"user": user},
            message="User profile retrieved successfully"
        )

    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    request: UserProfileUpdateRequest = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Update current user profile.

    Updates authenticated user's profile information.
    """
    try:
        logger.info("API: Updating current user profile")

        token = credentials.credentials
        user = await auth_service.update_user_profile(token, request, db)

        return success_response(
            data={"user": user},
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


@router.post("/change-password", response_model=dict)
async def change_password(
    request: PasswordChangeRequest = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Change user password.

    Updates user password after verifying current password.
    """
    try:
        logger.info("API: Changing user password")

        token = credentials.credentials
        result = await auth_service.change_password(token, request, db)

        return success_response(
            data=result,
            message="Password changed successfully"
        )

    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/welcome", response_model=dict)
async def welcome_endpoint(request: Request):
    """
    Welcome endpoint that logs request metadata and returns a welcome message.

    Returns a JSON response with a welcome message.
    Request metadata (method and path) is logged for monitoring.
    """
    try:
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

        return success_response(
            data={
                "message": "Welcome to the FastAPI Service!",
                "timestamp": datetime.now().isoformat()
            },
            message="Welcome message retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error in welcome endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=dict)
async def auth_health():
    """
    Health check endpoint for authentication service.

    Returns the operational status of the authentication service.
    """
    try:
        # Simulate service checks
        await asyncio.sleep(0.01)  # Mock processing time

        return success_response(
            data={
                "service": "authentication_service",
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            },
            message="Authentication service is healthy"
        )

    except Exception as e:
        logger.error(f"Auth service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
