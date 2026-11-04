"""
Flat Pydantic models for account operations without inheritance.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from enum import Enum


class AccountType(str, Enum):
    CHECKING = "checking"
    SAVINGS = "savings"
    INVESTMENT = "investment"
    CREDIT = "credit"


class AccountStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    CLOSED = "closed"


# Request Models
class AccountCreateRequest(BaseModel):
    account_type: AccountType
    name: str = Field(..., min_length=1, max_length=100)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    initial_deposit: Optional[Decimal] = Field(default=None, ge=0)
    overdraft_protection: bool = Field(default=False)
    minimum_balance: Optional[Decimal] = Field(default=None, ge=0)
    is_primary: bool = Field(default=False)


class AccountUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    overdraft_protection: Optional[bool] = None
    minimum_balance: Optional[Decimal] = Field(None, ge=0)
    is_primary: Optional[bool] = None


class AccountTransferRequest(BaseModel):
    from_account_id: str
    to_account_id: str
    amount: Decimal = Field(..., gt=0)
    description: Optional[str] = Field(None, max_length=255)


class StatementRequest(BaseModel):
    start_date: datetime
    end_date: datetime
    format: str = Field(default="json", pattern="^(json|pdf|csv)$")


class BalanceHistoryRequest(BaseModel):
    days: int = Field(default=30, ge=1, le=365)
    granularity: str = Field(default="daily", pattern="^(daily|weekly|monthly)$")


# Response Models
class Account(BaseModel):
    id: str
    user_id: str
    account_number: str
    account_type: str
    name: str
    currency: str
    balance: Decimal
    available_balance: Decimal
    status: str
    overdraft_protection: bool
    overdraft_limit: Optional[Decimal]
    minimum_balance: Optional[Decimal]
    is_primary: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AccountListResponse(BaseModel):
    success: bool = True
    message: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AccountResponse(BaseModel):
    success: bool = True
    message: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AccountCreatedResponse(BaseModel):
    success: bool = True
    message: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AccountBalanceResponse(BaseModel):
    success: bool = True
    message: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AccountStatementResponse(BaseModel):
    success: bool = True
    message: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BalanceHistoryResponse(BaseModel):
    success: bool = True
    message: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AccountOverviewResponse(BaseModel):
    success: bool = True
    message: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AccountTransferResponse(BaseModel):
    success: bool = True
    message: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)
