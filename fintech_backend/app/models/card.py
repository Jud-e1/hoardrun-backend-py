"""
Card management models for the fintech backend.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


class CardType(str, Enum):
    """Enumeration of card types."""
    DEBIT = "debit"
    CREDIT = "credit"
    PREPAID = "prepaid"
    VIRTUAL = "virtual"
    BUSINESS = "business"


class CardStatus(str, Enum):
    """Enumeration of card statuses."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"
    EXPIRED = "expired"
    PENDING = "pending"
    CANCELLED = "cancelled"


class CardNetwork(str, Enum):
    """Card network providers."""
    VISA = "visa"
    MASTERCARD = "mastercard"
    AMERICAN_EXPRESS = "american_express"
    DISCOVER = "discover"
    UNIONPAY = "unionpay"


class TransactionType(str, Enum):
    """Card transaction types."""
    PURCHASE = "purchase"
    WITHDRAWAL = "withdrawal"
    REFUND = "refund"
    AUTHORIZATION = "authorization"
    REVERSAL = "reversal"
    FEE = "fee"


class MerchantCategory(str, Enum):
    """Merchant category codes."""
    GROCERY = "grocery"
    GAS_STATION = "gas_station"
    RESTAURANT = "restaurant"
    RETAIL = "retail"
    ONLINE = "online"
    ATM = "atm"
    TRAVEL = "travel"
    ENTERTAINMENT = "entertainment"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    OTHER = "other"


class Card(BaseModel):
    """Card model representing a payment card."""
    id: Optional[str] = Field(None, description="Unique identifier")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    card_id: str = Field(..., description="Unique card identifier")
    account_id: str = Field(..., description="Associated account ID")
    user_id: str = Field(..., description="Card holder user ID")
    
    # Card details
    card_type: CardType = Field(..., description="Type of card")
    card_network: CardNetwork = Field(..., description="Card network provider")
    card_number_masked: str = Field(..., description="Masked card number (e.g., **** **** **** 1234)")
    card_holder_name: str = Field(..., description="Name on the card")
    
    # Expiration and security
    expiry_month: int = Field(..., ge=1, le=12, description="Expiration month")
    expiry_year: int = Field(..., description="Expiration year")
    
    # Status and settings
    status: CardStatus = Field(default=CardStatus.ACTIVE, description="Card status")
    is_primary: bool = Field(default=False, description="Whether this is the primary card")
    is_contactless_enabled: bool = Field(default=True, description="Contactless payments enabled")
    is_online_enabled: bool = Field(default=True, description="Online transactions enabled")
    is_international_enabled: bool = Field(default=False, description="International transactions enabled")
    
    # Limits
    daily_limit: Decimal = Field(default=Decimal("1000.00"), description="Daily spending limit")
    monthly_limit: Decimal = Field(default=Decimal("5000.00"), description="Monthly spending limit")
    atm_daily_limit: Decimal = Field(default=Decimal("500.00"), description="Daily ATM withdrawal limit")
    single_transaction_limit: Decimal = Field(default=Decimal("2000.00"), description="Single transaction limit")
    
    # Usage tracking
    current_daily_spent: Decimal = Field(default=Decimal("0.00"), description="Amount spent today")
    current_monthly_spent: Decimal = Field(default=Decimal("0.00"), description="Amount spent this month")
    last_used_at: Optional[datetime] = Field(None, description="Last transaction timestamp")
    
    # Metadata
    issued_date: date = Field(..., description="Card issuance date")
    activation_date: Optional[date] = Field(None, description="Card activation date")
    pin_set: bool = Field(default=False, description="Whether PIN has been set")
    
    @validator('expiry_year')
    def validate_expiry_year(cls, v):
        """Ensure expiry year is reasonable."""
        current_year = datetime.now().year
        if v < current_year or v > current_year + 10:
            raise ValueError("Invalid expiry year")
        return v
    
    @property
    def is_expired(self) -> bool:
        """Check if card is expired."""
        now = datetime.now()
        return (self.expiry_year < now.year or 
                (self.expiry_year == now.year and self.expiry_month < now.month))
    
    @property
    def remaining_daily_limit(self) -> Decimal:
        """Calculate remaining daily spending limit."""
        return max(Decimal("0"), self.daily_limit - self.current_daily_spent)
    
    @property
    def remaining_monthly_limit(self) -> Decimal:
        """Calculate remaining monthly spending limit."""
        return max(Decimal("0"), self.monthly_limit - self.current_monthly_spent)


