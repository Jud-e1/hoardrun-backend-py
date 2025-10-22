"""
Service layer for Paystack payment operations.
"""
import uuid
from decimal import Decimal
from datetime import datetime, UTC
from typing import Dict, List, Optional, Any

from ..external.paystack_client import get_paystack_client, PaystackChannel
from ..models.paystack import (
    InitializePaymentRequest,
    PaymentInitializationResponse,
    PaymentVerificationResponse,
    TransactionListResponse,
    PaystackTransaction,
    TransactionStatus,
    Currency
)
from ..config.logging import get_logger
from ..core.exceptions import ExternalServiceException, ValidationException

logger = get_logger("paystack_service")


class PaystackService:
    """Service for handling Paystack payment operations."""
    
    def __init__(self):
        self.client = get_paystack_client()
    
    async def initialize_payment(
        self,
        user_id: int,
        email: str,
        amount: Decimal,
        currency: Currency = Currency.GHS,
        reference: Optional[str] = None,
        callback_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        channels: Optional[List[PaystackChannel]] = None
    ) -> PaymentInitializationResponse:
        """Initialize a new payment transaction."""
        try:
            # Generate reference if not provided
            if not reference:
                reference = f"hoardrun_{user_id}_{uuid.uuid4().hex[:8]}"
            
            # Convert amount to kobo (smallest currency unit)
            amount_kobo = int(amount * 100)
            
            # Add user_id to metadata
            if not metadata:
                metadata = {}
            metadata["user_id"] = user_id
            metadata["initiated_at"] = datetime.now(UTC).isoformat()
            
            logger.info(f"Initializing payment for user {user_id}: {amount} {currency.value}")
            
            # Initialize transaction with Paystack
            result = await self.client.initialize_transaction(
                email=email,
                amount=amount_kobo,
                currency=currency.value,
                reference=reference,
                callback_url=callback_url,
                metadata=metadata,
                channels=channels
            )
            
            # TODO: Store transaction in database
            # await self._store_transaction(user_id, reference, amount, currency, "pending")
            
            return PaymentInitializationResponse(
                success=True,
                message="Payment initialized successfully",
                authorization_url=result["authorization_url"],
                access_code=result["access_code"],
                reference=result["reference"]
            )
            
        except ExternalServiceException as e:
            logger.error(f"Paystack initialization failed: {e}")
            raise e
        except Exception as e:
            logger.error(f"Payment initialization error: {e}")
            raise ExternalServiceException("PaystackService", "initialize_payment", str(e))
    
    async def verify_payment(self, reference: str) -> PaymentVerificationResponse:
        """Verify a payment transaction."""
        try:
            logger.info(f"Verifying payment with reference: {reference}")
            
            # Verify transaction with Paystack
            result = await self.client.verify_transaction(reference)
            
            # TODO: Update transaction in database
            # await self._update_transaction_status(reference, result)
            
            return PaymentVerificationResponse(
                success=True,
                message="Payment verification completed",
                transaction=result
            )
            
        except ExternalServiceException as e:
            logger.error(f"Paystack verification failed: {e}")
            raise e
        except Exception as e:
            logger.error(f"Payment verification error: {e}")
            raise ExternalServiceException("PaystackService", "verify_payment", str(e))
    
    async def list_transactions(
        self,
        per_page: int = 50,
        page: int = 1,
        customer: Optional[str] = None,
        status: Optional[TransactionStatus] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> TransactionListResponse:
        """List transactions with optional filters."""
        try:
            logger.info(f"Listing transactions: page {page}, per_page {per_page}")
            
            # Get transactions from Paystack
            result = await self.client.list_transactions(
                per_page=per_page,
                page=page,
                customer=customer,
                status=status,
                from_date=from_date,
                to_date=to_date
            )
            
            return TransactionListResponse(
                success=True,
                message="Transactions retrieved successfully",
                transactions=result.get("data", []),
                meta=result.get("meta", {})
            )
            
        except ExternalServiceException as e:
            logger.error(f"Transaction listing failed: {e}")
            raise e
        except Exception as e:
            logger.error(f"Transaction listing error: {e}")
            raise ExternalServiceException("PaystackService", "list_transactions", str(e))
    
    async def process_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """Process Paystack webhook."""
        try:
            # Verify webhook signature
            if not self.client.verify_webhook_signature(payload, signature):
                raise ValidationException("Invalid webhook signature")
            
            # Parse webhook payload
            import json
            webhook_data = json.loads(payload.decode('utf-8'))
            
            event = webhook_data.get("event")
            data = webhook_data.get("data", {})
            
            logger.info(f"Processing webhook event: {event}")
            
            # Handle different webhook events
            if event == "charge.success":
                await self._handle_successful_payment(data)
            elif event == "charge.failed":
                await self._handle_failed_payment(data)
            elif event == "transfer.success":
                await self._handle_successful_transfer(data)
            elif event == "transfer.failed":
                await self._handle_failed_transfer(data)
            else:
                logger.info(f"Unhandled webhook event: {event}")
            
            return {
                "success": True,
                "message": f"Webhook {event} processed successfully",
                "event": event,
                "reference": data.get("reference")
            }
            
        except ValidationException as e:
            logger.error(f"Webhook validation failed: {e}")
            raise e
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            raise ExternalServiceException("PaystackService", "process_webhook", str(e))
    
    async def _handle_successful_payment(self, data: Dict[str, Any]):
        """Handle successful payment webhook."""
        reference = data.get("reference")
        amount = data.get("amount", 0) / 100  # Convert from kobo
        
        logger.info(f"Payment successful: {reference}, amount: {amount}")
        
        # TODO: Update database, credit user account, send notifications
        # await self._update_transaction_status(reference, "success")
        # await self._credit_user_account(data)
        # await self._send_payment_notification(data)
    
    async def _handle_failed_payment(self, data: Dict[str, Any]):
        """Handle failed payment webhook."""
        reference = data.get("reference")
        
        logger.info(f"Payment failed: {reference}")
        
        # TODO: Update database, send notifications
        # await self._update_transaction_status(reference, "failed")
        # await self._send_failure_notification(data)
    
    async def _handle_successful_transfer(self, data: Dict[str, Any]):
        """Handle successful transfer webhook."""
        reference = data.get("reference")
        
        logger.info(f"Transfer successful: {reference}")
        
        # TODO: Update database, send notifications
    
    async def _handle_failed_transfer(self, data: Dict[str, Any]):
        """Handle failed transfer webhook."""
        reference = data.get("reference")
        
        logger.info(f"Transfer failed: {reference}")
        
        # TODO: Update database, send notifications
    
    def convert_amount_to_kobo(self, amount: Decimal) -> int:
        """Convert amount to kobo (smallest currency unit)."""
        return int(amount * 100)
    
    def convert_amount_from_kobo(self, amount_kobo: int) -> Decimal:
        """Convert amount from kobo to main currency unit."""
        return Decimal(amount_kobo) / 100
    
    def generate_reference(self, user_id: int, prefix: str = "hoardrun") -> str:
        """Generate a unique payment reference."""
        return f"{prefix}_{user_id}_{uuid.uuid4().hex[:8]}"


# Global service instance
_paystack_service: Optional[PaystackService] = None


def get_paystack_service() -> PaystackService:
    """Get the global Paystack service instance."""
    global _paystack_service
    
    if _paystack_service is None:
        _paystack_service = PaystackService()
    
    return _paystack_service
