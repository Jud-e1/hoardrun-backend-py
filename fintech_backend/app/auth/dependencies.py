"""
Authentication dependencies for FastAPI endpoints.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from sqlalchemy.orm import Session

from ..auth.jwt_handler import JWTHandler
from ..database.config import get_db
from ..repositories.database_repository import UserRepository

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    Extract and validate user ID from JWT token.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        str: User ID from the token
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    token = credentials.credentials
    return JWTHandler.get_user_id_from_token(token)


async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Get the current authenticated user from the database.
    
    Args:
        user_id: User ID from JWT token
        db: Database session
        
    Returns:
        User: Current authenticated user
        
    Raises:
        HTTPException: If user not found
    """
    user_repo = UserRepository(db)
    user = user_repo.get_user_by_id(user_id)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_optional_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[str]:
    """
    Extract user ID from JWT token if present (optional authentication).
    
    Args:
        credentials: Optional HTTP Bearer token credentials
        
    Returns:
        Optional[str]: User ID from token if present, None otherwise
    """
    if credentials is None:
        return None
    
    try:
        token = credentials.credentials
        return JWTHandler.get_user_id_from_token(token)
    except HTTPException:
        return None