class CardTransaction(BaseModel):
    """Card transaction model."""
    id: Optional[str] = Field(None, description="Unique identifier")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    transaction_id: str = Field(..., description="Unique transaction identifier")
    card_id: str = Field(..., description="Card identifier")
    account_id: str = Field(..., description="Associated account ID")
    
    # Transaction details
    transaction_type: TransactionType = Field(..., description="Type of transaction")
    amount: Decimal = Field(..., description="Transaction amount")
    currency: str = Field(default="USD", description="Transaction currency")
    
    # Merchant information
    merchant_name: str = Field(..., description="Merchant name")
    merchant_category: MerchantCategory = Field(..., description="Merchant category")
    merchant_id: Optional[str] = Field(None, description="Merchant identifier")
    
    # Location and timing
    transaction_date: datetime = Field(..., description="Transaction timestamp")
    location_city: Optional[str] = Field(None, description="Transaction city")
    location_country: Optional[str] = Field(None, description="Transaction country")
    
    # Processing details
    authorization_code: Optional[str] = Field(None, description="Authorization code")
    reference_number: str = Field(..., description="Transaction reference")
    processing_fee: Decimal = Field(default=Decimal("0.00"), description="Processing fee")
    
    # Status
    status: str = Field(default="completed", description="Transaction status")
    is_disputed: bool = Field(default=False, description="Whether transaction is disputed")
    
    # Security
    is_chip_transaction: bool = Field(default=True, description="Chip transaction")
    is_contactless: bool = Field(default=False, description="Contactless transaction")
    is_online: bool = Field(default=False, description="Online transaction")


class CardLimit(BaseModel):
    """Card spending limits configuration."""
    limit_type: str = Field(..., description="Type of limit (daily, monthly, single)")
    amount: Decimal = Field(..., ge=0, description="Limit amount")
    currency: str = Field(default="USD", description="Limit currency")
    is_active: bool = Field(default=True, description="Whether limit is active")


class CardSecurity(BaseModel):
    """Card security settings."""
    is_locked: bool = Field(default=False, description="Card temporarily locked")
    failed_pin_attempts: int = Field(default=0, description="Failed PIN attempts count")
    last_failed_attempt: Optional[datetime] = Field(None, description="Last failed PIN attempt")
    security_alerts_enabled: bool = Field(default=True, description="Security alerts enabled")
    transaction_notifications: bool = Field(default=True, description="Transaction notifications")
    international_block: bool = Field(default=True, description="Block international transactions")
    online_block: bool = Field(default=False, description="Block online transactions")
    atm_block: bool = Field(default=False, description="Block ATM transactions")


# Request models
class CardCreateRequest(BaseModel):
    """Request model for creating a new card."""
    account_id: str = Field(..., description="Account to link the card to")
    card_type: CardType = Field(..., description="Type of card to create")
    card_holder_name: str = Field(..., min_length=1, max_length=100, description="Name for the card")
    daily_limit: Optional[Decimal] = Field(None, ge=0, description="Daily spending limit")
    monthly_limit: Optional[Decimal] = Field(None, ge=0, description="Monthly spending limit")
    is_international_enabled: bool = Field(default=False, description="Enable international transactions")


class CardUpdateRequest(BaseModel):
    """Request model for updating card settings."""
    card_holder_name: Optional[str] = Field(None, min_length=1, max_length=100)
    daily_limit: Optional[Decimal] = Field(None, ge=0)
    monthly_limit: Optional[Decimal] = Field(None, ge=0)
    atm_daily_limit: Optional[Decimal] = Field(None, ge=0)
    single_transaction_limit: Optional[Decimal] = Field(None, ge=0)
    is_contactless_enabled: Optional[bool] = None
    is_online_enabled: Optional[bool] = None
    is_international_enabled: Optional[bool] = None


