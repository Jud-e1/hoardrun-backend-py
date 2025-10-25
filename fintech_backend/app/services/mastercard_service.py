"""
Mastercard service for payment processing and card management.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from decimal import Decimal

from ..services.auth_service import AuthService
from ..core.exceptions import (
    ValidationException, AuthenticationException, NotFoundError, BusinessLogicError
)
from ..config.settings import get_settings
from ..config.logging import get_logger
from ..external.mastercard_api import get_mastercard_client

logger = get_logger(__name__)
settings = get_settings()


class MastercardService:
    """Mastercard service for handling payment operations."""
    
    def __init__(self):
        self.auth_service = AuthService()
        self.mastercard_client = get_mastercard_client()
    
    async def process_payment(self, token: str, payment_data: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """
        Process a payment using Mastercard API.
        
        Args:
            token: Access token
            payment_data: Payment information
            db: Database session
            
        Returns:
            Dict: Payment result
        """
        try:
            logger.info(f"Processing Mastercard payment: {payment_data.get('amount')} {payment_data.get('currency', 'USD')}")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Validate payment data
            self._validate_payment_data(payment_data)
            
            # Prepare payment request
            payment_request = {
                "amount": payment_data["amount"],
                "currency": payment_data.get("currency", "USD"),
                "payment_method": payment_data["payment_method"],
                "description": payment_data.get("description", "Payment via Hoardrun"),
                "reference": payment_data.get("reference", self._generate_reference())
            }
            
            # Process payment with Mastercard API
            result = await self.mastercard_client.create_payment(payment_request)
            
            # Log successful payment
            logger.info(f"Mastercard payment processed successfully: {result.get('paymentId')}")
            
            return {
                "payment_id": result.get("paymentId"),
                "status": result.get("status", "PENDING"),
                "amount": payment_data["amount"],
                "currency": payment_data.get("currency", "USD"),
                "reference": payment_request["reference"],
                "created_at": datetime.utcnow().isoformat(),
                "provider": "mastercard"
            }
            
        except Exception as e:
            logger.error(f"Mastercard payment failed: {e}")
            raise ValidationException(f"Payment processing failed: {str(e)}")
    
    async def get_payment_status(self, token: str, payment_id: str, db: Session) -> Dict[str, Any]:
        """
        Get payment status from Mastercard API.
        
        Args:
            token: Access token
            payment_id: Payment ID
            db: Database session
            
        Returns:
            Dict: Payment status
        """
        try:
            logger.info(f"Getting Mastercard payment status: {payment_id}")
            
            # Get current user (for authentication)
            await self.auth_service.get_current_user(token, db)
            
            # Get payment status from Mastercard API
            result = await self.mastercard_client.get_payment_status(payment_id)
            
            return {
                "payment_id": payment_id,
                "status": result.get("status"),
                "amount": result.get("amount"),
                "currency": result.get("currency"),
                "created_at": result.get("createdAt"),
                "updated_at": result.get("updatedAt"),
                "provider": "mastercard"
            }
            
        except Exception as e:
            logger.error(f"Failed to get Mastercard payment status: {e}")
            raise
    
    async def refund_payment(self, token: str, payment_id: str, refund_data: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """
        Refund a payment using Mastercard API.
        
        Args:
            token: Access token
            payment_id: Payment ID to refund
            refund_data: Refund information
            db: Database session
            
        Returns:
            Dict: Refund result
        """
        try:
            logger.info(f"Processing Mastercard refund for payment: {payment_id}")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Process refund with Mastercard API
            result = await self.mastercard_client.refund_payment(payment_id, refund_data)
            
            logger.info(f"Mastercard refund processed: {result.get('refundId')}")
            
            return {
                "refund_id": result.get("refundId"),
                "payment_id": payment_id,
                "status": result.get("status", "PENDING"),
                "amount": refund_data.get("amount"),
                "currency": refund_data.get("currency", "USD"),
                "reason": refund_data.get("reason"),
                "created_at": datetime.utcnow().isoformat(),
                "provider": "mastercard"
            }
            
        except Exception as e:
            logger.error(f"Mastercard refund failed: {e}")
            raise ValidationException(f"Refund processing failed: {str(e)}")
    
    async def validate_card(self, token: str, card_data: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """
        Validate card information using Mastercard API.
        
        Args:
            token: Access token
            card_data: Card information
            db: Database session
            
        Returns:
            Dict: Validation result
        """
        try:
            logger.info("Validating card with Mastercard API")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Validate card with Mastercard API
            result = await self.mastercard_client.validate_card(card_data)
            
            return {
                "is_valid": result.get("isValid", False),
                "card_type": result.get("cardType"),
                "issuer": result.get("issuer"),
                "country": result.get("country"),
                "validation_id": result.get("validationId"),
                "provider": "mastercard"
            }
            
        except Exception as e:
            logger.error(f"Card validation failed: {e}")
            raise ValidationException(f"Card validation failed: {str(e)}")
    
    async def tokenize_card(self, token: str, card_data: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """
        Tokenize card for secure storage using Mastercard API.
        
        Args:
            token: Access token
            card_data: Card information
            db: Database session
            
        Returns:
            Dict: Tokenization result
        """
        try:
            logger.info("Tokenizing card with Mastercard API")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Tokenize card with Mastercard API
            result = await self.mastercard_client.tokenize_card(card_data)
            
            return {
                "token": result.get("token"),
                "token_id": result.get("tokenId"),
                "card_type": result.get("cardType"),
                "last_four": result.get("lastFour"),
                "expiry_month": result.get("expiryMonth"),
                "expiry_year": result.get("expiryYear"),
                "created_at": datetime.utcnow().isoformat(),
                "provider": "mastercard"
            }
            
        except Exception as e:
            logger.error(f"Card tokenization failed: {e}")
            raise ValidationException(f"Card tokenization failed: {str(e)}")
    
    async def create_transfer(self, token: str, transfer_data: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """
        Create a money transfer using Mastercard API.
        
        Args:
            token: Access token
            transfer_data: Transfer information
            db: Database session
            
        Returns:
            Dict: Transfer result
        """
        try:
            logger.info(f"Creating Mastercard transfer: {transfer_data.get('amount')} {transfer_data.get('currency', 'USD')}")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Create transfer with Mastercard API
            result = await self.mastercard_client.create_transfer(transfer_data)
            
            logger.info(f"Mastercard transfer created: {result.get('transferId')}")
            
            return {
                "transfer_id": result.get("transferId"),
                "status": result.get("status", "PENDING"),
                "amount": transfer_data["amount"],
                "currency": transfer_data.get("currency", "USD"),
                "recipient": transfer_data["recipient"],
                "reference": transfer_data.get("reference"),
                "created_at": datetime.utcnow().isoformat(),
                "provider": "mastercard"
            }
            
        except Exception as e:
            logger.error(f"Mastercard transfer failed: {e}")
            raise ValidationException(f"Transfer creation failed: {str(e)}")
    
    async def get_transfer_status(self, token: str, transfer_id: str, db: Session) -> Dict[str, Any]:
        """
        Get transfer status from Mastercard API.
        
        Args:
            token: Access token
            transfer_id: Transfer ID
            db: Database session
            
        Returns:
            Dict: Transfer status
        """
        try:
            logger.info(f"Getting Mastercard transfer status: {transfer_id}")
            
            # Get current user (for authentication)
            await self.auth_service.get_current_user(token, db)
            
            # Get transfer status from Mastercard API
            result = await self.mastercard_client.get_transfer_status(transfer_id)
            
            return {
                "transfer_id": transfer_id,
                "status": result.get("status"),
                "amount": result.get("amount"),
                "currency": result.get("currency"),
                "recipient": result.get("recipient"),
                "created_at": result.get("createdAt"),
                "updated_at": result.get("updatedAt"),
                "provider": "mastercard"
            }
            
        except Exception as e:
            logger.error(f"Failed to get Mastercard transfer status: {e}")
            raise
    
    async def get_exchange_rates(self, token: str, base_currency: str = "USD", db: Session = None) -> Dict[str, Any]:
        """
        Get exchange rates from Mastercard API.
        
        Args:
            token: Access token
            base_currency: Base currency
            db: Database session
            
        Returns:
            Dict: Exchange rates
        """
        try:
            logger.info(f"Getting exchange rates from Mastercard API: {base_currency}")
            
            # Get current user (for authentication)
            if db:
                await self.auth_service.get_current_user(token, db)
            
            # Get exchange rates from Mastercard API
            result = await self.mastercard_client.get_exchange_rates(base_currency)
            
            return {
                "base_currency": base_currency,
                "rates": result.get("rates", {}),
                "timestamp": result.get("timestamp"),
                "provider": "mastercard"
            }
            
        except Exception as e:
            logger.error(f"Failed to get exchange rates: {e}")
            raise
    
    async def get_transaction_history(
        self, 
        token: str, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Get transaction history from Mastercard API.
        
        Args:
            token: Access token
            start_date: Start date filter
            end_date: End date filter
            limit: Number of transactions to retrieve
            db: Database session
            
        Returns:
            Dict: Transaction history
        """
        try:
            logger.info("Getting transaction history from Mastercard API")
            
            # Get current user (for authentication)
            if db:
                await self.auth_service.get_current_user(token, db)
            
            # Get transaction history from Mastercard API
            result = await self.mastercard_client.get_transaction_history(start_date, end_date, limit)
            
            return {
                "transactions": result.get("transactions", []),
                "total": result.get("total", 0),
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "limit": limit,
                "provider": "mastercard"
            }
            
        except Exception as e:
            logger.error(f"Failed to get transaction history: {e}")
            raise
    
    def _validate_payment_data(self, payment_data: Dict[str, Any]) -> None:
        """Validate payment data."""
        required_fields = ["amount", "payment_method"]
        
        for field in required_fields:
            if field not in payment_data:
                raise ValidationException(f"Missing required field: {field}")
        
        if not isinstance(payment_data["amount"], (int, float, Decimal)) or payment_data["amount"] <= 0:
            raise ValidationException("Amount must be a positive number")
    
    def _generate_reference(self) -> str:
        """Generate unique payment reference."""
        return f"MC_{secrets.token_urlsafe(12)}"


# Service instance getter
def get_mastercard_service() -> MastercardService:
    """Get Mastercard service instance."""
    return MastercardService()
