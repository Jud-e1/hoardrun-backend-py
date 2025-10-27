"""
Mock payment gateway client with realistic response delays and behavior.
"""
import asyncio
import random
import uuid
from decimal import Decimal
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Any
from enum import Enum

from ..config.logging import get_logger, log_external_service_call
from ..core.exceptions import ExternalServiceException
from ..utils.calculations import FeeCalculator, TransferType

logger = get_logger("payment_gateway")


class PaymentStatus(str, Enum):
    """Payment processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentMethod(str, Enum):
    """Payment method types."""
    CARD = "card"
    BANK_ACCOUNT = "bank_account"
    DIGITAL_WALLET = "digital_wallet"
    MOBILE_MONEY = "mobile_money"


class MockPaymentGatewayClient:
    """Mock payment gateway client for processing payments and transfers."""
    
    def __init__(self, base_url: str = "https://mock-payment-gateway.com", timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout
        self.payments: Dict[str, Dict[str, Any]] = {}
    
    async def process_payment(
        self,
        amount: Decimal,
        currency: str,
        payment_method: PaymentMethod,
        payment_details: Dict[str, Any],
        reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a payment transaction."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate realistic processing delay
            await asyncio.sleep(random.uniform(0.5, 2.0))
            
            payment_id = str(uuid.uuid4())
            
            # Simulate different payment outcomes
            success_rate = 0.95  # 95% success rate
            
            if random.random() < success_rate:
                status = PaymentStatus.COMPLETED
                failure_reason = None
                
                # Calculate fees
                transfer_type = self._map_payment_method_to_transfer_type(payment_method)
                fee = FeeCalculator.calculate_transfer_fee(amount, transfer_type)
                
                result = {
                    "payment_id": payment_id,
                    "status": status.value,
                    "amount": float(amount),
                    "currency": currency.upper(),
                    "fee": float(fee),
                    "net_amount": float(amount - fee),
                    "payment_method": payment_method.value,
                    "reference": reference or f"PAY_{payment_id[:8]}",
                    "processed_at": datetime.now(UTC).isoformat(),
                    "estimated_settlement": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                    "gateway_reference": f"GW_{uuid.uuid4().hex[:12]}",
                    "failure_reason": None
                }
            else:
                # Simulate payment failure
                status = PaymentStatus.FAILED
                failure_reasons = [
                    "Insufficient funds",
                    "Card declined", 
                    "Invalid payment details",
                    "Bank network error",
                    "Daily limit exceeded"
                ]
                failure_reason = random.choice(failure_reasons)
                
                result = {
                    "payment_id": payment_id,
                    "status": status.value,
                    "amount": float(amount),
                    "currency": currency.upper(),
                    "fee": 0.0,
                    "net_amount": 0.0,
                    "payment_method": payment_method.value,
                    "reference": reference or f"PAY_{payment_id[:8]}",
                    "processed_at": datetime.now(UTC).isoformat(),
                    "estimated_settlement": None,
                    "gateway_reference": None,
                    "failure_reason": failure_reason
                }
            
            # Store payment for status tracking
            self.payments[payment_id] = result
            
            # Log the service call
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="PaymentGateway",
                operation="process_payment",
                duration_ms=duration_ms,
                success=status == PaymentStatus.COMPLETED
            )
            
            return result
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="PaymentGateway", 
                operation="process_payment",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("PaymentGateway", "process_payment", str(e))
    
    async def get_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """Get the status of a payment transaction."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate API delay
            await asyncio.sleep(random.uniform(0.1, 0.5))
            
            if payment_id not in self.payments:
                raise ExternalServiceException("PaymentGateway", "get_payment_status", f"Payment {payment_id} not found")
            
            payment = self.payments[payment_id]
            
            # Simulate status updates for pending payments
            if payment["status"] == PaymentStatus.PENDING.value:
                if random.random() < 0.3:  # 30% chance to update status
                    payment["status"] = PaymentStatus.PROCESSING.value
                    payment["updated_at"] = datetime.now(UTC).isoformat()
            elif payment["status"] == PaymentStatus.PROCESSING.value:
                if random.random() < 0.5:  # 50% chance to complete
                    payment["status"] = PaymentStatus.COMPLETED.value
                    payment["completed_at"] = datetime.now(UTC).isoformat()
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="PaymentGateway",
                operation="get_payment_status", 
                duration_ms=duration_ms,
                success=True
            )
            
            return payment
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="PaymentGateway",
                operation="get_payment_status",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("PaymentGateway", "get_payment_status", str(e))
    
    async def get_exchange_rates(self, base_currency: str = "USD") -> Dict[str, Decimal]:
        """Get current exchange rates."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate API delay
            await asyncio.sleep(random.uniform(0.2, 0.8))
            
            # Mock exchange rates with some variation
            base_rates = {
                "USD": 1.0000,
                "EUR": 0.8500,
                "GBP": 0.7800,
                "KES": 147.5000,
                "UGX": 3750.0000,
                "TZS": 2500.0000,
            }
            
            rates = {}
            for currency, rate in base_rates.items():
                if currency != base_currency.upper():
                    # Add random variation (±0.5%)
                    variation = random.uniform(0.995, 1.005)
                    rates[currency] = Decimal(str(rate * variation))
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="PaymentGateway",
                operation="get_exchange_rates",
                duration_ms=duration_ms,
                success=True
            )
            
            return rates
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="PaymentGateway",
                operation="get_exchange_rates",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("PaymentGateway", "get_exchange_rates", str(e))
    
    async def validate_payment_method(
        self,
        payment_method: PaymentMethod,
        payment_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate payment method details."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate validation delay
            await asyncio.sleep(random.uniform(0.3, 1.0))
            
            is_valid = random.random() < 0.9  # 90% validation success rate
            
            result = {
                "is_valid": is_valid,
                "payment_method": payment_method.value,
                "validation_code": "VALID" if is_valid else "INVALID",
                "checked_at": datetime.now(UTC).isoformat()
            }
            
            if not is_valid:
                result["error_message"] = random.choice([
                    "Invalid card number",
                    "Expired card",
                    "Invalid CVV",
                    "Card not supported",
                    "Account closed"
                ])
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="PaymentGateway",
                operation="validate_payment_method",
                duration_ms=duration_ms,
                success=is_valid
            )
            
            return result
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="PaymentGateway",
                operation="validate_payment_method",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("PaymentGateway", "validate_payment_method", str(e))
    
    async def refund_payment(self, payment_id: str, amount: Optional[Decimal] = None) -> Dict[str, Any]:
        """Process a payment refund."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate processing delay
            await asyncio.sleep(random.uniform(1.0, 3.0))
            
            if payment_id not in self.payments:
                raise ExternalServiceException("PaymentGateway", "refund_payment", f"Payment {payment_id} not found")
            
            original_payment = self.payments[payment_id]
            
            if original_payment["status"] != PaymentStatus.COMPLETED.value:
                raise ExternalServiceException("PaymentGateway", "refund_payment", "Can only refund completed payments")
            
            refund_amount = amount or Decimal(str(original_payment["amount"]))
            refund_id = str(uuid.uuid4())
            
            # Most refunds succeed
            success = random.random() < 0.95
            
            result = {
                "refund_id": refund_id,
                "original_payment_id": payment_id,
                "refund_amount": float(refund_amount),
                "currency": original_payment["currency"],
                "status": "completed" if success else "failed",
                "processed_at": datetime.now(UTC).isoformat(),
                "estimated_arrival": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
                "gateway_reference": f"RF_{uuid.uuid4().hex[:12]}" if success else None
            }
            
            if not success:
                result["failure_reason"] = "Bank declined refund request"
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="PaymentGateway",
                operation="refund_payment",
                duration_ms=duration_ms,
                success=success
            )
            
            return result
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="PaymentGateway",
                operation="refund_payment",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("PaymentGateway", "refund_payment", str(e))
    
    def _map_payment_method_to_transfer_type(self, payment_method: PaymentMethod) -> TransferType:
        """Map payment method to transfer type for fee calculation."""
        mapping = {
            PaymentMethod.CARD: TransferType.INSTANT,
            PaymentMethod.BANK_ACCOUNT: TransferType.ACH,
            PaymentMethod.DIGITAL_WALLET: TransferType.INSTANT,
            PaymentMethod.MOBILE_MONEY: TransferType.DOMESTIC
        }
        return mapping.get(payment_method, TransferType.DOMESTIC)


# Global client instance
_payment_gateway_client: Optional[MockPaymentGatewayClient] = None


def get_payment_gateway_client() -> MockPaymentGatewayClient:
    """Get the global payment gateway client instance."""
    global _payment_gateway_client
    
    if _payment_gateway_client is None:
        from ..config.settings import get_settings
        settings = get_settings()
        _payment_gateway_client = MockPaymentGatewayClient(
            base_url=settings.payment_gateway_url,
            timeout=settings.payment_gateway_timeout
        )
    
    return _payment_gateway_client


# Alias for backward compatibility
get_payment_gateway = get_payment_gateway_client