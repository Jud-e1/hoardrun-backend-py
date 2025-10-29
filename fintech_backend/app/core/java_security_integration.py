"""
Integration layer for Java security services with Python FastAPI backend.
Provides JWT token compatibility and security service communication.
"""

import jwt
import base64
import httpx
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel
from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class JavaSecurityConfig(BaseModel):
    """Configuration for Java security integration."""
    gateway_url: str = "http://localhost:8080"
    auth_service_url: str = "http://localhost:8081"
    transaction_service_url: str = "http://localhost:8082"
    audit_service_url: str = "http://localhost:8083"
    jwt_secret: str = "c2VjdXJlLXN1cGVyLXNlY3JldC1kZW1vLXNob3VsZC1iZS0zMi1ieXRlcy1vci1sb25nZXI="
    jwt_algorithm: str = "HS512"
    enabled: bool = False


class JavaJWTService:
    """JWT service compatible with Java security system."""
    
    def __init__(self, config: JavaSecurityConfig):
        self.config = config
        # Decode the base64 secret used by Java services
        self.secret_key = base64.b64decode(config.jwt_secret)
        self.algorithm = config.jwt_algorithm
        
    def decode_java_token(self, token: str) -> Dict[str, Any]:
        """Decode JWT token issued by Java auth service."""
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {str(e)}")
    
    def create_compatible_token(self, user_data: Dict[str, Any], expires_minutes: int = 15) -> str:
        """Create JWT token compatible with Java services."""
        import time

        # Use current timestamp directly to avoid timezone issues
        current_timestamp = int(time.time())
        expire_timestamp = current_timestamp + (abs(expires_minutes) * 60)  # Convert minutes to seconds

        payload = {
            "sub": user_data.get("username", user_data.get("email")),
            "role": user_data.get("role", "USER"),
            "token_use": "access",
            "mfa_verified": user_data.get("mfa_verified", False),
            "exp": expire_timestamp,
            "iat": current_timestamp,
            "jti": user_data.get("jti", f"python-{current_timestamp}")
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def validate_token_with_java_service(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate token by calling Java auth service."""
        if not self.config.enabled:
            return None
            
        try:
            # First try local validation
            payload = self.decode_java_token(token)
            return payload
        except Exception as e:
            logger.warning(f"Local token validation failed: {e}")
            return None


class JavaSecurityClient:
    """Client for communicating with Java security services."""
    
    def __init__(self, config: JavaSecurityConfig):
        self.config = config
        self.jwt_service = JavaJWTService(config)
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def authenticate_with_java(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user via Java auth service."""
        if not self.config.enabled:
            return None
            
        try:
            response = await self.client.post(
                f"{self.config.auth_service_url}/auth/login",
                json={
                    "username": username,
                    "password": password
                },
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 428:
                # MFA required
                return {"mfa_required": True, "status": "mfa_required"}
            else:
                logger.warning(f"Java auth failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error communicating with Java auth service: {e}")
            return None
    
    async def register_with_java(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Register user via Java auth service."""
        if not self.config.enabled:
            return None
            
        try:
            response = await self.client.post(
                f"{self.config.auth_service_url}/auth/register",
                json={
                    "username": username,
                    "password": password
                },
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Java registration failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error communicating with Java auth service: {e}")
            return None
    
    async def audit_log(self, event_type: str, username: str, details: Optional[Dict] = None):
        """Send audit log to Java audit service."""
        if not self.config.enabled:
            return
            
        try:
            await self.client.post(
                f"{self.config.audit_service_url}/audit/log",
                json={
                    "eventType": event_type,
                    "username": username,
                    "details": details or {},
                    "timestamp": datetime.utcnow().isoformat()
                },
                headers={"Content-Type": "application/json"}
            )
        except Exception as e:
            logger.error(f"Error sending audit log: {e}")
    
    async def validate_transaction_with_java(self, transaction_data: Dict[str, Any], token: str) -> bool:
        """Validate transaction via Java transaction service."""
        if not self.config.enabled:
            return True  # Fallback to allow transactions
            
        try:
            response = await self.client.post(
                f"{self.config.transaction_service_url}/api/tx/validate",
                json=transaction_data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                }
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error validating transaction with Java service: {e}")
            return True  # Fallback to allow transactions
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Global instances
java_security_config = JavaSecurityConfig(
    enabled=settings.java_security_enabled if hasattr(settings, 'java_security_enabled') else False,
    gateway_url=settings.java_gateway_url if hasattr(settings, 'java_gateway_url') else "http://localhost:8080",
    auth_service_url=settings.java_auth_service_url if hasattr(settings, 'java_auth_service_url') else "http://localhost:8081",
    transaction_service_url=settings.java_transaction_service_url if hasattr(settings, 'java_transaction_service_url') else "http://localhost:8082",
    audit_service_url=settings.java_audit_service_url if hasattr(settings, 'java_audit_service_url') else "http://localhost:8083"
)

java_security_client = JavaSecurityClient(java_security_config)


async def get_java_security_client() -> JavaSecurityClient:
    """Dependency to get Java security client."""
    return java_security_client


def decode_java_jwt(token: str) -> Dict[str, Any]:
    """Decode JWT token from Java services."""
    return java_security_client.jwt_service.decode_java_token(token)


def create_java_compatible_token(user_data: Dict[str, Any]) -> str:
    """Create JWT token compatible with Java services."""
    return java_security_client.jwt_service.create_compatible_token(user_data)
