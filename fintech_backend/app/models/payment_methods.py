"""
Payment Methods models for managing various payment options.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class PaymentMethodType(str, Enum):
    """Payment method type enumeration."""
    BANK_ACCOUNT = "bank_account"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    MOBILE_MONEY = "mobile_money"
    DIGITAL_WALLET = "digital_wallet"
    CRYPTO_WALLET = "crypto_wallet"
    PAYPAL = "paypal"
    STRIPE = "stripe"


class PaymentMethodStatus(str, Enum):
    """Payment method status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    EXPIRED = "expired"
    BLOCKED = "blocked"
    SUSPENDED = "suspended"


class CardType(str, Enum):
    """Card type enumeration."""
    VISA = "visa"
    MASTERCARD = "mastercard"
    AMERICAN_EXPRESS = "american_express"
    DISCOVER = "discover"
    DINERS_CLUB = "diners_club"
    JCB = "jcb"
    UNIONPAY = "unionpay"


class BankAccountType(str, Enum):
    """Bank account type enumeration."""
    CHECKING = "checking"
    SAVINGS = "savings"
    BUSINESS = "business"
    MONEY_MARKET = "money_market"


class Currency(str, Enum):
    """Supported currency enumeration."""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    UGX = "UGX"
    KES = "KES"
    TZS = "TZS"
    GHS = "GHS"
    NGN = "NGN"
    ZAR = "ZAR"


# Request Models
class PaymentMethodCreateRequest(BaseModel):
    """Payment method creation request model."""
    type: PaymentMethodType = Field(..., description="Payment method type")
    name: str = Field(..., min_length=1, max_length=100, description="Display name for payment method")
    currency: Currency = Field(..., description="Primary currency")
    is_default: bool = Field(False, description="Set as default payment method")
    
    # Bank account details
    bank_name: Optional[str] = Field(None, description="Bank name")
    account_number: Optional[str] = Field(None, description="Bank account number")
    routing_number: Optional[str] = Field(None, description="Bank routing number")
    swift_code: Optional[str] = Field(None, description="SWIFT code")
    iban: Optional[str] = Field(None, description="IBAN")
    account_type: Optional[BankAccountType] = Field(None, description="Bank account type")
    account_holder_name: Optional[str] = Field(None, description="Account holder name")
    
    # Card details
    card_number: Optional[str] = Field(None, description="Card number")
    card_holder_name: Optional[str] = Field(None, description="Card holder name")
    expiry_month: Optional[int] = Field(None, ge=1, le=12, description="Card expiry month")
    expiry_year: Optional[int] = Field(None, ge=2024, le=2050, description="Card expiry year")
    cvv: Optional[str] = Field(None, description="Card CVV")
    card_type: Optional[CardType] = Field(None, description="Card type")
    
    # Mobile money details
    mobile_provider: Optional[str] = Field(None, description="Mobile money provider")
    mobile_number: Optional[str] = Field(None, description="Mobile money number")
    
    # Digital wallet details
    wallet_provider: Optional[str] = Field(None, description="Digital wallet provider")
    wallet_id: Optional[str] = Field(None, description="Wallet ID or email")
    
    # Crypto wallet details
    wallet_address: Optional[str] = Field(None, description="Crypto wallet address")
    crypto_currency: Optional[str] = Field(None, description="Cryptocurrency type")
    network: Optional[str] = Field(None, description="Blockchain network")
    
    # Additional details
    country: Optional[str] = Field(None, description="Country code")
    billing_address: Optional[Dict[str, str]] = Field(None, description="Billing address")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    @validator('type')
    def validate_required_fields(cls, v, values):
        """Validate required fields based on payment method type."""
        if v == PaymentMethodType.BANK_ACCOUNT:
            required_fields = ['bank_name', 'account_number', 'account_holder_name']
            for field in required_fields:
                if not values.get(field):
                    raise ValueError(f'{field} is required for bank account payment methods')
        elif v in [PaymentMethodType.CREDIT_CARD, PaymentMethodType.DEBIT_CARD]:
            required_fields = ['card_number', 'card_holder_name', 'expiry_month', 'expiry_year', 'cvv']
            for field in required_fields:
                if not values.get(field):
                    raise ValueError(f'{field} is required for card payment methods')
        elif v == PaymentMethodType.MOBILE_MONEY:
            required_fields = ['mobile_provider', 'mobile_number']
            for field in required_fields:
                if not values.get(field):
                    raise ValueError(f'{field} is required for mobile money payment methods')
        elif v == PaymentMethodType.DIGITAL_WALLET:
            required_fields = ['wallet_provider', 'wallet_id']
            for field in required_fields:
                if not values.get(field):
                    raise ValueError(f'{field} is required for digital wallet payment methods')
        elif v == PaymentMethodType.CRYPTO_WALLET:
            required_fields = ['wallet_address', 'crypto_currency']
            for field in required_fields:
                if not values.get(field):
                    raise ValueError(f'{field} is required for crypto wallet payment methods')
        return v
    
    @validator('card_number')
    def validate_card_number(cls, v):
        """Validate card number format."""
        if v:
            # Remove spaces and dashes
            cleaned = v.replace(' ', '').replace('-', '')
            if not cleaned.isdigit():
                raise ValueError('Card number must contain only digits')
            if len(cleaned) < 13 or len(cleaned) > 19:
                raise ValueError('Card number must be between 13 and 19 digits')
        return v
    
    @validator('cvv')
    def validate_cvv(cls, v):
        """Validate CVV format."""
        if v:
            if not v.isdigit():
                raise ValueError('CVV must contain only digits')
            if len(v) < 3 or len(v) > 4:
                raise ValueError('CVV must be 3 or 4 digits')
        return v


