"""
Beneficiaries models for managing payment recipients.
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class BeneficiaryType(str, Enum):
    """Beneficiary type enumeration."""
    BANK_ACCOUNT = "bank_account"
    MOBILE_MONEY = "mobile_money"
    CARD = "card"
    CRYPTO_WALLET = "crypto_wallet"


class BeneficiaryStatus(str, Enum):
    """Beneficiary status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING_VERIFICATION = "pending_verification"
    BLOCKED = "blocked"


# Request Models
class BeneficiaryCreateRequest(BaseModel):
    """Beneficiary creation request model."""
    name: str = Field(..., min_length=1, max_length=100, description="Beneficiary name")
    email: Optional[EmailStr] = Field(None, description="Beneficiary email address")
    phone_number: Optional[str] = Field(None, description="Beneficiary phone number")
    type: BeneficiaryType = Field(..., description="Beneficiary type")
    
    # Bank account details
    bank_name: Optional[str] = Field(None, description="Bank name")
    account_number: Optional[str] = Field(None, description="Bank account number")
    routing_number: Optional[str] = Field(None, description="Bank routing number")
    swift_code: Optional[str] = Field(None, description="SWIFT code for international transfers")
    
    # Mobile money details
    mobile_provider: Optional[str] = Field(None, description="Mobile money provider")
    mobile_account: Optional[str] = Field(None, description="Mobile money account")
    
    # Card details
    card_number: Optional[str] = Field(None, description="Card number (last 4 digits)")
    card_type: Optional[str] = Field(None, description="Card type (visa, mastercard, etc.)")
    
    # Crypto wallet details
    wallet_address: Optional[str] = Field(None, description="Crypto wallet address")
    crypto_currency: Optional[str] = Field(None, description="Cryptocurrency type")
    
    # Additional details
    country: Optional[str] = Field(None, description="Country code")
    currency: Optional[str] = Field(None, description="Preferred currency")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")
    
    @validator('type')
    def validate_required_fields(cls, v, values):
        """Validate required fields based on beneficiary type."""
        if v == BeneficiaryType.BANK_ACCOUNT:
            if not values.get('bank_name') or not values.get('account_number'):
                raise ValueError('Bank name and account number are required for bank account beneficiaries')
        elif v == BeneficiaryType.MOBILE_MONEY:
            if not values.get('mobile_provider') or not values.get('mobile_account'):
                raise ValueError('Mobile provider and account are required for mobile money beneficiaries')
        elif v == BeneficiaryType.CARD:
            if not values.get('card_number'):
                raise ValueError('Card number is required for card beneficiaries')
        elif v == BeneficiaryType.CRYPTO_WALLET:
            if not values.get('wallet_address') or not values.get('crypto_currency'):
                raise ValueError('Wallet address and cryptocurrency are required for crypto wallet beneficiaries')
        return v


