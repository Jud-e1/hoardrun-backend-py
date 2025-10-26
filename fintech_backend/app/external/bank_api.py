"""
Mock bank API client for account operations and banking services.
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

logger = get_logger("bank_api")


class AccountStatus(str, Enum):
    """Account status types."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    FROZEN = "frozen"
    CLOSED = "closed"


class TransactionStatus(str, Enum):
    """Transaction status types."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MockBankAPIClient:
    """Mock bank API client for banking operations."""
    
    def __init__(self, base_url: str = "https://mock-bank-api.com", timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout
    
    async def get_account_balance(self, account_id: str) -> Dict[str, Any]:
        """Get real-time account balance."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate API delay
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Simulate occasional service issues
            if random.random() < 0.05:  # 5% failure rate
                raise ExternalServiceException("BankAPI", "get_account_balance", "Temporary service unavailable")
            
            # Mock balance data
            balance_data = {
                "account_id": account_id,
                "available_balance": float(Decimal(str(random.uniform(1000, 50000)))),
                "current_balance": float(Decimal(str(random.uniform(1200, 52000)))),
                "pending_balance": float(Decimal(str(random.uniform(0, 500)))),
                "currency": "USD",
                "last_updated": datetime.now(UTC).isoformat(),
                "account_status": AccountStatus.ACTIVE.value
            }
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="BankAPI",
                operation="get_account_balance",
                duration_ms=duration_ms,
                success=True
            )
            
            return balance_data
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="BankAPI",
                operation="get_account_balance",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            if isinstance(e, ExternalServiceException):
                raise
            raise ExternalServiceException("BankAPI", "get_account_balance", str(e))
    
    async def validate_account(self, account_number: str, routing_number: Optional[str] = None) -> Dict[str, Any]:
        """Validate bank account details."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate validation delay
            await asyncio.sleep(random.uniform(1.0, 2.5))
            
            # Most accounts are valid
            is_valid = random.random() < 0.85
            
            result = {
                "account_number": account_number,
                "routing_number": routing_number,
                "is_valid": is_valid,
                "account_type": random.choice(["checking", "savings"]) if is_valid else None,
                "bank_name": random.choice(["Chase", "Bank of America", "Wells Fargo", "Citi"]) if is_valid else None,
                "account_status": AccountStatus.ACTIVE.value if is_valid else AccountStatus.CLOSED.value,
                "validated_at": datetime.now(UTC).isoformat()
            }
            
            if not is_valid:
                result["error_message"] = random.choice([
                    "Account not found",
                    "Invalid routing number",
                    "Account closed",
                    "Unable to verify account"
                ])
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="BankAPI",
                operation="validate_account",
                duration_ms=duration_ms,
                success=is_valid
            )
            
            return result
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="BankAPI",
                operation="validate_account",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("BankAPI", "validate_account", str(e))
    
    async def initiate_transfer(
        self,
        from_account: str,
        to_account: str,
        amount: Decimal,
        currency: str = "USD",
        reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """Initiate a bank transfer."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate processing delay
            await asyncio.sleep(random.uniform(1.5, 3.0))
            
            transfer_id = str(uuid.uuid4())
            
            # Most transfers succeed
            success = random.random() < 0.92
            
            if success:
                status = TransactionStatus.PENDING
                estimated_completion = datetime.now(UTC) + timedelta(hours=random.randint(1, 24))
                
                result = {
                    "transfer_id": transfer_id,
                    "status": status.value,
                    "from_account": from_account,
                    "to_account": to_account,
                    "amount": float(amount),
                    "currency": currency.upper(),
                    "reference": reference or f"TRF_{transfer_id[:8]}",
                    "initiated_at": datetime.now(UTC).isoformat(),
                    "estimated_completion": estimated_completion.isoformat(),
                    "bank_reference": f"BK_{uuid.uuid4().hex[:10]}",
                    "failure_reason": None
                }
            else:
                # Simulate transfer failure
                failure_reasons = [
                    "Insufficient funds",
                    "Account blocked",
                    "Invalid beneficiary account",
                    "Daily transfer limit exceeded",
                    "Bank system maintenance"
                ]
                
                result = {
                    "transfer_id": transfer_id,
                    "status": TransactionStatus.FAILED.value,
                    "from_account": from_account,
                    "to_account": to_account,
                    "amount": float(amount),
                    "currency": currency.upper(),
                    "reference": reference or f"TRF_{transfer_id[:8]}",
                    "initiated_at": datetime.now(UTC).isoformat(),
                    "estimated_completion": None,
                    "bank_reference": None,
                    "failure_reason": random.choice(failure_reasons)
                }
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="BankAPI",
                operation="initiate_transfer",
                duration_ms=duration_ms,
                success=success
            )
            
            return result
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="BankAPI",
                operation="initiate_transfer",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("BankAPI", "initiate_transfer", str(e))
    
    async def get_transfer_status(self, transfer_id: str) -> Dict[str, Any]:
        """Get the status of a transfer."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate API delay
            await asyncio.sleep(random.uniform(0.2, 0.8))
            
            # Mock transfer status progression
            statuses = [
                TransactionStatus.PENDING.value,
                TransactionStatus.PROCESSING.value, 
                TransactionStatus.COMPLETED.value
            ]
            
            current_status = random.choice(statuses)
            
            result = {
                "transfer_id": transfer_id,
                "status": current_status,
                "last_updated": datetime.now(UTC).isoformat(),
                "estimated_completion": (datetime.now(UTC) + timedelta(hours=random.randint(1, 12))).isoformat(),
                "tracking_steps": [
                    {
                        "step": "Transfer initiated",
                        "status": "completed",
                        "timestamp": (datetime.now(UTC) - timedelta(hours=2)).isoformat()
                    },
                    {
                        "step": "Bank processing",
                        "status": "completed" if current_status != TransactionStatus.PENDING.value else "pending",
                        "timestamp": (datetime.now(UTC) - timedelta(hours=1)).isoformat() if current_status != TransactionStatus.PENDING.value else None
                    },
                    {
                        "step": "Transfer completed",
                        "status": "completed" if current_status == TransactionStatus.COMPLETED.value else "pending",
                        "timestamp": datetime.now(UTC).isoformat() if current_status == TransactionStatus.COMPLETED.value else None
                    }
                ]
            }
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="BankAPI",
                operation="get_transfer_status",
                duration_ms=duration_ms,
                success=True
            )
            
            return result
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="BankAPI",
                operation="get_transfer_status",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("BankAPI", "get_transfer_status", str(e))
    
    async def generate_statement(
        self,
        account_id: str,
        start_date: datetime,
        end_date: datetime,
        format_type: str = "pdf"
    ) -> Dict[str, Any]:
        """Generate account statement."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate statement generation delay
            await asyncio.sleep(random.uniform(2.0, 5.0))
            
            statement_id = str(uuid.uuid4())
            
            result = {
                "statement_id": statement_id,
                "account_id": account_id,
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "format": format_type,
                "generated_at": datetime.now(UTC).isoformat(),
                "download_url": f"{self.base_url}/statements/{statement_id}.{format_type}",
                "expires_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
                "file_size_bytes": random.randint(50000, 500000),
                "transaction_count": random.randint(10, 150),
                "status": "ready"
            }
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="BankAPI",
                operation="generate_statement",
                duration_ms=duration_ms,
                success=True
            )
            
            return result
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="BankAPI",
                operation="generate_statement",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("BankAPI", "generate_statement", str(e))
    
    async def get_supported_banks(self, country: str = "US") -> List[Dict[str, Any]]:
        """Get list of supported banks for transfers."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate API delay
            await asyncio.sleep(random.uniform(0.3, 1.0))
            
            # Mock bank data by country
            banks_by_country = {
                "US": [
                    {"code": "021000021", "name": "Chase Bank", "supports_instant": True},
                    {"code": "026009593", "name": "Bank of America", "supports_instant": True},
                    {"code": "121042882", "name": "Wells Fargo", "supports_instant": True},
                    {"code": "021001088", "name": "Citibank", "supports_instant": False},
                    {"code": "063103915", "name": "US Bank", "supports_instant": False}
                ],
                "KE": [
                    {"code": "KCB001", "name": "Kenya Commercial Bank", "supports_instant": True},
                    {"code": "EQT001", "name": "Equity Bank", "supports_instant": True},
                    {"code": "CBK001", "name": "Cooperative Bank", "supports_instant": False}
                ],
                "UG": [
                    {"code": "STB001", "name": "Stanbic Bank Uganda", "supports_instant": True},
                    {"code": "CEN001", "name": "Centenary Bank", "supports_instant": False}
                ]
            }
            
            banks = banks_by_country.get(country.upper(), [])
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="BankAPI",
                operation="get_supported_banks",
                duration_ms=duration_ms,
                success=True
            )
            
            return banks
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="BankAPI",
                operation="get_supported_banks",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("BankAPI", "get_supported_banks", str(e))
    
    async def verify_account_ownership(self, account_id: str, verification_data: Dict[str, Any]) -> Dict[str, Any]:
        """Verify account ownership through micro-deposits or other methods."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate verification delay
            await asyncio.sleep(random.uniform(2.0, 4.0))
            
            verification_id = str(uuid.uuid4())
            
            # Mock verification methods
            verification_methods = ["micro_deposits", "instant_verification", "manual_review"]
            method = random.choice(verification_methods)
            
            is_verified = random.random() < 0.88  # 88% verification success rate
            
            result = {
                "verification_id": verification_id,
                "account_id": account_id,
                "method": method,
                "status": "verified" if is_verified else "failed",
                "initiated_at": datetime.now(UTC).isoformat(),
                "verified_at": datetime.now(UTC).isoformat() if is_verified else None
            }
            
            if method == "micro_deposits" and is_verified:
                result["micro_deposits"] = [
                    float(Decimal(str(random.uniform(0.01, 0.99)))),
                    float(Decimal(str(random.uniform(0.01, 0.99))))
                ]
                result["verification_deadline"] = (datetime.now(UTC) + timedelta(days=2)).isoformat()
            
            if not is_verified:
                result["failure_reason"] = random.choice([
                    "Account owner name mismatch",
                    "Account closed",
                    "Insufficient account history",
                    "Manual verification required"
                ])
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="BankAPI",
                operation="verify_account_ownership",
                duration_ms=duration_ms,
                success=is_verified
            )
            
            return result
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="BankAPI",
                operation="verify_account_ownership",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("BankAPI", "verify_account_ownership", str(e))
    
    async def get_transaction_limits(self, account_id: str) -> Dict[str, Any]:
        """Get account transaction limits."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate API delay
            await asyncio.sleep(random.uniform(0.4, 1.2))
            
            # Mock limits based on account type
            account_types = ["checking", "savings", "premium_checking"]
            account_type = random.choice(account_types)
            
            base_limits = {
                "checking": {
                    "daily_transfer_limit": 10000.00,
                    "monthly_transfer_limit": 100000.00,
                    "daily_withdrawal_limit": 5000.00,
                    "monthly_withdrawal_limit": 50000.00
                },
                "savings": {
                    "daily_transfer_limit": 5000.00,
                    "monthly_transfer_limit": 50000.00,
                    "daily_withdrawal_limit": 1000.00,
                    "monthly_withdrawal_limit": 6000.00
                },
                "premium_checking": {
                    "daily_transfer_limit": 50000.00,
                    "monthly_transfer_limit": 500000.00,
                    "daily_withdrawal_limit": 10000.00,
                    "monthly_withdrawal_limit": 100000.00
                }
            }
            
            limits = base_limits.get(account_type, base_limits["checking"])
            
            result = {
                "account_id": account_id,
                "account_type": account_type,
                "limits": limits,
                "current_usage": {
                    "daily_transfers_used": float(Decimal(str(random.uniform(0, limits["daily_transfer_limit"] * 0.5)))),
                    "monthly_transfers_used": float(Decimal(str(random.uniform(0, limits["monthly_transfer_limit"] * 0.3)))),
                    "daily_withdrawals_used": float(Decimal(str(random.uniform(0, limits["daily_withdrawal_limit"] * 0.4)))),
                    "monthly_withdrawals_used": float(Decimal(str(random.uniform(0, limits["monthly_withdrawal_limit"] * 0.2))))
                },
                "reset_times": {
                    "daily_reset": (datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat(),
                    "monthly_reset": (datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0) + timedelta(days=32)).replace(day=1).isoformat()
                },
                "retrieved_at": datetime.now(UTC).isoformat()
            }
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="BankAPI",
                operation="get_transaction_limits",
                duration_ms=duration_ms,
                success=True
            )
            
            return result
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="BankAPI",
                operation="get_transaction_limits",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("BankAPI", "get_transaction_limits", str(e))


# Global client instance
_bank_api_client: Optional[MockBankAPIClient] = None


def get_bank_api_client() -> MockBankAPIClient:
    """Get the global bank API client instance."""
    global _bank_api_client
    
    if _bank_api_client is None:
        from ..config.settings import get_settings
        settings = get_settings()
        _bank_api_client = MockBankAPIClient(
            base_url=settings.bank_api_url,
            timeout=settings.bank_api_timeout
        )
    
    return _bank_api_client
