"""
Mobile Money models for mobile payment integration.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from decimal import Decimal


class MobileMoneyProvider(str, Enum):
    """Mobile money provider enumeration."""
    MTN_MOMO = "mtn_momo"
    AIRTEL_MONEY = "airtel_money"
    VODAFONE_CASH = "vodafone_cash"
    TIGO_CASH = "tigo_cash"
    ORANGE_MONEY = "orange_money"
    MPESA = "mpesa"
    ECOCASH = "ecocash"
    MOBILE_MONEY = "mobile_money"


class TransactionType(str, Enum):
    """Transaction type enumeration."""
    SEND = "send"
    RECEIVE = "receive"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"


class TransactionStatus(str, Enum):
    """Transaction status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Currency(str, Enum):
    """Supported currency enumeration."""
    UGX = "UGX"  # Ugandan Shilling
    KES = "KES"  # Kenyan Shilling
    TZS = "TZS"  # Tanzanian Shilling
    GHS = "GHS"  # Ghanaian Cedi
    NGN = "NGN"  # Nigerian Naira
    ZAR = "ZAR"  # South African Rand
    USD = "USD"  # US Dollar
    EUR = "EUR"  # Euro


# Request Models
class MobileMoneyAccountRequest(BaseModel):
    """Mobile money account verification request."""
    provider: MobileMoneyProvider = Field(..., description="Mobile money provider")
    phone_number: str = Field(..., description="Phone number")
    country_code: str = Field(..., description="Country code (e.g., UG, KE)")
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        """Validate phone number format."""
        # Remove any spaces, dashes, or plus signs
        cleaned = v.replace(' ', '').replace('-', '').replace('+', '')
        if not cleaned.isdigit():
            raise ValueError('Phone number must contain only digits')
        if len(cleaned) < 9 or len(cleaned) > 15:
            raise ValueError('Phone number must be between 9 and 15 digits')
        return cleaned


class MobileMoneyTransferRequest(BaseModel):
    """Mobile money transfer request."""
    provider: MobileMoneyProvider = Field(..., description="Mobile money provider")
    recipient_phone: str = Field(..., description="Recipient phone number")
    amount: Decimal = Field(..., gt=0, description="Transfer amount")
    currency: Currency = Field(..., description="Currency code")
    reference: Optional[str] = Field(None, description="Transfer reference")
    description: Optional[str] = Field(None, max_length=200, description="Transfer description")
    
    @validator('amount')
    def validate_amount(cls, v):
        """Validate transfer amount."""
        if v <= 0:
            raise ValueError('Amount must be greater than 0')
        if v > 10000000:  # 10 million limit
            raise ValueError('Amount exceeds maximum transfer limit')
        return v
    
    @validator('recipient_phone')
    def validate_recipient_phone(cls, v):
        """Validate recipient phone number."""
        cleaned = v.replace(' ', '').replace('-', '').replace('+', '')
        if not cleaned.isdigit():
            raise ValueError('Phone number must contain only digits')
        if len(cleaned) < 9 or len(cleaned) > 15:
            raise ValueError('Phone number must be between 9 and 15 digits')
        return cleaned


class MobileMoneyReceiveRequest(BaseModel):
    """Mobile money receive request."""
    provider: MobileMoneyProvider = Field(..., description="Mobile money provider")
    sender_phone: str = Field(..., description="Sender phone number")
    amount: Decimal = Field(..., gt=0, description="Expected amount")
    currency: Currency = Field(..., description="Currency code")
    reference: Optional[str] = Field(None, description="Transaction reference")
    
    @validator('sender_phone')
    def validate_sender_phone(cls, v):
        """Validate sender phone number."""
        cleaned = v.replace(' ', '').replace('-', '').replace('+', '')
        if not cleaned.isdigit():
            raise ValueError('Phone number must contain only digits')
        if len(cleaned) < 9 or len(cleaned) > 15:
            raise ValueError('Phone number must be between 9 and 15 digits')
        return cleaned


