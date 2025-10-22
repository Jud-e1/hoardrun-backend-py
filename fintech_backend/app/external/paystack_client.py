"""
Paystack payment gateway client for processing payments and transfers.
"""
import asyncio
import hashlib
import hmac
import json
from decimal import Decimal
from datetime import datetime, UTC
from typing import Dict, List, Optional, Any
from enum import Enum

import httpx

from ..config.logging import get_logger, log_external_service_call
from ..core.exceptions import ExternalServiceException

logger = get_logger("paystack_client")


class PaystackTransactionStatus(str, Enum):
    """Paystack transaction status."""
    PENDING = "pending"
    ONGOING = "ongoing"
    SUCCESS = "success"
    FAILED = "failed"
    ABANDONED = "abandoned"
    CANCELLED = "cancelled"


class PaystackChannel(str, Enum):
    """Paystack payment channels."""
    CARD = "card"
    BANK = "bank"
    USSD = "ussd"
    QR = "qr"
    MOBILE_MONEY = "mobile_money"
    BANK_TRANSFER = "bank_transfer"


class PaystackClient:
    """Paystack payment gateway client."""
    
    def __init__(
        self, 
        public_key: str, 
        secret_key: str, 
        environment: str = "test",
        webhook_secret: str = "",
        timeout: int = 30
    ):
        self.public_key = public_key
        self.secret_key = secret_key
        self.environment = environment
        self.webhook_secret = webhook_secret
        self.timeout = timeout

        # Base URL for direct API calls
        self.base_url = "https://api.paystack.co"
        
        # HTTP client for direct API calls
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {secret_key}",
                "Content-Type": "application/json",
                "Cache-Control": "no-cache"
            }
        )
    
    async def initialize_transaction(
        self,
        email: str,
        amount: int,  # Amount in kobo (smallest currency unit)
        currency: str = "NGN",
        reference: Optional[str] = None,
        callback_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        channels: Optional[List[PaystackChannel]] = None
    ) -> Dict[str, Any]:
        """Initialize a payment transaction."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            payload = {
                "email": email,
                "amount": amount,
                "currency": currency.upper()
            }
            
            if reference:
                payload["reference"] = reference
            if callback_url:
                payload["callback_url"] = callback_url
            if metadata:
                payload["metadata"] = metadata
            if channels:
                payload["channels"] = [channel.value for channel in channels]
            
            response = await self.client.post(
                f"{self.base_url}/transaction/initialize",
                json=payload
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("status"):
                duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                log_external_service_call(
                    logger=logger,
                    service_name="Paystack",
                    operation="initialize_transaction",
                    duration_ms=duration_ms,
                    success=True
                )
                return result["data"]
            else:
                raise ExternalServiceException(
                    "Paystack", 
                    "initialize_transaction", 
                    result.get("message", "Transaction initialization failed")
                )
                
        except httpx.HTTPStatusError as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="Paystack",
                operation="initialize_transaction",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("Paystack", "initialize_transaction", str(e))
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="Paystack",
                operation="initialize_transaction",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("Paystack", "initialize_transaction", str(e))
    
    async def verify_transaction(self, reference: str) -> Dict[str, Any]:
        """Verify a payment transaction."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            response = await self.client.get(
                f"{self.base_url}/transaction/verify/{reference}"
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("status"):
                duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                log_external_service_call(
                    logger=logger,
                    service_name="Paystack",
                    operation="verify_transaction",
                    duration_ms=duration_ms,
                    success=True
                )
                return result["data"]
            else:
                raise ExternalServiceException(
                    "Paystack", 
                    "verify_transaction", 
                    result.get("message", "Transaction verification failed")
                )
                
        except httpx.HTTPStatusError as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="Paystack",
                operation="verify_transaction",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("Paystack", "verify_transaction", str(e))
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="Paystack",
                operation="verify_transaction",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("Paystack", "verify_transaction", str(e))
    
    async def list_transactions(
        self,
        per_page: int = 50,
        page: int = 1,
        customer: Optional[str] = None,
        status: Optional[PaystackTransactionStatus] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """List transactions with optional filters."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            params = {
                "perPage": per_page,
                "page": page
            }
            
            if customer:
                params["customer"] = customer
            if status:
                params["status"] = status.value
            if from_date:
                params["from"] = from_date.isoformat()
            if to_date:
                params["to"] = to_date.isoformat()
            
            response = await self.client.get(
                f"{self.base_url}/transaction",
                params=params
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("status"):
                duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                log_external_service_call(
                    logger=logger,
                    service_name="Paystack",
                    operation="list_transactions",
                    duration_ms=duration_ms,
                    success=True
                )
                return result["data"]
            else:
                raise ExternalServiceException(
                    "Paystack", 
                    "list_transactions", 
                    result.get("message", "Failed to list transactions")
                )
                
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="Paystack",
                operation="list_transactions",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("Paystack", "list_transactions", str(e))
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature from Paystack."""
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured")
            return False
        
        try:
            expected_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha512
            ).hexdigest()
            
            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            logger.error(f"Webhook signature verification failed: {e}")
            return False
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Global client instance
_paystack_client: Optional[PaystackClient] = None


def get_paystack_client() -> PaystackClient:
    """Get the global Paystack client instance."""
    global _paystack_client
    
    if _paystack_client is None:
        from ..config.settings import get_settings
        settings = get_settings()
        _paystack_client = PaystackClient(
            public_key=settings.paystack_public_key,
            secret_key=settings.paystack_secret_key,
            environment=settings.paystack_environment,
            webhook_secret=settings.paystack_webhook_secret,
            timeout=settings.paystack_timeout
        )
    
    return _paystack_client
