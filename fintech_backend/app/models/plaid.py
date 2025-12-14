"""
Plaid integration models for bank account connections.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional, Any
from enum import Enum

from pydantic import BaseModel, Field
from ..models.base import BaseModel
from sqlalchemy import Column, String, DateTime, Boolean, Numeric
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class PlaidConnectionStatus(str, Enum):
    """Plaid connection status enumeration."""
    ACTIVE = "active"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class PlaidLinkTokenRequest(BaseModel):
    """Request model for creating Plaid link tokens."""
    client_name: Optional[str] = Field(default="HoardRun", description="Name of the client application")


class PlaidLinkTokenResponse(BaseModel):
    """Response model for Plaid link token creation."""
    link_token: str = Field(..., description="Plaid link token")
    expiration: str = Field(..., description="Token expiration timestamp")
    link_token_id: str = Field(..., description="Internal link token identifier")


class PlaidExchangeTokenRequest(BaseModel):
    """Request model for exchanging public tokens."""
    public_token: str = Field(..., description="Plaid public token from Link")
    link_token_id: Optional[str] = Field(default=None, description="Associated link token ID")


class PlaidExchangeTokenResponse(BaseModel):
    """Response model for token exchange."""
    connection_id: str = Field(..., description="Internal connection identifier")
    access_token: str = Field(..., description="Plaid access token")
    item_id: str = Field(..., description="Plaid item ID")


class PlaidAccount(BaseModel):
    """Model for Plaid account information."""
    account_id: str = Field(..., description="Plaid account identifier")
    connection_id: str = Field(..., description="Internal connection identifier")
    name: str = Field(..., description="Account name")
    official_name: Optional[str] = Field(default=None, description="Official account name")
    type: Optional[str] = Field(default=None, description="Account type (checking, savings, etc.)")
    subtype: Optional[str] = Field(default=None, description="Account subtype")
    mask: Optional[str] = Field(default=None, description="Account mask (last 4 digits)")
    balances: Optional[Dict[str, Any]] = Field(default=None, description="Account balances")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Record update timestamp")


class PlaidTransaction(BaseModel):
    """Model for Plaid transaction information."""
    transaction_id: str = Field(..., description="Plaid transaction identifier")
    account_id: str = Field(..., description="Plaid account identifier")
    connection_id: str = Field(..., description="Internal connection identifier")
    amount: Decimal = Field(..., description="Transaction amount")
    iso_currency_code: Optional[str] = Field(default=None, description="ISO currency code")
    unofficial_currency_code: Optional[str] = Field(default=None, description="Unofficial currency code")
    date: str = Field(..., description="Transaction date")
    authorized_date: Optional[str] = Field(default=None, description="Authorized date")
    name: str = Field(..., description="Transaction name/description")
    merchant_name: Optional[str] = Field(default=None, description="Merchant name")
    payment_channel: Optional[str] = Field(default=None, description="Payment channel")
    pending: bool = Field(default=False, description="Whether transaction is pending")
    pending_transaction_id: Optional[str] = Field(default=None, description="Pending transaction ID")
    account_owner: Optional[str] = Field(default=None, description="Account owner")
    transaction_type: Optional[str] = Field(default=None, description="Transaction type")
    payment_meta: Optional[Dict[str, Any]] = Field(default=None, description="Payment metadata")
    location: Optional[Dict[str, Any]] = Field(default=None, description="Transaction location")
    transaction_code: Optional[str] = Field(default=None, description="Transaction code")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Record update timestamp")


class PlaidConnection(BaseModel):
    """Model for Plaid connection information."""
    connection_id: str = Field(..., description="Internal connection identifier")
    user_id: str = Field(..., description="User identifier")
    item_id: str = Field(..., description="Plaid item ID")
    access_token: str = Field(..., description="Plaid access token")
    status: PlaidConnectionStatus = Field(default=PlaidConnectionStatus.ACTIVE, description="Connection status")
    institution_id: Optional[str] = Field(default=None, description="Institution identifier")
    institution_name: Optional[str] = Field(default=None, description="Institution name")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Connection creation timestamp")
    last_synced_at: Optional[datetime] = Field(default=None, description="Last sync timestamp")
    error_message: Optional[str] = Field(default=None, description="Last error message")


class PlaidSyncRequest(BaseModel):
    """Request model for syncing Plaid data."""
    pass  # No additional parameters needed for basic sync


class PlaidSyncResponse(BaseModel):
    """Response model for sync operations."""
    connection_id: str = Field(..., description="Connection identifier")
    accounts_synced: int = Field(..., description="Number of accounts synced")
    transactions_synced: int = Field(..., description="Number of transactions synced")
    last_synced_at: datetime = Field(..., description="Last sync timestamp")


class PlaidLinkToken(Base):
    """Database model for Plaid link tokens."""
    __tablename__ = "plaid_link_tokens"

    link_token_id = Column(String, primary_key=True)
    user_id = Column(String)
    link_token = Column(String)
    expiration = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    used = Column(Boolean, default=False)


# Database models for Plaid data (using SQLAlchemy)
class PlaidConnectionDB(Base):
    """Database model for Plaid connections."""
    __tablename__ = "plaid_connections"

    connection_id = Column(String, primary_key=True)
    user_id = Column(String)
    item_id = Column(String)
    access_token = Column(String)
    status = Column(String, default=PlaidConnectionStatus.ACTIVE.value)
    institution_id = Column(String, nullable=True)
    institution_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_synced_at = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)


class PlaidAccountDB(Base):
    """Database model for Plaid accounts."""
    __tablename__ = "plaid_accounts"

    account_id = Column(String, primary_key=True)
    connection_id = Column(String)
    name = Column(String)
    official_name = Column(String, nullable=True)
    type = Column(String, nullable=True)
    subtype = Column(String, nullable=True)
    mask = Column(String, nullable=True)
    balances = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class PlaidTransactionDB(Base):
    """Database model for Plaid transactions."""
    __tablename__ = "plaid_transactions"

    transaction_id = Column(String, primary_key=True)
    account_id = Column(String)
    connection_id = Column(String)
    amount = Column(Numeric(precision=10, scale=2))
    iso_currency_code = Column(String, nullable=True)
    unofficial_currency_code = Column(String, nullable=True)
    date = Column(String)
    authorized_date = Column(String, nullable=True)
    name = Column(String)
    merchant_name = Column(String, nullable=True)
    payment_channel = Column(String, nullable=True)
    pending = Column(Boolean, default=False)
    pending_transaction_id = Column(String, nullable=True)
    account_owner = Column(String, nullable=True)
    transaction_type = Column(String, nullable=True)
    payment_meta = Column(String, nullable=True)
    location = Column(String, nullable=True)
    transaction_code = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
