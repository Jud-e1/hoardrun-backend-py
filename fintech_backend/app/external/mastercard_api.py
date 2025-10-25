"""
Mastercard API client for payment processing and card services.
"""

import asyncio
import json
import ssl
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import httpx
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
import base64
import uuid

from ..config.settings import get_settings
from ..config.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class MastercardAPIClient:
    """Mastercard API client for payment processing."""
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self._get_base_url()
        self.session = None
        self._ssl_context = None
        
    def _get_base_url(self) -> str:
        """Get the appropriate base URL based on environment."""
        if self.settings.mastercard_environment.lower() == "production":
            return "https://api.mastercard.com"
        else:
            return "https://sandbox.api.mastercard.com"
    
    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session with SSL configuration."""
        if self.session is None:
            # Configure SSL context for client certificate authentication
            ssl_context = ssl.create_default_context()
            
            # Load client certificate if available
            if self.settings.mastercard_cert_path and self.settings.mastercard_private_key_path:
                try:
                    ssl_context.load_cert_chain(
                        self.settings.mastercard_cert_path,
                        self.settings.mastercard_private_key_path,
                        password=self.settings.mastercard_cert_password or None
                    )
                    logger.info("Loaded Mastercard client certificate")
                except Exception as e:
                    logger.warning(f"Failed to load Mastercard client certificate: {e}")
            
            self.session = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.settings.mastercard_timeout),
                verify=ssl_context,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "X-MC-Client-Id": self.settings.mastercard_client_id,
                    "X-MC-Partner-Id": self.settings.mastercard_partner_id,
                }
            )
        
        return self.session
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        return str(uuid.uuid4())
    
    def _sign_request(self, payload: str, private_key_path: str) -> str:
        """Sign request payload with private key."""
        try:
            with open(private_key_path, 'rb') as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=self.settings.mastercard_cert_password.encode() if self.settings.mastercard_cert_password else None,
                    backend=default_backend()
                )
            
            signature = private_key.sign(
                payload.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            
            return base64.b64encode(signature).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to sign request: {e}")
            raise
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated request to Mastercard API."""
        try:
            session = await self._get_session()
            request_id = self._generate_request_id()
            
            headers = {
                "X-MC-Request-Id": request_id,
                "X-MC-Timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            # Add API key authentication
            if self.settings.mastercard_api_key:
                headers["Authorization"] = f"Bearer {self.settings.mastercard_api_key}"
            
            # Sign request if private key is available
            if data and self.settings.mastercard_private_key_path:
                payload = json.dumps(data, separators=(',', ':'))
                signature = self._sign_request(payload, self.settings.mastercard_private_key_path)
                headers["X-MC-Signature"] = signature
            
            logger.info(f"Making Mastercard API request: {method} {endpoint}")
            
            response = await session.request(
                method=method,
                url=endpoint,
                json=data,
                params=params,
                headers=headers
            )
            
            response.raise_for_status()
            
            result = response.json() if response.content else {}
            logger.info(f"Mastercard API request successful: {response.status_code}")
            
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Mastercard API HTTP error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Mastercard API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Mastercard API request failed: {e}")
            raise
    
    async def create_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a payment transaction."""
        endpoint = "/payments/v1/payments"
        
        payload = {
            "requestId": self._generate_request_id(),
            "partnerId": self.settings.mastercard_partner_id,
            "amount": payment_data.get("amount"),
            "currency": payment_data.get("currency", "USD"),
            "paymentMethod": payment_data.get("payment_method"),
            "merchantInfo": {
                "merchantId": self.settings.mastercard_client_id,
                "merchantName": self.settings.mastercard_org_name,
                "merchantCountry": self.settings.mastercard_country
            },
            "transactionInfo": {
                "description": payment_data.get("description", "Payment"),
                "reference": payment_data.get("reference")
            }
        }
        
        return await self._make_request("POST", endpoint, payload)
    
    async def get_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """Get payment status."""
        endpoint = f"/payments/v1/payments/{payment_id}"
        return await self._make_request("GET", endpoint)
    
    async def refund_payment(self, payment_id: str, refund_data: Dict[str, Any]) -> Dict[str, Any]:
        """Refund a payment."""
        endpoint = f"/payments/v1/payments/{payment_id}/refunds"
        
        payload = {
            "requestId": self._generate_request_id(),
            "amount": refund_data.get("amount"),
            "currency": refund_data.get("currency", "USD"),
            "reason": refund_data.get("reason", "Customer request")
        }
        
        return await self._make_request("POST", endpoint, payload)
    
    async def validate_card(self, card_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate card information."""
        endpoint = "/cards/v1/validate"
        
        payload = {
            "requestId": self._generate_request_id(),
            "cardNumber": card_data.get("card_number"),
            "expiryMonth": card_data.get("expiry_month"),
            "expiryYear": card_data.get("expiry_year"),
            "cvv": card_data.get("cvv")
        }
        
        return await self._make_request("POST", endpoint, payload)
    
    async def tokenize_card(self, card_data: Dict[str, Any]) -> Dict[str, Any]:
        """Tokenize card for secure storage."""
        endpoint = "/tokens/v1/tokenize"
        
        payload = {
            "requestId": self._generate_request_id(),
            "cardNumber": card_data.get("card_number"),
            "expiryMonth": card_data.get("expiry_month"),
            "expiryYear": card_data.get("expiry_year"),
            "cardholderName": card_data.get("cardholder_name")
        }
        
        return await self._make_request("POST", endpoint, payload)
    
    async def get_exchange_rates(self, base_currency: str = "USD") -> Dict[str, Any]:
        """Get current exchange rates."""
        endpoint = "/rates/v1/exchange-rates"
        params = {"baseCurrency": base_currency}
        
        return await self._make_request("GET", endpoint, params=params)
    
    async def create_transfer(self, transfer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a money transfer."""
        endpoint = "/transfers/v1/transfers"
        
        payload = {
            "requestId": self._generate_request_id(),
            "partnerId": self.settings.mastercard_partner_id,
            "amount": transfer_data.get("amount"),
            "currency": transfer_data.get("currency", "USD"),
            "sender": transfer_data.get("sender"),
            "recipient": transfer_data.get("recipient"),
            "purpose": transfer_data.get("purpose", "Personal transfer"),
            "reference": transfer_data.get("reference")
        }
        
        return await self._make_request("POST", endpoint, payload)
    
    async def get_transfer_status(self, transfer_id: str) -> Dict[str, Any]:
        """Get transfer status."""
        endpoint = f"/transfers/v1/transfers/{transfer_id}"
        return await self._make_request("GET", endpoint)
    
    async def get_transaction_history(
        self, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Get transaction history."""
        endpoint = "/transactions/v1/history"
        
        params = {"limit": limit}
        if start_date:
            params["startDate"] = start_date.isoformat()
        if end_date:
            params["endDate"] = end_date.isoformat()
        
        return await self._make_request("GET", endpoint, params=params)
    
    async def verify_merchant(self, merchant_data: Dict[str, Any]) -> Dict[str, Any]:
        """Verify merchant information."""
        endpoint = "/merchants/v1/verify"
        
        payload = {
            "requestId": self._generate_request_id(),
            "merchantId": merchant_data.get("merchant_id"),
            "merchantName": merchant_data.get("merchant_name"),
            "merchantCountry": merchant_data.get("merchant_country", self.settings.mastercard_country)
        }
        
        return await self._make_request("POST", endpoint, payload)
    
    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.aclose()
            self.session = None


# Global client instance
_mastercard_client: Optional[MastercardAPIClient] = None


def get_mastercard_client() -> MastercardAPIClient:
    """Get the global Mastercard API client instance."""
    global _mastercard_client
    
    if _mastercard_client is None:
        _mastercard_client = MastercardAPIClient()
    
    return _mastercard_client


async def close_mastercard_client():
    """Close the global Mastercard API client."""
    global _mastercard_client
    
    if _mastercard_client:
        await _mastercard_client.close()
        _mastercard_client = None
