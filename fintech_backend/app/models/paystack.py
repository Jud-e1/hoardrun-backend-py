"""
Pydantic models for Paystack payment operations.
"""
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from enum import Enum

from pydantic import BaseModel, Field, EmailStr, validator
from .base import BaseResponse


class PaymentChannel(str, Enum):
    """Available payment channels."""
    CARD = "card"
    BANK = "bank"
    USSD = "ussd"
    QR = "qr"
    MOBILE_MONEY = "mobile_money"
    BANK_TRANSFER = "bank_transfer"


class TransactionStatus(str, Enum):
    """Transaction status options."""
    PENDING = "pending"
    ONGOING = "ongoing"
    SUCCESS = "success"
    FAILED = "failed"
    ABANDONED = "abandoned"
    CANCELLED = "cancelled"


class Currency(str, Enum):
    """Supported currencies."""
    GHS = "GHS"  # Ghanaian Cedi (Primary - enabled on test account)
    NGN = "NGN"  # Nigerian Naira
    USD = "USD"  # US Dollar
    ZAR = "ZAR"  # South African Rand
    KES = "KES"  # Kenyan Shilling


# Request Models
class InitializePaymentRequest(BaseModel):
    """Request model for initializing a payment."""
    email: EmailStr = Field(..., description="Customer's email address")
    amount: Decimal = Field(..., gt=0, description="Payment amount")
    currency: Currency = Field(default=Currency.GHS, description="Payment currency")
    reference: Optional[str] = Field(None, description="Unique payment reference")
    callback_url: Optional[str] = Field(None, description="URL to redirect after payment")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    channels: Optional[List[PaymentChannel]] = Field(None, description="Allowed payment channels")
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be greater than 0')
        return v
    
    @validator('reference')
    def validate_reference(cls, v):
        if v and len(v) > 100:
            raise ValueError('Reference must be 100 characters or less')
        return v


class VerifyPaymentRequest(BaseModel):
    """Request model for verifying a payment."""
    reference: str = Field(..., description="Payment reference to verify")


class ListTransactionsRequest(BaseModel):
    """Request model for listing transactions."""
    per_page: int = Field(default=50, ge=1, le=100, description="Number of transactions per page")
    page: int = Field(default=1, ge=1, description="Page number")
    customer: Optional[str] = Field(None, description="Customer ID or email")
    status: Optional[TransactionStatus] = Field(None, description="Transaction status filter")
    from_date: Optional[datetime] = Field(None, description="Start date filter")
    to_date: Optional[datetime] = Field(None, description="End date filter")


class WebhookRequest(BaseModel):
    """Request model for webhook payload."""
    event: str = Field(..., description="Webhook event type")
    data: Dict[str, Any] = Field(..., description="Webhook data")


# Response Models
class PaymentInitializationResponse(BaseResponse):
    """Response model for payment initialization."""
    authorization_url: str = Field(..., description="URL to redirect customer for payment")
    access_code: str = Field(..., description="Access code for the transaction")
    reference: str = Field(..., description="Transaction reference")


class TransactionData(BaseModel):
    """Transaction data model."""
    id: int = Field(..., description="Transaction ID")
    domain: str = Field(..., description="Domain")
    status: str = Field(..., description="Transaction status")
    reference: str = Field(..., description="Transaction reference")
    amount: int = Field(..., description="Amount in kobo")
    message: Optional[str] = Field(None, description="Transaction message")
    gateway_response: str = Field(..., description="Gateway response")
    paid_at: Optional[datetime] = Field(None, description="Payment date")
    created_at: datetime = Field(..., description="Creation date")
    channel: str = Field(..., description="Payment channel")
    currency: str = Field(..., description="Transaction currency")
    ip_address: Optional[str] = Field(None, description="Customer IP address")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Transaction metadata")
    fees: Optional[int] = Field(None, description="Transaction fees in kobo")
    customer: Optional[Dict[str, Any]] = Field(None, description="Customer data")
    authorization: Optional[Dict[str, Any]] = Field(None, description="Authorization data")
    plan: Optional[Dict[str, Any]] = Field(None, description="Plan data")


class PaymentVerificationResponse(BaseResponse):
    """Response model for payment verification."""
    transaction: TransactionData = Field(..., description="Transaction details")


class TransactionListResponse(BaseResponse):
    """Response model for transaction list."""
    transactions: List[TransactionData] = Field(..., description="List of transactions")
    meta: Dict[str, Any] = Field(..., description="Pagination metadata")


class WebhookResponse(BaseResponse):
    """Response model for webhook processing."""
    event_type: str = Field(..., description="Type of webhook event processed")
    transaction_reference: Optional[str] = Field(None, description="Transaction reference if applicable")


# Internal Models for Database Storage
class PaystackTransaction(BaseModel):
    """Internal model for storing Paystack transactions."""
    id: Optional[int] = None
    user_id: int = Field(..., description="User ID")
    paystack_reference: str = Field(..., description="Paystack transaction reference")
    paystack_transaction_id: Optional[int] = Field(None, description="Paystack transaction ID")
    amount: Decimal = Field(..., description="Transaction amount")
    currency: str = Field(..., description="Transaction currency")
    status: str = Field(..., description="Transaction status")
    channel: Optional[str] = Field(None, description="Payment channel")
    gateway_response: Optional[str] = Field(None, description="Gateway response message")
    paid_at: Optional[datetime] = Field(None, description="Payment completion time")
    fees: Optional[Decimal] = Field(None, description="Transaction fees")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Record update time")
    
    class Config:
        from_attributes = True


# Utility Models
class PaymentSummary(BaseModel):
    """Summary model for payment statistics."""
    total_amount: Decimal = Field(..., description="Total payment amount")
    total_fees: Decimal = Field(..., description="Total fees paid")
    transaction_count: int = Field(..., description="Number of transactions")
    success_rate: float = Field(..., description="Success rate percentage")
    currency: str = Field(..., description="Currency code")


class PaymentChannelStats(BaseModel):
    """Statistics for payment channels."""
    channel: str = Field(..., description="Payment channel")
    transaction_count: int = Field(..., description="Number of transactions")
    total_amount: Decimal = Field(..., description="Total amount processed")
    success_rate: float = Field(..., description="Success rate percentage")
