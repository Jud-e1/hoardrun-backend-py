"""
Flat Pydantic models for card operations without inheritance.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime, date
from enum import Enum


class CardType(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"
    PREPAID = "prepaid"


class CardStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class CardProvider(str, Enum):
    VISA = "visa"
    MASTERCARD = "mastercard"
    AMEX = "amex"
    DISCOVER = "discover"


# Request Models
class CardCreateRequest(BaseModel):
    account_id: str
    card_type: CardType
    card_provider: CardProvider = Field(default=CardProvider.VISA)
    name_on_card: str = Field(..., min_length=1, max_length=100)
    credit_limit: Optional[Decimal] = Field(default=None, ge=0)
    pin: str = Field(..., min_length=4, max_length=6)


class CardUpdateRequest(BaseModel):
    name_on_card: Optional[str] = Field(None, min_length=1, max_length=100)
    credit_limit: Optional[Decimal] = Field(None, ge=0)
    daily_limit: Optional[Decimal] = Field(None, ge=0)
    monthly_limit: Optional[Decimal] = Field(None, ge=0)


class CardActivationRequest(BaseModel):
    activation_code: str = Field(..., min_length=6, max_length=10)


class CardPinChangeRequest(BaseModel):
    current_pin: str = Field(..., min_length=4, max_length=6)
    new_pin: str = Field(..., min_length=4, max_length=6)


class CardLimitRequest(BaseModel):
    daily_limit: Optional[Decimal] = Field(None, ge=0)
    monthly_limit: Optional[Decimal] = Field(None, ge=0)
    atm_daily_limit: Optional[Decimal] = Field(None, ge=0)


class CardTransactionRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    merchant_name: str = Field(..., min_length=1, max_length=100)
    merchant_category: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=255)


# Response Models
class Card(BaseModel):
    id: str
    account_id: str
    user_id: str
    card_number: str
    card_type: str
    card_provider: str
    name_on_card: str
    expiry_date: date
    status: str
    credit_limit: Optional[Decimal]
    available_credit: Optional[Decimal]
    daily_limit: Decimal
    monthly_limit: Decimal
    atm_daily_limit: Decimal
    is_contactless: bool
    is_international: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CardListResponse(BaseModel):
    success: bool = True
    message: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CardResponse(BaseModel):
    success: bool = True
    message: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CardCreatedResponse(BaseModel):
    success: bool = True
    message: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CardActivationResponse(BaseModel):
    success: bool = True
    message: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CardTransactionResponse(BaseModel):
    success: bool = True
    message: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CardStatementResponse(BaseModel):
    success: bool = True
    message: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CardLimitResponse(BaseModel):
    success: bool = True
    message: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)