class BeneficiaryUpdateRequest(BaseModel):
    """Beneficiary update request model."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = Field(None)
    phone_number: Optional[str] = Field(None)
    
    # Bank account details
    bank_name: Optional[str] = Field(None)
    account_number: Optional[str] = Field(None)
    routing_number: Optional[str] = Field(None)
    swift_code: Optional[str] = Field(None)
    
    # Mobile money details
    mobile_provider: Optional[str] = Field(None)
    mobile_account: Optional[str] = Field(None)
    
    # Card details
    card_number: Optional[str] = Field(None)
    card_type: Optional[str] = Field(None)
    
    # Crypto wallet details
    wallet_address: Optional[str] = Field(None)
    crypto_currency: Optional[str] = Field(None)
    
    # Additional details
    country: Optional[str] = Field(None)
    currency: Optional[str] = Field(None)
    notes: Optional[str] = Field(None, max_length=500)
    status: Optional[BeneficiaryStatus] = Field(None)


# Response Models
class BeneficiaryProfile(BaseModel):
    """Beneficiary profile model."""
    id: str = Field(..., description="Beneficiary ID")
    user_id: str = Field(..., description="Owner user ID")
    name: str = Field(..., description="Beneficiary name")
    email: Optional[str] = Field(None, description="Beneficiary email")
    phone_number: Optional[str] = Field(None, description="Beneficiary phone number")
    type: BeneficiaryType = Field(..., description="Beneficiary type")
    status: BeneficiaryStatus = Field(..., description="Beneficiary status")
    
    # Bank account details
    bank_name: Optional[str] = Field(None, description="Bank name")
    account_number: Optional[str] = Field(None, description="Masked account number")
    routing_number: Optional[str] = Field(None, description="Bank routing number")
    swift_code: Optional[str] = Field(None, description="SWIFT code")
    
    # Mobile money details
    mobile_provider: Optional[str] = Field(None, description="Mobile money provider")
    mobile_account: Optional[str] = Field(None, description="Masked mobile account")
    
    # Card details
    card_number: Optional[str] = Field(None, description="Masked card number")
    card_type: Optional[str] = Field(None, description="Card type")
    
    # Crypto wallet details
    wallet_address: Optional[str] = Field(None, description="Masked wallet address")
    crypto_currency: Optional[str] = Field(None, description="Cryptocurrency type")
    
    # Additional details
    country: Optional[str] = Field(None, description="Country code")
    currency: Optional[str] = Field(None, description="Preferred currency")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    # Metadata
    is_verified: bool = Field(False, description="Verification status")
    is_favorite: bool = Field(False, description="Favorite status")
    last_used_at: Optional[datetime] = Field(None, description="Last used timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class BeneficiaryListResponse(BaseModel):
    """Beneficiary list response model."""
    success: bool = Field(True, description="Response success status")
    message: str = Field(..., description="Response message")
    data: Dict[str, List[BeneficiaryProfile]] = Field(..., description="Beneficiaries data")
    total: int = Field(..., description="Total number of beneficiaries")
    page: int = Field(1, description="Current page")
    per_page: int = Field(20, description="Items per page")


class BeneficiaryResponse(BaseModel):
    """Single beneficiary response model."""
    success: bool = Field(True, description="Response success status")
    message: str = Field(..., description="Response message")
    data: Dict[str, BeneficiaryProfile] = Field(..., description="Beneficiary data")


class RecentBeneficiariesResponse(BaseModel):
    """Recent beneficiaries response model."""
    success: bool = Field(True, description="Response success status")
    message: str = Field(..., description="Response message")
    data: Dict[str, List[BeneficiaryProfile]] = Field(..., description="Recent beneficiaries data")


# Database Models
class BeneficiaryCreate(BaseModel):
    """Beneficiary creation model for database operations."""
    user_id: str
    name: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    type: BeneficiaryType
    status: BeneficiaryStatus = BeneficiaryStatus.ACTIVE
    
    # Encrypted/hashed sensitive data
    bank_name: Optional[str] = None
    account_number_encrypted: Optional[str] = None
    routing_number: Optional[str] = None
    swift_code: Optional[str] = None
    
    mobile_provider: Optional[str] = None
    mobile_account_encrypted: Optional[str] = None
    
    card_number_encrypted: Optional[str] = None
    card_type: Optional[str] = None
    
    wallet_address_encrypted: Optional[str] = None
    crypto_currency: Optional[str] = None
    
    country: Optional[str] = None
    currency: Optional[str] = None
    notes: Optional[str] = None
    
    is_verified: bool = False
    is_favorite: bool = False


class BeneficiaryUpdate(BaseModel):
    """Beneficiary update model for database operations."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    status: Optional[BeneficiaryStatus] = None
    
    bank_name: Optional[str] = None
    account_number_encrypted: Optional[str] = None
    routing_number: Optional[str] = None
    swift_code: Optional[str] = None
    
    mobile_provider: Optional[str] = None
    mobile_account_encrypted: Optional[str] = None
    
    card_number_encrypted: Optional[str] = None
    card_type: Optional[str] = None
    
    wallet_address_encrypted: Optional[str] = None
    crypto_currency: Optional[str] = None
    
    country: Optional[str] = None
    currency: Optional[str] = None
    notes: Optional[str] = None
    
    is_verified: Optional[bool] = None
    is_favorite: Optional[bool] = None
    last_used_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# Utility Models
class BeneficiarySearchRequest(BaseModel):
    """Beneficiary search request model."""
    query: Optional[str] = Field(None, description="Search query")
    type: Optional[BeneficiaryType] = Field(None, description="Filter by type")
    status: Optional[BeneficiaryStatus] = Field(None, description="Filter by status")
    country: Optional[str] = Field(None, description="Filter by country")
    is_favorite: Optional[bool] = Field(None, description="Filter by favorite status")
    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(20, ge=1, le=100, description="Items per page")


class BeneficiaryVerificationRequest(BaseModel):
    """Beneficiary verification request model."""
    beneficiary_id: str = Field(..., description="Beneficiary ID")
    verification_method: str = Field(..., description="Verification method")
    verification_data: Dict[str, Any] = Field(..., description="Verification data")


class BeneficiaryStats(BaseModel):
    """Beneficiary statistics model."""
    total_beneficiaries: int = Field(..., description="Total number of beneficiaries")
    active_beneficiaries: int = Field(..., description="Number of active beneficiaries")
    verified_beneficiaries: int = Field(..., description="Number of verified beneficiaries")
    favorite_beneficiaries: int = Field(..., description="Number of favorite beneficiaries")
    by_type: Dict[str, int] = Field(..., description="Beneficiaries count by type")
    by_country: Dict[str, int] = Field(..., description="Beneficiaries count by country")
    recent_additions: int = Field(..., description="Recent additions (last 30 days)")
