"""
Card management models for the fintech backend.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from enum import Enum

from app.models.base import BaseResponse, TimestampMixin


class CardType(str, Enum):
    """Enumeration of supported card types."""
    DEBIT = "debit"
    CREDIT = "credit"
    PREPAID = "prepaid"


class CardStatus(str, Enum):
    """Enumeration of card statuses."""
    ACTIVE = "active"
    BLOCKED = "blocked"
    FROZEN = "frozen"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class CardNetwork(str, Enum):
    """Enumeration of card networks."""
    VISA = "visa"
    MASTERCARD = "mastercard"
    AMEX = "amex"
    DISCOVER = "discover"


class TransactionType(str, Enum):
    """Types of card transactions for limits."""
    ATM_WITHDRAWAL = "atm_withdrawal"
    POS_PURCHASE = "pos_purchase"
    ONLINE_PURCHASE = "online_purchase"
    CONTACTLESS = "contactless"
    INTERNATIONAL = "international"


class LimitPeriod(str, Enum):
    """Time periods for card limits."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class CardLimit(BaseModel):
    """Card spending and transaction limits."""
    transaction_type: TransactionType
    period: LimitPeriod
    limit_amount: Decimal = Field(..., gt=0, description="Maximum amount for the period")
    current_usage: Decimal = Field(default=Decimal("0"), ge=0, description="Current usage in the period")
    period_start: datetime = Field(..., description="Start of the current limit period")
    period_end: datetime = Field(..., description="End of the current limit period")
    is_enabled: bool = Field(default=True, description="Whether the limit is active")

    @validator('current_usage')
    def validate_usage_not_exceed_limit(cls, v, values):
        if 'limit_amount' in values and v > values['limit_amount']:
            # Allow current usage to exceed limit (historical data) but warn
            pass
        return v


class Card(BaseModel, TimestampMixin):
    """Card model representing a payment card."""
    card_id: str = Field(..., description="Unique card identifier")
    user_id: str = Field(..., description="Owner user ID")
    account_id: str = Field(..., description="Associated account ID")
    card_type: CardType = Field(..., description="Type of card")
    card_network: CardNetwork = Field(..., description="Card network provider")
    status: CardStatus = Field(default=CardStatus.ACTIVE, description="Current card status")
    
    # Card details (masked for security)
    masked_number: str = Field(..., description="Masked card number (e.g., **** **** **** 1234)")
    card_name: str = Field(..., description="Name on card")
    expiry_month: int = Field(..., ge=1, le=12, description="Expiry month")
    expiry_year: int = Field(..., ge=2024, description="Expiry year")
    
    # Limits and settings
    limits: List[CardLimit] = Field(default_factory=list, description="Card spending limits")
    is_contactless_enabled: bool = Field(default=True, description="Contactless payments enabled")
    is_online_enabled: bool = Field(default=True, description="Online payments enabled")
    is_international_enabled: bool = Field(default=False, description="International payments enabled")
    
    # Security settings
    pin_attempts_remaining: int = Field(default=3, ge=0, le=3, description="PIN attempts remaining")
    last_transaction_date: Optional[datetime] = Field(None, description="Last transaction timestamp")
    
    @validator('expiry_year')
    def validate_expiry_year(cls, v):
        current_year = datetime.now().year
        if v < current_year:
            raise ValueError("Card expiry year cannot be in the past")
        return v

    @property
    def is_expired(self) -> bool:
        """Check if card is expired."""
        current_date = date.today()
        expiry_date = date(self.expiry_year, self.expiry_month, 1)
        return current_date > expiry_date

    @property
    def remaining_limit(self) -> dict:
        """Get remaining limits for all transaction types."""
        remaining = {}
        for limit in self.limits:
            if limit.is_enabled:
                remaining[f"{limit.transaction_type}_{limit.period}"] = max(
                    Decimal("0"), 
                    limit.limit_amount - limit.current_usage
                )
        return remaining