class MobileMoneyDepositRequest(BaseModel):
    """Mobile money deposit request."""
    provider: MobileMoneyProvider = Field(..., description="Mobile money provider")
    phone_number: str = Field(..., description="Phone number")
    amount: Decimal = Field(..., gt=0, description="Deposit amount")
    currency: Currency = Field(..., description="Currency code")
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        """Validate phone number."""
        cleaned = v.replace(' ', '').replace('-', '').replace('+', '')
        if not cleaned.isdigit():
            raise ValueError('Phone number must contain only digits')
        if len(cleaned) < 9 or len(cleaned) > 15:
            raise ValueError('Phone number must be between 9 and 15 digits')
        return cleaned


# Response Models
class MobileMoneyProvider_Info(BaseModel):
    """Mobile money provider information."""
    provider: MobileMoneyProvider = Field(..., description="Provider code")
    name: str = Field(..., description="Provider display name")
    country: str = Field(..., description="Country code")
    currency: Currency = Field(..., description="Primary currency")
    logo_url: Optional[str] = Field(None, description="Provider logo URL")
    is_active: bool = Field(True, description="Provider availability status")
    min_amount: Decimal = Field(..., description="Minimum transaction amount")
    max_amount: Decimal = Field(..., description="Maximum transaction amount")
    fee_percentage: Decimal = Field(..., description="Transaction fee percentage")
    fee_fixed: Decimal = Field(..., description="Fixed transaction fee")
    
    class Config:
        from_attributes = True


class MobileMoneyTransaction(BaseModel):
    """Mobile money transaction model."""
    id: str = Field(..., description="Transaction ID")
    user_id: str = Field(..., description="User ID")
    provider: MobileMoneyProvider = Field(..., description="Mobile money provider")
    transaction_type: TransactionType = Field(..., description="Transaction type")
    status: TransactionStatus = Field(..., description="Transaction status")
    
    # Amount details
    amount: Decimal = Field(..., description="Transaction amount")
    currency: Currency = Field(..., description="Currency code")
    fee: Decimal = Field(..., description="Transaction fee")
    total_amount: Decimal = Field(..., description="Total amount including fees")
    
    # Participant details
    sender_phone: Optional[str] = Field(None, description="Sender phone number")
    recipient_phone: Optional[str] = Field(None, description="Recipient phone number")
    
    # Transaction details
    reference: Optional[str] = Field(None, description="Transaction reference")
    external_reference: Optional[str] = Field(None, description="Provider transaction reference")
    description: Optional[str] = Field(None, description="Transaction description")
    
    # Timestamps
    created_at: datetime = Field(..., description="Transaction creation time")
    updated_at: datetime = Field(..., description="Last update time")
    completed_at: Optional[datetime] = Field(None, description="Completion time")
    expires_at: Optional[datetime] = Field(None, description="Expiration time")
    
    # Metadata
    provider_response: Optional[Dict[str, Any]] = Field(None, description="Provider response data")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    retry_count: int = Field(0, description="Number of retry attempts")
    
    class Config:
        from_attributes = True


class MobileMoneyAccount(BaseModel):
    """Mobile money account model."""
    id: str = Field(..., description="Account ID")
    user_id: str = Field(..., description="User ID")
    provider: MobileMoneyProvider = Field(..., description="Mobile money provider")
    phone_number: str = Field(..., description="Masked phone number")
    country_code: str = Field(..., description="Country code")
    account_name: Optional[str] = Field(None, description="Account holder name")
    is_verified: bool = Field(False, description="Verification status")
    is_active: bool = Field(True, description="Account status")
    balance: Optional[Decimal] = Field(None, description="Account balance")
    currency: Currency = Field(..., description="Account currency")
    created_at: datetime = Field(..., description="Account creation time")
    updated_at: datetime = Field(..., description="Last update time")
    last_used_at: Optional[datetime] = Field(None, description="Last usage time")
    
    class Config:
        from_attributes = True


# Response Models
class MobileMoneyTransferResponse(BaseModel):
    """Mobile money transfer response."""
    success: bool = Field(True, description="Response success status")
    message: str = Field(..., description="Response message")
    data: Dict[str, MobileMoneyTransaction] = Field(..., description="Transaction data")


class MobileMoneyReceiveResponse(BaseModel):
    """Mobile money receive response."""
    success: bool = Field(True, description="Response success status")
    message: str = Field(..., description="Response message")
    data: Dict[str, MobileMoneyTransaction] = Field(..., description="Transaction data")


