"""
JWT token handling for authentication and authorization.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from jwt import InvalidTokenError as JWTError
from fastapi import HTTPException, status
import os

from . import passwords
from .signing_key import jwt_secret

# JWT settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


class JWTHandler:
    """JWT token handler for authentication operations."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return passwords.hash_password(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Check a password against its bcrypt hash. Anything else never matches."""
        return passwords.verify_password(plain_password, hashed_password)

    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, jwt_secret(), algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: Dict[str, Any]) -> str:
        """Create a JWT refresh token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, jwt_secret(), algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, jwt_secret(), algorithms=[ALGORITHM])
            
            # Check token type
            # Login tokens carry "token_type"; refresh tokens carry "type"
            if (payload.get("type") or payload.get("token_type")) != token_type:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Check expiration
            exp = payload.get("exp")
            if exp is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token missing expiration",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            if datetime.utcnow() > datetime.utcfromtimestamp(exp):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            return payload
            
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    @staticmethod
    def get_user_id_from_token(token: str) -> str:
        """Extract user ID from JWT token."""
        payload = JWTHandler.verify_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing user ID",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user_id