class CardStatusUpdateRequest(BaseModel):
    """Request model for updating card status."""
    status: CardStatus = Field(..., description="New card status")
    reason: Optional[str] = Field(None, max_length=200, description="Reason for status change")


class CardPinRequest(BaseModel):
    """Request model for PIN operations."""
    current_pin: Optional[str] = Field(None, min_length=4, max_length=6, description="Current PIN")
    new_pin: str = Field(..., min_length=4, max_length=6, description="New PIN")
    confirm_pin: str = Field(..., min_length=4, max_length=6, description="Confirm new PIN")
    
    @validator('confirm_pin')
    def validate_pin_match(cls, v, values):
        if 'new_pin' in values and v != values['new_pin']:
            raise ValueError("PIN confirmation does not match")
        return v


class CardTransactionQuery(BaseModel):
    """Request model for querying card transactions."""
    start_date: Optional[date] = Field(None, description="Start date for transaction search")
    end_date: Optional[date] = Field(None, description="End date for transaction search")
    transaction_type: Optional[TransactionType] = Field(None, description="Filter by transaction type")
    merchant_category: Optional[MerchantCategory] = Field(None, description="Filter by merchant category")
    min_amount: Optional[Decimal] = Field(None, ge=0, description="Minimum transaction amount")
    max_amount: Optional[Decimal] = Field(None, ge=0, description="Maximum transaction amount")
    limit: int = Field(default=50, ge=1, le=500, description="Number of transactions to return")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")


# Response models
class CardListResponse(BaseModel):
    """Response model for card listing."""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(default="Success", description="Response message")
    cards: List[Card] = Field(..., description="List of user cards")
    total_count: int = Field(..., description="Total number of cards")
    primary_card_id: Optional[str] = Field(None, description="Primary card identifier")


class CardResponse(BaseModel):
    """Response model for single card operations."""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(default="Success", description="Response message")
    card: Card = Field(..., description="Card details")


class CardCreatedResponse(BaseModel):
    """Response model for card creation."""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(default="Card created successfully", description="Response message")
    card: Card = Field(..., description="Created card details")
    delivery_info: Dict[str, str] = Field(..., description="Card delivery information")
    activation_required: bool = Field(default=True, description="Whether activation is required")


class CardTransactionResponse(BaseModel):
    """Response model for card transactions."""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(default="Success", description="Response message")
    transactions: List[CardTransaction] = Field(..., description="List of transactions")
    total_count: int = Field(..., description="Total number of transactions")
    summary: Dict[str, Decimal] = Field(..., description="Transaction summary")


class CardLimitsResponse(BaseModel):
    """Response model for card limits."""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(default="Success", description="Response message")
    card_id: str = Field(..., description="Card identifier")
    limits: Dict[str, CardLimit] = Field(..., description="Current card limits")
    usage: Dict[str, Decimal] = Field(..., description="Current usage against limits")


class CardSecurityResponse(BaseModel):
    """Response model for card security settings."""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(default="Success", description="Response message")
    card_id: str = Field(..., description="Card identifier")
    security: CardSecurity = Field(..., description="Security settings")


class CardActivationResponse(BaseModel):
    """Response model for card activation."""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(default="Card activated successfully", description="Response message")
    card_id: str = Field(..., description="Activated card identifier")
    activated_at: datetime = Field(..., description="Activation timestamp")
    pin_required: bool = Field(default=True, description="Whether PIN setup is required")


class CardStatementResponse(BaseModel):
    """Response model for card statements."""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(default="Success", description="Response message")
    card_id: str = Field(..., description="Card identifier")
    statement_period: Dict[str, date] = Field(..., description="Statement period")
    transactions: List[CardTransaction] = Field(..., description="Statement transactions")
    summary: Dict[str, Decimal] = Field(..., description="Statement summary")
    total_spent: Decimal = Field(..., description="Total amount spent in period")
    transaction_count: int = Field(..., description="Number of transactions")
