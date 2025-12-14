"""
MTN MOMO API client for mobile money transactions.
"""

import asyncio
import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import httpx
import base64

from ..config.settings import get_settings
from ..config.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class MTNMomoAPIClient:
    """MTN MOMO API client for mobile money operations."""
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.momo_api_url
        self.session = None
        self._access_token = None
        self._token_expires_at = None
        
    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session."""
        if self.session is None:
            self.session = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.settings.momo_timeout),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "X-Target-Environment": self.settings.momo_target_environment,
                    "Ocp-Apim-Subscription-Key": self.settings.momo_primary_key,
                }
            )
        
        return self.session
    
    def _generate_uuid(self) -> str:
        """Generate UUID for requests."""
        return str(uuid.uuid4())
    
    async def _get_access_token(self) -> str:
        """Get or refresh access token."""
        if self._access_token and self._token_expires_at and datetime.utcnow() < self._token_expires_at:
            return self._access_token
        
        try:
            session = await self._get_session()
            
            # Create API user if needed (sandbox only)
            if self.settings.momo_target_environment == "sandbox":
                await self._create_api_user()
            
            # Get access token
            auth_string = base64.b64encode(f"{self.settings.momo_primary_key}:{self.settings.momo_secondary_key}".encode()).decode()
            
            response = await session.post(
                "/collection/token/",
                headers={
                    "Authorization": f"Basic {auth_string}",
                    "Ocp-Apim-Subscription-Key": self.settings.momo_primary_key,
                }
            )
            
            response.raise_for_status()
            token_data = response.json()
            
            self._access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)
            self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)  # Refresh 1 minute early
            
            logger.info("MTN MOMO access token obtained successfully")
            return self._access_token
            
        except Exception as e:
            logger.error(f"Failed to get MTN MOMO access token: {e}")
            raise
    
    async def _create_api_user(self):
        """Create API user for sandbox environment."""
        try:
            session = await self._get_session()
            user_id = self._generate_uuid()
            
            response = await session.post(
                f"/v1_0/apiuser",
                json={
                    "providerCallbackHost": "webhook.site"  # Sandbox callback host
                },
                headers={
                    "X-Reference-Id": user_id,
                    "Ocp-Apim-Subscription-Key": self.settings.momo_primary_key,
                }
            )
            
            if response.status_code in [201, 409]:  # Created or already exists
                logger.info("MTN MOMO API user created/exists")
            else:
                response.raise_for_status()
                
        except Exception as e:
            logger.warning(f"Failed to create MTN MOMO API user: {e}")
            # Continue anyway as this might not be required in all environments
    
    async def _make_authenticated_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Make authenticated request to MTN MOMO API."""
        try:
            session = await self._get_session()
            access_token = await self._get_access_token()
            
            request_headers = {
                "Authorization": f"Bearer {access_token}",
                "X-Target-Environment": self.settings.momo_target_environment,
                "Ocp-Apim-Subscription-Key": self.settings.momo_primary_key,
            }
            
            if headers:
                request_headers.update(headers)
            
            logger.info(f"Making MTN MOMO API request: {method} {endpoint}")
            
            response = await session.request(
                method=method,
                url=endpoint,
                json=data,
                params=params,
                headers=request_headers
            )
            
            response.raise_for_status()
            
            result = response.json() if response.content else {}
            logger.info(f"MTN MOMO API request successful: {response.status_code}")
            
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"MTN MOMO API HTTP error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"MTN MOMO API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"MTN MOMO API request failed: {e}")
            raise
    
    async def request_to_pay(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Request payment from a customer."""
        endpoint = "/collection/v1_0/requesttopay"
        reference_id = self._generate_uuid()
        
        payload = {
            "amount": str(payment_data["amount"]),
            "currency": payment_data.get("currency", "EUR"),
            "externalId": payment_data.get("external_id", reference_id),
            "payer": {
                "partyIdType": "MSISDN",
                "partyId": payment_data["phone_number"]
            },
            "payerMessage": payment_data.get("payer_message", "Payment request"),
            "payeeNote": payment_data.get("payee_note", "Payment from Hoardrun")
        }
        
        headers = {"X-Reference-Id": reference_id}
        
        await self._make_authenticated_request("POST", endpoint, payload, headers=headers)
        
        return {
            "reference_id": reference_id,
            "status": "PENDING",
            "external_id": payload["externalId"]
        }
    
    async def get_request_to_pay_status(self, reference_id: str) -> Dict[str, Any]:
        """Get the status of a payment request."""
        endpoint = f"/collection/v1_0/requesttopay/{reference_id}"
        return await self._make_authenticated_request("GET", endpoint)
    
    async def transfer(self, transfer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transfer money to a recipient."""
        endpoint = "/disbursement/v1_0/transfer"
        reference_id = self._generate_uuid()
        
        payload = {
            "amount": str(transfer_data["amount"]),
            "currency": transfer_data.get("currency", "EUR"),
            "externalId": transfer_data.get("external_id", reference_id),
            "payee": {
                "partyIdType": "MSISDN",
                "partyId": transfer_data["recipient_phone"]
            },
            "payerMessage": transfer_data.get("payer_message", "Transfer from Hoardrun"),
            "payeeNote": transfer_data.get("payee_note", "Money transfer")
        }
        
        headers = {"X-Reference-Id": reference_id}
        
        await self._make_authenticated_request("POST", endpoint, payload, headers=headers)
        
        return {
            "reference_id": reference_id,
            "status": "PENDING",
            "external_id": payload["externalId"]
        }
    
    async def get_transfer_status(self, reference_id: str) -> Dict[str, Any]:
        """Get the status of a transfer."""
        endpoint = f"/disbursement/v1_0/transfer/{reference_id}"
        return await self._make_authenticated_request("GET", endpoint)
    
    async def get_account_balance(self) -> Dict[str, Any]:
        """Get account balance."""
        endpoint = "/collection/v1_0/account/balance"
        return await self._make_authenticated_request("GET", endpoint)
    
    async def get_account_holder_info(self, phone_number: str) -> Dict[str, Any]:
        """Get account holder information."""
        endpoint = f"/collection/v1_0/accountholder/msisdn/{phone_number}/basicuserinfo"
        return await self._make_authenticated_request("GET", endpoint)
    
    async def validate_account_holder(self, phone_number: str) -> Dict[str, Any]:
        """Validate if account holder is active."""
        endpoint = f"/collection/v1_0/accountholder/msisdn/{phone_number}/active"
        return await self._make_authenticated_request("GET", endpoint)
    
    async def deposit(self, deposit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Deposit money to user's account."""
        endpoint = "/collection/v1_0/deposit"
        reference_id = self._generate_uuid()
        
        payload = {
            "amount": str(deposit_data["amount"]),
            "currency": deposit_data.get("currency", "EUR"),
            "externalId": deposit_data.get("external_id", reference_id),
            "payer": {
                "partyIdType": "MSISDN",
                "partyId": deposit_data["phone_number"]
            },
            "payerMessage": deposit_data.get("payer_message", "Deposit to Hoardrun"),
            "payeeNote": deposit_data.get("payee_note", "Account deposit")
        }
        
        headers = {"X-Reference-Id": reference_id}
        
        await self._make_authenticated_request("POST", endpoint, payload, headers=headers)
        
        return {
            "reference_id": reference_id,
            "status": "PENDING",
            "external_id": payload["externalId"]
        }
    
    async def get_deposit_status(self, reference_id: str) -> Dict[str, Any]:
        """Get the status of a deposit."""
        endpoint = f"/collection/v1_0/deposit/{reference_id}"
        return await self._make_authenticated_request("GET", endpoint)
    
    async def withdraw(self, withdrawal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Withdraw money from user's account."""
        endpoint = "/disbursement/v1_0/withdraw"
        reference_id = self._generate_uuid()
        
        payload = {
            "amount": str(withdrawal_data["amount"]),
            "currency": withdrawal_data.get("currency", "EUR"),
            "externalId": withdrawal_data.get("external_id", reference_id),
            "payee": {
                "partyIdType": "MSISDN",
                "partyId": withdrawal_data["phone_number"]
            },
            "payerMessage": withdrawal_data.get("payer_message", "Withdrawal from Hoardrun"),
            "payeeNote": withdrawal_data.get("payee_note", "Account withdrawal")
        }
        
        headers = {"X-Reference-Id": reference_id}
        
        await self._make_authenticated_request("POST", endpoint, payload, headers=headers)
        
        return {
            "reference_id": reference_id,
            "status": "PENDING",
            "external_id": payload["externalId"]
        }
    
    async def get_withdrawal_status(self, reference_id: str) -> Dict[str, Any]:
        """Get the status of a withdrawal."""
        endpoint = f"/disbursement/v1_0/withdraw/{reference_id}"
        return await self._make_authenticated_request("GET", endpoint)
    
    async def get_transaction_status(self, reference_id: str, transaction_type: str = "collection") -> Dict[str, Any]:
        """Get transaction status by reference ID and type."""
        if transaction_type == "collection":
            return await self.get_request_to_pay_status(reference_id)
        elif transaction_type == "disbursement":
            return await self.get_transfer_status(reference_id)
        elif transaction_type == "deposit":
            return await self.get_deposit_status(reference_id)
        elif transaction_type == "withdrawal":
            return await self.get_withdrawal_status(reference_id)
        else:
            raise ValueError(f"Unknown transaction type: {transaction_type}")
    
    async def cancel_transaction(self, reference_id: str, transaction_type: str = "collection") -> Dict[str, Any]:
        """Cancel a pending transaction."""
        # Note: MTN MOMO API doesn't have a direct cancel endpoint
        # This would typically be handled by checking status and implementing business logic
        status = await self.get_transaction_status(reference_id, transaction_type)
        
        if status.get("status") == "PENDING":
            logger.info(f"Transaction {reference_id} is pending - cancellation would be handled by business logic")
            return {
                "reference_id": reference_id,
                "status": "CANCELLATION_REQUESTED",
                "message": "Cancellation request noted - transaction will be cancelled if still pending"
            }
        else:
            return {
                "reference_id": reference_id,
                "status": status.get("status"),
                "message": f"Transaction cannot be cancelled - current status: {status.get('status')}"
            }
    
    async def get_supported_currencies(self) -> List[str]:
        """Get list of supported currencies."""
        # This would typically come from an API endpoint, but for now return common ones
        return ["EUR", "USD", "GHS", "UGX", "KES", "TZS", "RWF"]
    
    async def health_check(self) -> Dict[str, Any]:
        """Check API health status."""
        try:
            # Try to get account balance as a health check
            await self.get_account_balance()
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "environment": self.settings.momo_target_environment
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
                "environment": self.settings.momo_target_environment
            }
    
    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.aclose()
            self.session = None


# Global client instance
_mtn_momo_client: Optional[MTNMomoAPIClient] = None


def get_mtn_momo_client() -> MTNMomoAPIClient:
    """Get the global MTN MOMO API client instance."""
    global _mtn_momo_client
    
    if _mtn_momo_client is None:
        _mtn_momo_client = MTNMomoAPIClient()
    
    return _mtn_momo_client


async def close_mtn_momo_client():
    """Close the global MTN MOMO API client."""
    global _mtn_momo_client
    
    if _mtn_momo_client:
        await _mtn_momo_client.close()
        _mtn_momo_client = None
