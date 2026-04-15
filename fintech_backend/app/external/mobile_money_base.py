"""
Shared base types for all mobile money provider clients.

Provider-specific clients (mtn_momo_api.py, etc.) import from here
to avoid redefining the same enums across multiple files.
"""
from enum import Enum
from decimal import Decimal
from datetime import datetime
from typing import Optional, Any, Dict


class MobileMoneyProvider(str, Enum):
    """Supported mobile money providers."""
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


class TransactionStatus(str, Enum):
    """Transaction status values shared across providers."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"
    CANCELLED = "cancelled"


class Currency(str, Enum):
    """Common currencies used in mobile money operations."""
    KES = "KES"   # Kenyan Shilling
    UGX = "UGX"   # Ugandan Shilling
    TZS = "TZS"   # Tanzanian Shilling
    GHS = "GHS"   # Ghanaian Cedi
    NGN = "NGN"   # Nigerian Naira
    USD = "USD"
    EUR = "EUR"


class MobileMoneyTransaction:
    """Lightweight data class for a completed transaction."""
    __slots__ = ("id", "provider", "type", "status", "amount", "currency",
                 "sender_phone", "recipient_phone", "reference",
                 "created_at", "metadata")

    def __init__(
        self,
        id: str,
        provider: MobileMoneyProvider,
        type: TransactionType,
        status: TransactionStatus,
        amount: Decimal,
        currency: str,
        sender_phone: str,
        recipient_phone: str,
        reference: Optional[str] = None,
        created_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.id = id
        self.provider = provider
        self.type = type
        self.status = status
        self.amount = amount
        self.currency = currency
        self.sender_phone = sender_phone
        self.recipient_phone = recipient_phone
        self.reference = reference
        self.created_at = created_at or datetime.utcnow()
        self.metadata = metadata or {}
