"""
Authentication and authorization utilities for FastAPI.
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from datetime import datetime, UTC

from ..config.settings import get_settings
from ..core.exceptions import AuthenticationException, TokenExpiredException, InvalidTokenException

# Security scheme for JWT tokens
security = HTTPBearer()
settings = get_settings()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Get the current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        dict: User information from token payload
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        # Extract token from credentials
        token = credentials.credentials
        
        # Decode JWT token
        payload = jwt.decode(
            token, 
            settings.jwt_secret_key, 
            algorithms=[settings.jwt_algorithm]
        )
        
        # Check token expiration
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp, UTC) < datetime.now(UTC):
            raise TokenExpiredException("access_token")
        
        # Extract user information
        user_id = payload.get("sub")
        if not user_id:
            raise InvalidTokenException("access_token")
        
        # Return user info (in a real app, you might fetch from database)
        return {
            "user_id": user_id,
            "email": payload.get("email"),
            "is_active": payload.get("is_active", True),
            "is_verified": payload.get("is_verified", False),
            "token_type": payload.get("token_type", "access")
        }
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (TokenExpiredException, InvalidTokenException) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Get the current active user.
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        dict: Active user information
        
    Raises:
        HTTPException: If user is not active
    """
    if not current_user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


async def get_current_verified_user(current_user: dict = Depends(get_current_active_user)) -> dict:
    """
    Get the current verified user.
    
    Args:
        current_user: Current active user from get_current_active_user dependency
        
    Returns:
        dict: Verified user information
        
    Raises:
        HTTPException: If user is not verified
    """
    if not current_user.get("is_verified", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not verified"
        )
    return current_user


def create_access_token(user_id: str, email: str, expires_delta: Optional[int] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        user_id: User identifier
        email: User email
        expires_delta: Token expiration time in seconds
        
    Returns:
        str: JWT access token
    """
    if expires_delta:
        expire = datetime.now(UTC).timestamp() + expires_delta
    else:
        expire = datetime.now(UTC).timestamp() + settings.jwt_access_token_expire_minutes * 60
    
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.now(UTC).timestamp(),
        "token_type": "access",
        "is_active": True,
        "is_verified": True
    }
    
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str, email: str) -> str:
    """
    Create a JWT refresh token.
    
    Args:
        user_id: User identifier
        email: User email
        
    Returns:
        str: JWT refresh token
    """
    expire = datetime.now(UTC).timestamp() + settings.jwt_refresh_token_expire_days * 24 * 60 * 60
    
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.now(UTC).timestamp(),
        "token_type": "refresh"
    }
    
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_token(token: str, token_type: str = "access") -> dict:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token to verify
        token_type: Expected token type (access or refresh)
        
    Returns:
        dict: Token payload
        
    Raises:
        InvalidTokenException: If token is invalid
        TokenExpiredException: If token is expired
    """
    try:
        payload = jwt.decode(
            token, 
            settings.jwt_secret_key, 
            algorithms=[settings.jwt_algorithm]
        )
        
        # Check token type
        if payload.get("token_type") != token_type:
            raise InvalidTokenException(f"Expected {token_type} token")
        
        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp, UTC) < datetime.now(UTC):
            raise TokenExpiredException(token_type)
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise TokenExpiredException(token_type)
    except jwt.InvalidTokenError:
        raise InvalidTokenException(token_type)


# Optional dependency for routes that don't require authentication
async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))) -> Optional[dict]:
    """
    Get current user if token is provided, otherwise return None.
    
    Args:
        credentials: Optional HTTP Bearer token credentials
        
    Returns:
        Optional[dict]: User information if authenticated, None otherwise
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
