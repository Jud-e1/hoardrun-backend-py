"""
Paystack payment API endpoints.
"""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import JSONResponse

from ...auth.dependencies import get_current_user
from ...models.auth import User
from ...models.paystack import (
    InitializePaymentRequest,
    VerifyPaymentRequest,
    ListTransactionsRequest,
    PaymentInitializationResponse,
    PaymentVerificationResponse,
    TransactionListResponse,
    WebhookResponse,
    Currency,
    TransactionStatus
)
from ...services.paystack_service import get_paystack_service
from ...core.exceptions import ExternalServiceException, ValidationException
from ...config.logging import get_logger

logger = get_logger("paystack_api")

router = APIRouter(prefix="/paystack", tags=["Paystack Payments"])


@router.post("/initialize", response_model=PaymentInitializationResponse)
async def initialize_payment(
    request: InitializePaymentRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Initialize a new payment transaction with Paystack.
    
    This endpoint creates a new payment transaction and returns the authorization URL
    where the user should be redirected to complete the payment.
    """
    try:
        service = get_paystack_service()
        
        result = await service.initialize_payment(
            user_id=current_user.id,
            email=request.email,
            amount=request.amount,
            currency=request.currency,
            reference=request.reference,
            callback_url=request.callback_url,
            metadata=request.metadata,
            channels=request.channels
        )
        
        logger.info(f"Payment initialized for user {current_user.id}: {request.amount} {request.currency.value}")
        
        return result
        
    except ExternalServiceException as e:
        logger.error(f"Payment initialization failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in payment initialization: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/verify/{reference}", response_model=PaymentVerificationResponse)
async def verify_payment(
    reference: str,
    current_user: User = Depends(get_current_user)
):
    """
    Verify a payment transaction using its reference.
    
    This endpoint checks the status of a payment transaction with Paystack
    and returns the current status and details.
    """
    try:
        service = get_paystack_service()
        
        result = await service.verify_payment(reference)
        
        logger.info(f"Payment verified for user {current_user.id}: {reference}")
        
        return result
        
    except ExternalServiceException as e:
        logger.error(f"Payment verification failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in payment verification: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/transactions", response_model=TransactionListResponse)
async def list_transactions(
    per_page: int = 50,
    page: int = 1,
    customer: Optional[str] = None,
    status: Optional[TransactionStatus] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user)
):
    """
    List payment transactions with optional filters.
    
    This endpoint returns a paginated list of transactions from Paystack
    with optional filtering by customer, status, and date range.
    """
    try:
        service = get_paystack_service()
        
        result = await service.list_transactions(
            per_page=per_page,
            page=page,
            customer=customer,
            status=status,
            from_date=from_date,
            to_date=to_date
        )
        
        logger.info(f"Transactions listed for user {current_user.id}: page {page}")
        
        return result
        
    except ExternalServiceException as e:
        logger.error(f"Transaction listing failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in transaction listing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/webhook", response_model=WebhookResponse)
async def handle_webhook(
    request: Request,
    x_paystack_signature: str = Header(None)
):
    """
    Handle Paystack webhook notifications.
    
    This endpoint receives and processes webhook notifications from Paystack
    for events like successful payments, failed payments, etc.
    """
    try:
        # Get raw request body
        payload = await request.body()
        
        if not x_paystack_signature:
            raise ValidationException("Missing webhook signature")
        
        service = get_paystack_service()
        
        result = await service.process_webhook(payload, x_paystack_signature)
        
        logger.info(f"Webhook processed: {result.get('event')}")
        
        return WebhookResponse(
            success=True,
            message=result["message"],
            event_type=result["event"],
            transaction_reference=result.get("reference")
        )
        
    except ValidationException as e:
        logger.error(f"Webhook validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ExternalServiceException as e:
        logger.error(f"Webhook processing failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in webhook processing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/config")
async def get_paystack_config(
    current_user: User = Depends(get_current_user)
):
    """
    Get Paystack configuration for frontend integration.
    
    Returns the public key and other configuration needed by the frontend
    to integrate with Paystack.
    """
    try:
        from ...config.settings import get_settings
        settings = get_settings()
        
        return {
            "success": True,
            "message": "Paystack configuration retrieved",
            "data": {
                "public_key": settings.paystack_public_key,
                "environment": settings.paystack_environment,
                "supported_currencies": ["NGN", "USD", "GHS", "ZAR", "KES"],
                "supported_channels": [
                    "card", "bank", "ussd", "qr", 
                    "mobile_money", "bank_transfer"
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting Paystack config: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health")
async def paystack_health_check():
    """
    Health check endpoint for Paystack integration.
    
    Checks if the Paystack service is properly configured and accessible.
    """
    try:
        from ...config.settings import get_settings
        settings = get_settings()
        
        # Basic configuration check
        config_status = {
            "public_key_configured": bool(settings.paystack_public_key),
            "secret_key_configured": bool(settings.paystack_secret_key),
            "environment": settings.paystack_environment,
            "webhook_secret_configured": bool(settings.paystack_webhook_secret)
        }
        
        # Overall health status
        is_healthy = (
            config_status["public_key_configured"] and 
            config_status["secret_key_configured"]
        )
        
        return {
            "success": True,
            "message": "Paystack health check completed",
            "data": {
                "status": "healthy" if is_healthy else "unhealthy",
                "configuration": config_status,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Paystack health check failed: {e}")
        return {
            "success": False,
            "message": "Paystack health check failed",
            "data": {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        }
