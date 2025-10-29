"""
Hybrid authentication middleware that supports both Python and Java JWT tokens.
"""

import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.auth import decode_access_token
from app.core.java_security_integration import decode_java_jwt, java_security_client
from app.database.config import get_db
from app.database.models import User
from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
security = HTTPBearer()


class HybridAuthService:
    """Service for handling both Python and Java authentication."""
    
    def __init__(self):
        self.settings = settings
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate token from either Python or Java auth system."""
        
        # Try Python JWT first
        try:
            payload = decode_access_token(token)
            if payload:
                logger.debug("Token validated by Python auth system")
                return {
                    "source": "python",
                    "user_id": payload.get("sub"),
                    "email": payload.get("email"),
                    "role": payload.get("role", "user"),
                    "is_active": payload.get("is_active", True),
                    "is_verified": payload.get("is_verified", True),
                    "payload": payload
                }
        except Exception as e:
            logger.debug(f"Python JWT validation failed: {e}")
        
        # Try Java JWT if Python fails and Java integration is enabled
        if self.settings.java_security_enabled:
            try:
                payload = decode_java_jwt(token)
                if payload:
                    logger.debug("Token validated by Java auth system")
                    return {
                        "source": "java",
                        "user_id": payload.get("sub"),
                        "username": payload.get("sub"),
                        "role": payload.get("role", "USER"),
                        "mfa_verified": payload.get("mfa_verified", False),
                        "token_use": payload.get("token_use", "access"),
                        "payload": payload
                    }
            except Exception as e:
                logger.debug(f"Java JWT validation failed: {e}")
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    async def get_user_from_token_data(self, token_data: Dict[str, Any], db: Session) -> Optional[User]:
        """Get user from database based on token data."""
        
        if token_data["source"] == "python":
            # For Python tokens, we have user_id
            user_id = token_data.get("user_id")
            if user_id:
                return db.query(User).filter(User.id == user_id).first()
        
        elif token_data["source"] == "java":
            # For Java tokens, we have username
            username = token_data.get("username")
            if username:
                # Try to find user by email (assuming username is email)
                user = db.query(User).filter(User.email == username).first()
                if not user:
                    # If not found by email, try by username if you have that field
                    # For now, we'll create a virtual user object
                    logger.info(f"Java user {username} not found in Python database")
                    return None
                return user
        
        return None


# Global instance
hybrid_auth_service = HybridAuthService()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Dependency to get current user from either Python or Java JWT token.
    Returns user data and token information.
    """
    
    token = credentials.credentials
    
    # Validate token (try both Python and Java)
    token_data = await hybrid_auth_service.validate_token(token)
    
    # Try to get user from database
    user = await hybrid_auth_service.get_user_from_token_data(token_data, db)
    
    # Audit log for Java integration
    if settings.java_security_enabled and token_data["source"] == "java":
        try:
            await java_security_client.audit_log(
                "API_ACCESS", 
                token_data.get("username", "unknown"),
                {"endpoint": "api_access", "source": "python_backend"}
            )
        except Exception as e:
            logger.warning(f"Failed to send audit log: {e}")
    
    return {
        "token_data": token_data,
        "user": user,
        "user_id": token_data.get("user_id"),
        "username": token_data.get("username"),
        "email": token_data.get("email"),
        "role": token_data.get("role"),
        "source": token_data["source"],
        "is_java_user": token_data["source"] == "java"
    }


async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Dependency to get current active user.
    Ensures user is active and verified.
    """
    
    token_data = current_user["token_data"]
    
    # Check if user is active (different logic for Python vs Java)
    if current_user["source"] == "python":
        if not token_data.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        if not token_data.get("is_verified", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email not verified"
            )
    
    elif current_user["source"] == "java":
        # Java tokens don't have is_active field, assume active if token is valid
        # You might want to add additional checks here
        pass
    
    return current_user


async def require_role(required_role: str):
    """
    Dependency factory to require specific role.
    """
    async def role_checker(current_user: Dict[str, Any] = Depends(get_current_active_user)):
        user_role = current_user.get("role", "").upper()
        required_role_upper = required_role.upper()
        
        # Role hierarchy: ADMIN > PREMIUM > USER
        role_hierarchy = {"USER": 1, "PREMIUM": 2, "ADMIN": 3}
        
        user_level = role_hierarchy.get(user_role, 0)
        required_level = role_hierarchy.get(required_role_upper, 999)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}"
            )
        
        return current_user
    
    return role_checker


# Convenience dependencies
require_admin = require_role("ADMIN")
require_premium = require_role("PREMIUM")
require_user = require_role("USER")