class MobileMoneyProvidersResponse(BaseModel):
    """Mobile money providers response."""
    success: bool = Field(True, description="Response success status")
    message: str = Field(..., description="Response message")
    data: Dict[str, List[MobileMoneyProvider_Info]] = Field(..., description="Providers data")


class MobileMoneyAccountResponse(BaseModel):
    """Mobile money account response."""
    success: bool = Field(True, description="Response success status")
    message: str = Field(..., description="Response message")
    data: Dict[str, MobileMoneyAccount] = Field(..., description="Account data")


class MobileMoneyTransactionListResponse(BaseModel):
    """Mobile money transaction list response."""
    success: bool = Field(True, description="Response success status")
    message: str = Field(..., description="Response message")
    data: Dict[str, List[MobileMoneyTransaction]] = Field(..., description="Transactions data")
    total: int = Field(..., description="Total number of transactions")
    page: int = Field(1, description="Current page")
    per_page: int = Field(20, description="Items per page")


# Database Models
class MobileMoneyTransactionCreate(BaseModel):
    """Mobile money transaction creation model."""
    user_id: str
    provider: MobileMoneyProvider
    transaction_type: TransactionType
    amount: Decimal
    currency: Currency
    sender_phone: Optional[str] = None
    recipient_phone: Optional[str] = None
    reference: Optional[str] = None
    description: Optional[str] = None


class MobileMoneyTransactionUpdate(BaseModel):
    """Mobile money transaction update model."""
    status: Optional[TransactionStatus] = None
    external_reference: Optional[str] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    provider_response: Optional[Dict[str, Any]] = None
    retry_count: Optional[int] = None
    updated_at: Optional[datetime] = None


class MobileMoneyAccountCreate(BaseModel):
    """Mobile money account creation model."""
    user_id: str
    provider: MobileMoneyProvider
    phone_number_encrypted: str
    country_code: str
    account_name: Optional[str] = None
    currency: Currency


class MobileMoneyAccountUpdate(BaseModel):
    """Mobile money account update model."""
    account_name: Optional[str] = None
    is_verified: Optional[bool] = None
    is_active: Optional[bool] = None
    balance: Optional[Decimal] = None
    last_used_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# Utility Models
class MobileMoneyTransactionFilter(BaseModel):
    """Mobile money transaction filter model."""
    provider: Optional[MobileMoneyProvider] = Field(None, description="Filter by provider")
    transaction_type: Optional[TransactionType] = Field(None, description="Filter by type")
    status: Optional[TransactionStatus] = Field(None, description="Filter by status")
    currency: Optional[Currency] = Field(None, description="Filter by currency")
    date_from: Optional[datetime] = Field(None, description="Filter from date")
    date_to: Optional[datetime] = Field(None, description="Filter to date")
    min_amount: Optional[Decimal] = Field(None, description="Minimum amount filter")
    max_amount: Optional[Decimal] = Field(None, description="Maximum amount filter")
    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(20, ge=1, le=100, description="Items per page")


class MobileMoneyStats(BaseModel):
    """Mobile money statistics model."""
    total_transactions: int = Field(..., description="Total number of transactions")
    successful_transactions: int = Field(..., description="Number of successful transactions")
    failed_transactions: int = Field(..., description="Number of failed transactions")
    pending_transactions: int = Field(..., description="Number of pending transactions")
    total_volume: Decimal = Field(..., description="Total transaction volume")
    total_fees: Decimal = Field(..., description="Total fees paid")
    by_provider: Dict[str, int] = Field(..., description="Transactions by provider")
    by_type: Dict[str, int] = Field(..., description="Transactions by type")
    by_currency: Dict[str, Decimal] = Field(..., description="Volume by currency")
    success_rate: float = Field(..., description="Transaction success rate")


class MobileMoneyFeeCalculation(BaseModel):
    """Mobile money fee calculation model."""
    amount: Decimal = Field(..., description="Transaction amount")
    currency: Currency = Field(..., description="Currency")
    provider: MobileMoneyProvider = Field(..., description="Provider")
    fee_percentage: Decimal = Field(..., description="Fee percentage")
    fee_fixed: Decimal = Field(..., description="Fixed fee")
    total_fee: Decimal = Field(..., description="Total calculated fee")
    total_amount: Decimal = Field(..., description="Total amount including fee")
