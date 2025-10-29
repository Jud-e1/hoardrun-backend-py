"""
API endpoints for Java security integration.
Provides endpoints to interact with Java security services.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Body
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging

from app.core.java_security_integration import get_java_security_client, JavaSecurityClient
from app.middleware.hybrid_auth import get_current_user, get_current_active_user
from app.core.response import success_response, error_response
from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/java-security", tags=["Java Security Integration"])


class JavaLoginRequest(BaseModel):
    """Request model for Java authentication."""
    username: str
    password: str
    mfa_code: Optional[str] = None


class JavaRegisterRequest(BaseModel):
    """Request model for Java registration."""
    username: str
    password: str


class TransactionValidationRequest(BaseModel):
    """Request model for transaction validation."""
    amount: float
    currency: str
    recipient: str
    transaction_type: str
    metadata: Optional[Dict[str, Any]] = None


@router.get("/status")
async def get_java_security_status():
    """
    Get the status of Java security integration.
    """
    return success_response(
        data={
            "enabled": settings.java_security_enabled,
            "gateway_url": settings.java_gateway_url,
            "auth_service_url": settings.java_auth_service_url,
            "transaction_service_url": settings.java_transaction_service_url,
            "audit_service_url": settings.java_audit_service_url,
            "integration_active": settings.java_security_enabled
        },
        message="Java security integration status"
    )


@router.post("/auth/login")
async def java_login(
    request: JavaLoginRequest = Body(...),
    java_client: JavaSecurityClient = Depends(get_java_security_client)
):
    """
    Authenticate user via Java auth service.
    """
    if not settings.java_security_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Java security integration is disabled"
        )
    
    try:
        result = await java_client.authenticate_with_java(
            request.username, 
            request.password
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        if result.get("mfa_required"):
            return success_response(
                data={"mfa_required": True},
                message="MFA verification required"
            )
        
        return success_response(
            data=result,
            message="Authentication successful"
        )
        
    except Exception as e:
        logger.error(f"Java authentication error: {e}")
        return error_response(
            message="Authentication failed",
            details=str(e)
        )


@router.post("/auth/register")
async def java_register(
    request: JavaRegisterRequest = Body(...),
    java_client: JavaSecurityClient = Depends(get_java_security_client)
):
    """
    Register user via Java auth service.
    """
    if not settings.java_security_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Java security integration is disabled"
        )
    
    try:
        result = await java_client.register_with_java(
            request.username, 
            request.password
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration failed"
            )
        
        return success_response(
            data=result,
            message="Registration successful"
        )
        
    except Exception as e:
        logger.error(f"Java registration error: {e}")
        return error_response(
            message="Registration failed",
            details=str(e)
        )


@router.post("/transaction/validate")
async def validate_transaction(
    request: TransactionValidationRequest = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    java_client: JavaSecurityClient = Depends(get_java_security_client)
):
    """
    Validate transaction via Java transaction service.
    """
    if not settings.java_security_enabled:
        # If Java integration is disabled, allow all transactions
        return success_response(
            data={"valid": True, "source": "python_fallback"},
            message="Transaction validation passed (Java integration disabled)"
        )
    
    try:
        # Get the token from current user context
        token_data = current_user.get("token_data", {})
        
        # For Java users, we need to pass the original token
        if current_user.get("source") == "java":
            # We would need to store the original token, for now use a placeholder
            token = "java-token-placeholder"
        else:
            # For Python users, create a compatible token
            from app.core.java_security_integration import create_java_compatible_token
            token = create_java_compatible_token({
                "username": current_user.get("email"),
                "role": current_user.get("role", "USER")
            })
        
        transaction_data = {
            "amount": request.amount,
            "currency": request.currency,
            "recipient": request.recipient,
            "transactionType": request.transaction_type,
            "metadata": request.metadata or {},
            "userId": current_user.get("user_id") or current_user.get("username")
        }
        
        is_valid = await java_client.validate_transaction_with_java(
            transaction_data, 
            token
        )
        
        return success_response(
            data={
                "valid": is_valid,
                "source": "java_transaction_service",
                "transaction_data": transaction_data
            },
            message="Transaction validation completed"
        )
        
    except Exception as e:
        logger.error(f"Transaction validation error: {e}")
        # Fallback to allow transaction if validation service fails
        return success_response(
            data={"valid": True, "source": "fallback_on_error"},
            message="Transaction validation failed, allowing transaction as fallback"
        )


@router.post("/audit/log")
async def send_audit_log(
    event_type: str = Body(...),
    details: Optional[Dict[str, Any]] = Body(None),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    java_client: JavaSecurityClient = Depends(get_java_security_client)
):
    """
    Send audit log to Java audit service.
    """
    if not settings.java_security_enabled:
        return success_response(
            data={"logged": False},
            message="Java security integration is disabled"
        )
    
    try:
        username = current_user.get("username") or current_user.get("email")
        
        await java_client.audit_log(
            event_type=event_type,
            username=username,
            details=details
        )
        
        return success_response(
            data={"logged": True},
            message="Audit log sent successfully"
        )
        
    except Exception as e:
        logger.error(f"Audit logging error: {e}")
        return error_response(
            message="Failed to send audit log",
            details=str(e)
        )


@router.get("/health")
async def java_security_health(
    java_client: JavaSecurityClient = Depends(get_java_security_client)
):
    """
    Check health of Java security services.
    """
    if not settings.java_security_enabled:
        return success_response(
            data={
                "status": "disabled",
                "services": {
                    "gateway": "disabled",
                    "auth": "disabled", 
                    "transaction": "disabled",
                    "audit": "disabled"
                }
            },
            message="Java security integration is disabled"
        )
    
    # TODO: Implement actual health checks for each service
    # For now, return basic status
    return success_response(
        data={
            "status": "enabled",
            "services": {
                "gateway": "unknown",
                "auth": "unknown",
                "transaction": "unknown", 
                "audit": "unknown"
            },
            "configuration": {
                "gateway_url": settings.java_gateway_url,
                "auth_service_url": settings.java_auth_service_url,
                "transaction_service_url": settings.java_transaction_service_url,
                "audit_service_url": settings.java_audit_service_url
            }
        },
        message="Java security services status"
    )