class PaymentMethodUpdateRequest(BaseModel):
    """Payment method update request model."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_default: Optional[bool] = Field(None)
    status: Optional[PaymentMethodStatus] = Field(None)
    
    # Bank account details
    account_holder_name: Optional[str] = Field(None)
    
    # Card details
    card_holder_name: Optional[str] = Field(None)
    expiry_month: Optional[int] = Field(None, ge=1, le=12)
    expiry_year: Optional[int] = Field(None, ge=2024, le=2050)
    
    # Additional details
    billing_address: Optional[Dict[str, str]] = Field(None)
    metadata: Optional[Dict[str, Any]] = Field(None)


class PaymentMethodVerificationRequest(BaseModel):
    """Payment method verification request model."""
    verification_method: str = Field(..., description="Verification method")
    verification_data: Dict[str, Any] = Field(..., description="Verification data")
    
    # For micro-deposits verification
    deposit_amounts: Optional[List[float]] = Field(None, description="Micro-deposit amounts")
    
    # For card verification
    verification_code: Optional[str] = Field(None, description="Verification code")
    
    # For document verification
    document_type: Optional[str] = Field(None, description="Document type")
    document_url: Optional[str] = Field(None, description="Document URL")


# Response Models
class PaymentMethodProfile(BaseModel):
    """Payment method profile model."""
    id: str = Field(..., description="Payment method ID")
    user_id: str = Field(..., description="Owner user ID")
    type: PaymentMethodType = Field(..., description="Payment method type")
    name: str = Field(..., description="Display name")
    currency: Currency = Field(..., description="Primary currency")
    status: PaymentMethodStatus = Field(..., description="Payment method status")
    is_default: bool = Field(..., description="Default payment method flag")
    is_verified: bool = Field(..., description="Verification status")
    
    # Masked sensitive details
    bank_name: Optional[str] = Field(None, description="Bank name")
    account_number_masked: Optional[str] = Field(None, description="Masked account number")
    routing_number: Optional[str] = Field(None, description="Bank routing number")
    swift_code: Optional[str] = Field(None, description="SWIFT code")
    iban_masked: Optional[str] = Field(None, description="Masked IBAN")
    account_type: Optional[BankAccountType] = Field(None, description="Bank account type")
    account_holder_name: Optional[str] = Field(None, description="Account holder name")
    
    card_number_masked: Optional[str] = Field(None, description="Masked card number")
    card_holder_name: Optional[str] = Field(None, description="Card holder name")
    expiry_month: Optional[int] = Field(None, description="Card expiry month")
    expiry_year: Optional[int] = Field(None, description="Card expiry year")
    card_type: Optional[CardType] = Field(None, description="Card type")
    
    mobile_provider: Optional[str] = Field(None, description="Mobile money provider")
    mobile_number_masked: Optional[str] = Field(None, description="Masked mobile number")
    
    wallet_provider: Optional[str] = Field(None, description="Digital wallet provider")
    wallet_id_masked: Optional[str] = Field(None, description="Masked wallet ID")
    
    wallet_address_masked: Optional[str] = Field(None, description="Masked wallet address")
    crypto_currency: Optional[str] = Field(None, description="Cryptocurrency type")
    network: Optional[str] = Field(None, description="Blockchain network")
    
    country: Optional[str] = Field(None, description="Country code")
    billing_address: Optional[Dict[str, str]] = Field(None, description="Billing address")
    
    # Metadata
    last_used_at: Optional[datetime] = Field(None, description="Last used timestamp")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class PaymentMethodListResponse(BaseModel):
    """Payment method list response model."""
    success: bool = Field(True, description="Response success status")
    message: str = Field(..., description="Response message")
    data: Dict[str, List[PaymentMethodProfile]] = Field(..., description="Payment methods data")
    total: int = Field(..., description="Total number of payment methods")
    page: int = Field(1, description="Current page")
    per_page: int = Field(20, description="Items per page")


class PaymentMethodResponse(BaseModel):
    """Single payment method response model."""
    success: bool = Field(True, description="Response success status")
    message: str = Field(..., description="Response message")
    data: Dict[str, PaymentMethodProfile] = Field(..., description="Payment method data")


class PaymentMethodVerificationResponse(BaseModel):
    """Payment method verification response model."""
    success: bool = Field(True, description="Response success status")
    message: str = Field(..., description="Response message")
    data: Dict[str, Any] = Field(..., description="Verification result data")


# Database Models
class PaymentMethodCreate(BaseModel):
    """Payment method creation model for database operations."""
    user_id: str
    type: PaymentMethodType
    name: str
    currency: Currency
    status: PaymentMethodStatus = PaymentMethodStatus.PENDING_VERIFICATION
    is_default: bool = False
    is_verified: bool = False
    
    # Encrypted sensitive data
    bank_name: Optional[str] = None
    account_number_encrypted: Optional[str] = None
    routing_number: Optional[str] = None
    swift_code: Optional[str] = None
    iban_encrypted: Optional[str] = None
    account_type: Optional[BankAccountType] = None
    account_holder_name: Optional[str] = None
    
    card_number_encrypted: Optional[str] = None
    card_holder_name: Optional[str] = None
    expiry_month: Optional[int] = None
    expiry_year: Optional[int] = None
    cvv_encrypted: Optional[str] = None
    card_type: Optional[CardType] = None
    
    mobile_provider: Optional[str] = None
    mobile_number_encrypted: Optional[str] = None
    
    wallet_provider: Optional[str] = None
    wallet_id_encrypted: Optional[str] = None
    
    wallet_address_encrypted: Optional[str] = None
    crypto_currency: Optional[str] = None
    network: Optional[str] = None
    
    country: Optional[str] = None
    billing_address: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None


class PaymentMethodUpdate(BaseModel):
    """Payment method update model for database operations."""
    name: Optional[str] = None
    status: Optional[PaymentMethodStatus] = None
    is_default: Optional[bool] = None
    is_verified: Optional[bool] = None
    
    account_holder_name: Optional[str] = None
    card_holder_name: Optional[str] = None
    expiry_month: Optional[int] = None
    expiry_year: Optional[int] = None
    
    billing_address: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# Utility Models
class PaymentMethodFilter(BaseModel):
    """Payment method filter model."""
    type: Optional[PaymentMethodType] = Field(None, description="Filter by type")
    status: Optional[PaymentMethodStatus] = Field(None, description="Filter by status")
    currency: Optional[Currency] = Field(None, description="Filter by currency")
    is_default: Optional[bool] = Field(None, description="Filter by default status")
    is_verified: Optional[bool] = Field(None, description="Filter by verification status")
    country: Optional[str] = Field(None, description="Filter by country")
    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(20, ge=1, le=100, description="Items per page")


class PaymentMethodStats(BaseModel):
    """Payment method statistics model."""
    total_payment_methods: int = Field(..., description="Total number of payment methods")
    active_payment_methods: int = Field(..., description="Number of active payment methods")
    verified_payment_methods: int = Field(..., description="Number of verified payment methods")
    default_payment_method_id: Optional[str] = Field(None, description="Default payment method ID")
    by_type: Dict[str, int] = Field(..., description="Payment methods count by type")
    by_status: Dict[str, int] = Field(..., description="Payment methods count by status")
    by_currency: Dict[str, int] = Field(..., description="Payment methods count by currency")
    expiring_soon: int = Field(..., description="Number of payment methods expiring soon")


class PaymentMethodValidation(BaseModel):
    """Payment method validation result model."""
    is_valid: bool = Field(..., description="Validation result")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    suggestions: List[str] = Field(default_factory=list, description="Improvement suggestions")


class PaymentMethodSecurity(BaseModel):
    """Payment method security information model."""
    encryption_status: str = Field(..., description="Encryption status")
    last_security_check: datetime = Field(..., description="Last security check timestamp")
    security_score: int = Field(..., ge=0, le=100, description="Security score")
    compliance_status: str = Field(..., description="Compliance status")
    pci_compliant: bool = Field(..., description="PCI compliance status")


class PaymentMethodDB(BaseModel):
    """Database model for payment methods."""
    id: str = Field(..., description="Payment method ID")
    user_id: str = Field(..., description="Owner user ID")
    type: PaymentMethodType = Field(..., description="Payment method type")
    name: str = Field(..., description="Display name")
    currency: Currency = Field(..., description="Primary currency")
    status: PaymentMethodStatus = Field(..., description="Payment method status")
    is_default: bool = Field(..., description="Default payment method flag")
    is_verified: bool = Field(..., description="Verification status")
    
    # Encrypted sensitive data
    bank_name: Optional[str] = Field(None, description="Bank name")
    account_number_encrypted: Optional[str] = Field(None, description="Encrypted account number")
    account_number_masked: Optional[str] = Field(None, description="Masked account number")
    routing_number: Optional[str] = Field(None, description="Bank routing number")
    swift_code: Optional[str] = Field(None, description="SWIFT code")
    iban_encrypted: Optional[str] = Field(None, description="Encrypted IBAN")
    iban_masked: Optional[str] = Field(None, description="Masked IBAN")
    account_type: Optional[BankAccountType] = Field(None, description="Bank account type")
    account_holder_name: Optional[str] = Field(None, description="Account holder name")
    
    card_number_encrypted: Optional[str] = Field(None, description="Encrypted card number")
    card_number_masked: Optional[str] = Field(None, description="Masked card number")
    card_holder_name: Optional[str] = Field(None, description="Card holder name")
    expiry_month: Optional[int] = Field(None, description="Card expiry month")
    expiry_year: Optional[int] = Field(None, description="Card expiry year")
    cvv_encrypted: Optional[str] = Field(None, description="Encrypted CVV")
    card_type: Optional[CardType] = Field(None, description="Card type")
    
    mobile_provider: Optional[str] = Field(None, description="Mobile money provider")
    mobile_number_encrypted: Optional[str] = Field(None, description="Encrypted mobile number")
    mobile_number_masked: Optional[str] = Field(None, description="Masked mobile number")
    
    wallet_provider: Optional[str] = Field(None, description="Digital wallet provider")
    wallet_id_encrypted: Optional[str] = Field(None, description="Encrypted wallet ID")
    wallet_id_masked: Optional[str] = Field(None, description="Masked wallet ID")
    
    wallet_address_encrypted: Optional[str] = Field(None, description="Encrypted wallet address")
    wallet_address_masked: Optional[str] = Field(None, description="Masked wallet address")
    crypto_currency: Optional[str] = Field(None, description="Cryptocurrency type")
    network: Optional[str] = Field(None, description="Blockchain network")
    
    country: Optional[str] = Field(None, description="Country code")
    billing_address: Optional[Dict[str, str]] = Field(None, description="Billing address")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    # Timestamps
    last_used_at: Optional[datetime] = Field(None, description="Last used timestamp")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    deleted_at: Optional[datetime] = Field(None, description="Deletion timestamp")
    
    class Config:
        from_attributes = True
