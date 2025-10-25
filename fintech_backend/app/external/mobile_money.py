"""
Mock mobile money service for peer-to-peer transactions and mobile payments.
"""
import asyncio
import random
import uuid
from decimal import Decimal
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Any
from enum import Enum

from ..config.logging import get_logger, log_external_service_call
from ...core.exceptions import ExternalServiceException

logger = get_logger("mobile_money")


class MobileMoneyProvider(str, Enum):
    """Mobile money provider types."""
    MPESA = "mpesa"
    AIRTEL_MONEY = "airtel_money"
    MTN_MONEY = "mtn_money"
    TIGO_PESA = "tigo_pesa"


class TransactionType(str, Enum):
    """Mobile money transaction types."""
    SEND_MONEY = "send_money"
    RECEIVE_MONEY = "receive_money"
    WITHDRAW_CASH = "withdraw_cash"
    DEPOSIT_CASH = "deposit_cash"
    PAY_BILL = "pay_bill"
    BUY_AIRTIME = "buy_airtime"


class MockMobileMoneyClient:
    """Mock mobile money service client."""
    
    def __init__(self, base_url: str = "https://mock-mobile-money.com", timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout
        self.transactions: Dict[str, Dict[str, Any]] = {}
    
    async def send_money(
        self,
        sender_phone: str,
        recipient_phone: str,
        amount: Decimal,
        currency: str = "KES",
        provider: MobileMoneyProvider = MobileMoneyProvider.MPESA,
        reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send money via mobile money."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate processing delay
            await asyncio.sleep(random.uniform(2.0, 5.0))
            
            transaction_id = str(uuid.uuid4())
            
            # Calculate fees (mobile money providers charge fees)
            fee_rate = {
                MobileMoneyProvider.MPESA: 0.02,      # 2%
                MobileMoneyProvider.AIRTEL_MONEY: 0.025, # 2.5%
                MobileMoneyProvider.MTN_MONEY: 0.03,   # 3%
                MobileMoneyProvider.TIGO_PESA: 0.025   # 2.5%
            }
            
            rate = fee_rate.get(provider, 0.02)
            fee = amount * Decimal(str(rate))
            min_fee = Decimal("10.00")  # Minimum fee in local currency
            max_fee = Decimal("500.00")  # Maximum fee
            
            calculated_fee = min(max(fee, min_fee), max_fee)
            net_amount = amount - calculated_fee
            
            # Most transactions succeed
            success = random.random() < 0.92
            
            if success:
                status = "completed"
                result = {
                    "transaction_id": transaction_id,
                    "status": status,
                    "sender_phone": sender_phone,
                    "recipient_phone": self._mask_phone_number(recipient_phone),
                    "amount": float(amount),
                    "fee": float(calculated_fee),
                    "net_amount": float(net_amount),
                    "currency": currency.upper(),
                    "provider": provider.value,
                    "reference": reference or f"MM_{transaction_id[:8]}",
                    "confirmation_code": f"MP{random.randint(100000000, 999999999)}",
                    "processed_at": datetime.now(UTC).isoformat(),
                    "provider_reference": f"{provider.value.upper()}_{uuid.uuid4().hex[:10]}",
                    "failure_reason": None
                }
            else:
                # Simulate transaction failure
                failure_reasons = [
                    "Recipient phone not registered",
                    "Insufficient balance",
                    "Daily transaction limit exceeded",
                    "Service temporarily unavailable",
                    "Invalid recipient details"
                ]
                
                result = {
                    "transaction_id": transaction_id,
                    "status": "failed",
                    "sender_phone": sender_phone,
                    "recipient_phone": self._mask_phone_number(recipient_phone),
                    "amount": float(amount),
                    "fee": 0.0,
                    "net_amount": 0.0,
                    "currency": currency.upper(),
                    "provider": provider.value,
                    "reference": reference or f"MM_{transaction_id[:8]}",
                    "confirmation_code": None,
                    "processed_at": datetime.now(UTC).isoformat(),
                    "provider_reference": None,
                    "failure_reason": random.choice(failure_reasons)
                }
            
            # Store transaction
            self.transactions[transaction_id] = result
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MobileMoney",
                operation="send_money",
                duration_ms=duration_ms,
                success=success
            )
            
            return result
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MobileMoney",
                operation="send_money",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("MobileMoney", "send_money", str(e))
    
    async def check_balance(self, phone_number: str, provider: MobileMoneyProvider) -> Dict[str, Any]:
        """Check mobile money wallet balance."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate API delay
            await asyncio.sleep(random.uniform(1.0, 3.0))
            
            # Simulate occasional service unavailability
            if random.random() < 0.05:  # 5% failure rate
                raise ExternalServiceException("MobileMoney", "check_balance", "Service temporarily unavailable")
            
            # Mock balance data
            balance_data = {
                "phone_number": self._mask_phone_number(phone_number),
                "provider": provider.value,
                "available_balance": float(Decimal(str(random.uniform(100, 10000)))),
                "pending_balance": float(Decimal(str(random.uniform(0, 500)))),
                "currency": "KES" if provider == MobileMoneyProvider.MPESA else "UGX",
                "account_status": "active",
                "daily_limit": 150000.0,
                "monthly_limit": 1000000.0,
                "daily_used": float(Decimal(str(random.uniform(0, 50000)))),
                "monthly_used": float(Decimal(str(random.uniform(0, 300000)))),
                "last_transaction": (datetime.now(UTC) - timedelta(hours=random.randint(1, 72))).isoformat(),
                "checked_at": datetime.now(UTC).isoformat()
            }
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MobileMoney",
                operation="check_balance",
                duration_ms=duration_ms,
                success=True
            )
            
            return balance_data
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MobileMoney",
                operation="check_balance",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            if isinstance(e, ExternalServiceException):
                raise
            raise ExternalServiceException("MobileMoney", "check_balance", str(e))
    
    async def verify_phone_number(self, phone_number: str, provider: MobileMoneyProvider) -> Dict[str, Any]:
        """Verify if phone number is registered with mobile money provider."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate verification delay
            await asyncio.sleep(random.uniform(1.5, 3.5))
            
            # Most phone numbers are valid
            is_registered = random.random() < 0.85
            
            result = {
                "phone_number": self._mask_phone_number(phone_number),
                "provider": provider.value,
                "is_registered": is_registered,
                "account_status": "active" if is_registered else "not_found",
                "verified_at": datetime.now(UTC).isoformat()
            }
            
            if is_registered:
                # Mock account holder information (limited for privacy)
                result["account_holder"] = {
                    "name_initials": f"{random.choice('ABCDEFGHIJK')}.{random.choice('ABCDEFGHIJK')}.",
                    "registration_date": (datetime.now(UTC) - timedelta(days=random.randint(30, 1000))).isoformat()
                }
            else:
                result["error_message"] = "Phone number not registered with mobile money service"
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MobileMoney",
                operation="verify_phone_number",
                duration_ms=duration_ms,
                success=is_registered
            )
            
            return result
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MobileMoney",
                operation="verify_phone_number",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("MobileMoney", "verify_phone_number", str(e))
    
    async def get_transaction_status(self, transaction_id: str) -> Dict[str, Any]:
        """Get mobile money transaction status."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate API delay
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            if transaction_id not in self.transactions:
                # Generate mock transaction if not found
                transaction = {
                    "transaction_id": transaction_id,
                    "status": random.choice(["completed", "pending", "failed"]),
                    "amount": float(Decimal(str(random.uniform(100, 5000)))),
                    "currency": "KES",
                    "provider": random.choice(list(MobileMoneyProvider)).value,
                    "processed_at": (datetime.now(UTC) - timedelta(hours=random.randint(1, 24))).isoformat(),
                    "reference": f"MM_{transaction_id[:8]}"
                }
                self.transactions[transaction_id] = transaction
            
            transaction = self.transactions[transaction_id]
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MobileMoney",
                operation="get_transaction_status",
                duration_ms=duration_ms,
                success=True
            )
            
            return transaction
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MobileMoney",
                operation="get_transaction_status",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("MobileMoney", "get_transaction_status", str(e))
    
    async def get_providers_for_country(self, country_code: str) -> List[Dict[str, Any]]:
        """Get available mobile money providers for a country."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate API delay
            await asyncio.sleep(random.uniform(0.3, 1.0))
            
            # Mock provider data by country
            providers_by_country = {
                "KE": [
                    {
                        "provider": MobileMoneyProvider.MPESA.value,
                        "name": "M-Pesa",
                        "currency": "KES",
                        "supported_operations": ["send_money", "receive_money", "pay_bill", "buy_airtime"],
                        "daily_limit": 150000.0,
                        "monthly_limit": 1000000.0,
                        "min_transaction": 10.0,
                        "max_transaction": 150000.0
                    }
                ],
                "UG": [
                    {
                        "provider": MobileMoneyProvider.MTN_MONEY.value,
                        "name": "MTN Mobile Money",
                        "currency": "UGX",
                        "supported_operations": ["send_money", "receive_money", "pay_bill"],
                        "daily_limit": 5000000.0,
                        "monthly_limit": 50000000.0,
                        "min_transaction": 500.0,
                        "max_transaction": 2000000.0
                    },
                    {
                        "provider": MobileMoneyProvider.AIRTEL_MONEY.value,
                        "name": "Airtel Money",
                        "currency": "UGX", 
                        "supported_operations": ["send_money", "receive_money"],
                        "daily_limit": 3000000.0,
                        "monthly_limit": 30000000.0,
                        "min_transaction": 500.0,
                        "max_transaction": 1500000.0
                    }
                ],
                "TZ": [
                    {
                        "provider": MobileMoneyProvider.TIGO_PESA.value,
                        "name": "Tigo Pesa",
                        "currency": "TZS",
                        "supported_operations": ["send_money", "receive_money", "pay_bill"],
                        "daily_limit": 2000000.0,
                        "monthly_limit": 20000000.0,
                        "min_transaction": 1000.0,
                        "max_transaction": 1000000.0
                    }
                ]
            }
            
            providers = providers_by_country.get(country_code.upper(), [])
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MobileMoney",
                operation="get_providers_for_country",
                duration_ms=duration_ms,
                success=True
            )
            
            return providers
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MobileMoney",
                operation="get_providers_for_country",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("MobileMoney", "get_providers_for_country", str(e))
    
    async def request_money(
        self,
        requester_phone: str,
        payer_phone: str,
        amount: Decimal,
        currency: str = "KES",
        provider: MobileMoneyProvider = MobileMoneyProvider.MPESA,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send money request to another user."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate processing delay
            await asyncio.sleep(random.uniform(1.0, 2.5))
            
            request_id = str(uuid.uuid4())
            
            # Most requests are sent successfully
            success = random.random() < 0.95
            
            if success:
                # Request will expire in 24 hours
                expires_at = datetime.now(UTC) + timedelta(hours=24)
                
                result = {
                    "request_id": request_id,
                    "status": "sent",
                    "requester_phone": self._mask_phone_number(requester_phone),
                    "payer_phone": self._mask_phone_number(payer_phone),
                    "amount": float(amount),
                    "currency": currency.upper(),
                    "provider": provider.value,
                    "description": description or f"Money request from {self._mask_phone_number(requester_phone)}",
                    "created_at": datetime.now(UTC).isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "provider_reference": f"REQ_{uuid.uuid4().hex[:10]}",
                    "failure_reason": None
                }
            else:
                failure_reasons = [
                    "Recipient phone not registered",
                    "Service temporarily unavailable",
                    "Invalid request amount",
                    "Request limit exceeded"
                ]
                
                result = {
                    "request_id": request_id,
                    "status": "failed",
                    "requester_phone": self._mask_phone_number(requester_phone),
                    "payer_phone": self._mask_phone_number(payer_phone),
                    "amount": float(amount),
                    "currency": currency.upper(),
                    "provider": provider.value,
                    "description": description,
                    "created_at": datetime.now(UTC).isoformat(),
                    "expires_at": None,
                    "provider_reference": None,
                    "failure_reason": random.choice(failure_reasons)
                }
            
            # Store request
            self.transactions[request_id] = result
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MobileMoney",
                operation="request_money",
                duration_ms=duration_ms,
                success=success
            )
            
            return result
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MobileMoney",
                operation="request_money",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("MobileMoney", "request_money", str(e))
    
    async def calculate_fees(
        self,
        amount: Decimal,
        transaction_type: TransactionType,
        provider: MobileMoneyProvider,
        currency: str = "KES"
    ) -> Dict[str, Any]:
        """Calculate mobile money transaction fees."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate API delay
            await asyncio.sleep(random.uniform(0.2, 0.8))
            
            # Mock fee structures by provider and transaction type
            fee_structures = {
                MobileMoneyProvider.MPESA: {
                    TransactionType.SEND_MONEY: {"rate": 0.02, "min": 10.0, "max": 500.0},
                    TransactionType.WITHDRAW_CASH: {"rate": 0.015, "min": 20.0, "max": 300.0},
                    TransactionType.PAY_BILL: {"rate": 0.01, "min": 5.0, "max": 100.0}
                },
                MobileMoneyProvider.MTN_MONEY: {
                    TransactionType.SEND_MONEY: {"rate": 0.03, "min": 500.0, "max": 15000.0},
                    TransactionType.WITHDRAW_CASH: {"rate": 0.025, "min": 1000.0, "max": 10000.0}
                }
            }
            
            provider_fees = fee_structures.get(provider, fee_structures[MobileMoneyProvider.MPESA])
            transaction_fees = provider_fees.get(transaction_type, provider_fees[TransactionType.SEND_MONEY])
            
            # Calculate fee
            fee_amount = amount * Decimal(str(transaction_fees["rate"]))
            min_fee = Decimal(str(transaction_fees["min"]))
            max_fee = Decimal(str(transaction_fees["max"]))
            
            final_fee = min(max(fee_amount, min_fee), max_fee)
            net_amount = amount - final_fee
            
            result = {
                "amount": float(amount),
                "fee": float(final_fee),
                "net_amount": float(net_amount),
                "currency": currency.upper(),
                "provider": provider.value,
                "transaction_type": transaction_type.value,
                "fee_breakdown": {
                    "base_rate": transaction_fees["rate"] * 100,  # Convert to percentage
                    "minimum_fee": transaction_fees["min"],
                    "maximum_fee": transaction_fees["max"],
                    "calculated_fee": float(fee_amount),
                    "applied_fee": float(final_fee)
                },
                "calculated_at": datetime.now(UTC).isoformat()
            }
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MobileMoney",
                operation="calculate_fees",
                duration_ms=duration_ms,
                success=True
            )
            
            return result
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MobileMoney",
                operation="calculate_fees",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("MobileMoney", "calculate_fees", str(e))
    
    def _mask_phone_number(self, phone_number: str) -> str:
        """Mask phone number for privacy."""
        if len(phone_number) <= 4:
            return "*" * len(phone_number)
        
        # Show country code and last 3 digits
        if phone_number.startswith("+"):
            return f"{phone_number[:4]}****{phone_number[-3:]}"
        else:
            return f"****{phone_number[-3:]}"


# Global client instance
_mobile_money_client: Optional[MockMobileMoneyClient] = None


def get_mobile_money_client() -> MockMobileMoneyClient:
    """Get the global mobile money client instance."""
    global _mobile_money_client
    
    if _mobile_money_client is None:
        from ..config.settings import get_settings
        settings = get_settings()
        _mobile_money_client = MockMobileMoneyClient(
            base_url=settings.mobile_money_url,
            timeout=settings.mobile_money_timeout
        )
    
    return _mobile_money_client