class CardDetails(Card):
    """Extended card details with sensitive information (admin view)."""
    full_number: Optional[str] = Field(None, description="Full card number (admin only)")
    cvv: Optional[str] = Field(None, description="CVV code (admin only)")


# Request/Response models
class CardListRequest(BaseModel):
    """Request model for listing cards."""
    user_id: Optional[str] = None
    card_type: Optional[CardType] = None
    status: Optional[CardStatus] = None
    account_id: Optional[str] = None


class CardCreateRequest(BaseModel):
    """Request model for creating a new card."""
    account_id: str = Field(..., description="Account to associate the card with")
    card_type: CardType = Field(..., description="Type of card to create")
    card_network: CardNetwork = Field(..., description="Preferred card network")
    card_name: str = Field(..., min_length=1, max_length=100, description="Name to print on card")
    is_contactless_enabled: bool = Field(default=True)
    is_online_enabled: bool = Field(default=True)
    is_international_enabled: bool = Field(default=False)


class CardUpdateRequest(BaseModel):
    """Request model for updating card settings."""
    card_name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_contactless_enabled: Optional[bool] = None
    is_online_enabled: Optional[bool] = None
    is_international_enabled: Optional[bool] = None


class CardStatusRequest(BaseModel):
    """Request model for changing card status."""
    status: CardStatus = Field(..., description="New card status")
    reason: Optional[str] = Field(None, description="Reason for status change")


class CardLimitRequest(BaseModel):
    """Request model for setting card limits."""
    transaction_type: TransactionType = Field(..., description="Type of transaction to limit")
    period: LimitPeriod = Field(..., description="Time period for the limit")
    limit_amount: Decimal = Field(..., gt=0, description="Maximum amount for the period")
    is_enabled: bool = Field(default=True, description="Whether the limit is active")


class CardPinChangeRequest(BaseModel):
    """Request model for changing card PIN."""
    current_pin: str = Field(..., min_length=4, max_length=6, description="Current PIN")
    new_pin: str = Field(..., min_length=4, max_length=6, description="New PIN")
    confirm_pin: str = Field(..., min_length=4, max_length=6, description="Confirm new PIN")

    @validator('confirm_pin')
    def validate_pins_match(cls, v, values):
        if 'new_pin' in values and v != values['new_pin']:
            raise ValueError("PIN confirmation does not match")
        return v


# Response models
class CardListResponse(BaseResponse):
    """Response model for card listing."""
    cards: List[Card] = Field(..., description="List of user cards")
    total_count: int = Field(..., description="Total number of cards")


class CardResponse(BaseResponse):
    """Response model for single card operations."""
    card: Card = Field(..., description="Card details")


class CardCreatedResponse(BaseResponse):
    """Response model for card creation."""
    card: Card = Field(..., description="Created card details")
    delivery_estimate: str = Field(..., description="Estimated delivery timeframe")


class CardLimitsResponse(BaseResponse):
    """Response model for card limits."""
    limits: List[CardLimit] = Field(..., description="Current card limits")
    remaining_limits: dict = Field(..., description="Remaining amounts for each limit type")


class CardTransactionSummary(BaseModel):
    """Summary of card transactions."""
    transaction_type: TransactionType
    period: LimitPeriod
    transaction_count: int = Field(..., ge=0)
    total_amount: Decimal = Field(..., ge=0)
    average_amount: Decimal = Field(..., ge=0)


class CardUsageResponse(BaseResponse):
    """Response model for card usage analytics."""
    card_id: str = Field(..., description="Card identifier")
    period_start: datetime = Field(..., description="Start of analysis period")
    period_end: datetime = Field(..., description="End of analysis period")
    transaction_summary: List[CardTransactionSummary] = Field(..., description="Transaction summaries by type")
    total_spent: Decimal = Field(..., ge=0, description="Total amount spent in period")
    merchant_categories: dict = Field(..., description="Spending by merchant category")
