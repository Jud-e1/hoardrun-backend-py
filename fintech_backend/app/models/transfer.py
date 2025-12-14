"""
Money transfer models for the fintech backend.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from enum import Enum

from ..models.base import BaseResponse, BaseModel as AppBaseModel


class TransferType(str, Enum):
    """Enumeration of transfer types."""
    DOMESTIC_BANK = "domestic_bank"
    INTERNATIONAL_WIRE = "international_wire"
    MOBILE_MONEY = "mobile_money"
    CRYPTO = "crypto"
    REMITTANCE = "remittance"
    INSTANT_TRANSFER = "instant_transfer"
    PLAID_TRANSFER = "plaid_transfer"


class TransferStatus(str, Enum):
    """Enumeration of transfer statuses."""
    PENDING = "pending"
    PROCESSING = "processing"
    IN_TRANSIT = "in_transit"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETURNED = "returned"
    ON_HOLD = "on_hold"


class TransferPriority(str, Enum):
    """Transfer processing priority levels."""
    STANDARD = "standard"
    EXPRESS = "express"
    URGENT = "urgent"


class BeneficiaryType(str, Enum):
    """Types of transfer beneficiaries."""
    INDIVIDUAL = "individual"
    BUSINESS = "business"
    ORGANIZATION = "organization"


class BeneficiaryStatus(str, Enum):
    """Beneficiary verification status."""
    ACTIVE = "active"
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    SUSPENDED = "suspended"
    BLOCKED = "blocked"


class CountryCode(str, Enum):
    """Supported country codes for transfers."""
    US = "US"
    GB = "GB"
    DE = "DE"
    FR = "FR"
    CA = "CA"
    AU = "AU"
    JP = "JP"
    CN = "CN"
    IN = "IN"
    BR = "BR"
    MX = "MX"
    KE = "KE"
    NG = "NG"
    ZA = "ZA"
    EG = "EG"


class Beneficiary(BaseModel):
    """Beneficiary model for money transfers."""
    beneficiary_id: str = Field(..., description="Unique beneficiary identifier")
    user_id: str = Field(..., description="Owner user ID")
    
    # Personal information
    beneficiary_type: BeneficiaryType = Field(..., description="Type of beneficiary")
    first_name: str = Field(..., description="Beneficiary first name")
    last_name: str = Field(..., description="Beneficiary last name")
    business_name: Optional[str] = Field(None, description="Business name if business beneficiary")
    
    # Contact information
    email: Optional[str] = Field(None, description="Beneficiary email address")
    phone_number: Optional[str] = Field(None, description="Beneficiary phone number")
    
    # Address information
    address_line1: str = Field(..., description="Address line 1")
    address_line2: Optional[str] = Field(None, description="Address line 2")
    city: str = Field(..., description="City")
    state_province: Optional[str] = Field(None, description="State or province")
    postal_code: str = Field(..., description="Postal code")
    country: CountryCode = Field(..., description="Country code")
    
    # Banking information
    bank_name: str = Field(..., description="Beneficiary bank name")
    bank_code: Optional[str] = Field(None, description="Bank code (routing number, sort code, etc.)")
    swift_bic: Optional[str] = Field(None, description="SWIFT/BIC code for international transfers")
    account_number: str = Field(..., description="Beneficiary account number")
    iban: Optional[str] = Field(None, description="IBAN for European transfers")
    
    # Mobile money information (if applicable)
    mobile_money_provider: Optional[str] = Field(None, description="Mobile money provider")
    mobile_money_number: Optional[str] = Field(None, description="Mobile money number")
    
    # Status and verification
    status: BeneficiaryStatus = Field(default=BeneficiaryStatus.PENDING_VERIFICATION)
    is_favorite: bool = Field(default=False, description="Favorite beneficiary for quick access")
    verification_date: Optional[datetime] = Field(None, description="When beneficiary was verified")
    
    # Metadata
    nickname: Optional[str] = Field(None, description="User-defined nickname")
    relationship: Optional[str] = Field(None, description="Relationship to user")
    notes: Optional[str] = Field(None, description="User notes")
    
    @validator('email')
    def validate_email_format(cls, v):
        if v and '@' not in v:
            raise ValueError("Invalid email format")
        return v
    
    @property
    def display_name(self) -> str:
        """Get display name for beneficiary."""
        if self.nickname:
            return self.nickname
        elif self.business_name:
            return self.business_name
        else:
            return f"{self.first_name} {self.last_name}"


class ExchangeRate(BaseModel):
    """Exchange rate information for currency conversion."""
    from_currency: str = Field(..., description="Source currency code")
    to_currency: str = Field(..., description="Target currency code")
    rate: Decimal = Field(..., gt=0, description="Exchange rate")
    inverse_rate: Decimal = Field(..., gt=0, description="Inverse exchange rate")
    margin: Decimal = Field(default=Decimal("0.02"), description="Exchange rate margin")
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    valid_until: datetime = Field(..., description="Rate validity expiration")
    
    @validator('inverse_rate')
    def validate_inverse_rate(cls, v, values):
        if 'rate' in values and abs(v - (1 / values['rate'])) > 0.001:
            raise ValueError("Inverse rate must be 1/rate")
        return v


class TransferQuote(BaseModel):
    """Transfer cost quote and exchange rate information."""
    quote_id: str = Field(..., description="Unique quote identifier")
    from_amount: Decimal = Field(..., gt=0, description="Source amount")
    from_currency: str = Field(..., description="Source currency")
    to_amount: Decimal = Field(..., gt=0, description="Destination amount after conversion")
    to_currency: str = Field(..., description="Destination currency")
    
    # Exchange rate details
    exchange_rate: Optional[ExchangeRate] = Field(None, description="Applied exchange rate")
    
    # Fee breakdown
    transfer_fee: Decimal = Field(default=Decimal("0"), description="Transfer processing fee")
    exchange_fee: Decimal = Field(default=Decimal("0"), description="Currency exchange fee")
    total_fees: Decimal = Field(..., description="Total fees charged")
    
    # Total cost
    total_cost: Decimal = Field(..., description="Total amount debited from source account")
    
    # Quote validity
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(..., description="Quote expiration time")
    transfer_type: TransferType = Field(..., description="Type of transfer")
    
    @validator('total_cost')
    def validate_total_cost(cls, v, values):
        if 'from_amount' in values and 'total_fees' in values:
            expected = values['from_amount'] + values['total_fees']
            if abs(v - expected) > Decimal("0.01"):
                raise ValueError("Total cost must equal source amount plus fees")
        return v


class MoneyTransfer(BaseModel):
    """Money transfer model representing an external transfer."""
    transfer_id: str = Field(..., description="Unique transfer identifier")
    user_id: str = Field(..., description="Sender user ID")
    
    # Source information
    source_account_id: str = Field(..., description="Source account ID")
    
    # Destination information
    beneficiary_id: str = Field(..., description="Beneficiary ID")
    
    # Transfer details
    transfer_type: TransferType = Field(..., description="Type of transfer")
    status: TransferStatus = Field(..., description="Current transfer status")
    priority: TransferPriority = Field(default=TransferPriority.STANDARD, description="Transfer priority")
    
    # Amount and currency
    source_amount: Decimal = Field(..., gt=0, description="Amount in source currency")
    source_currency: str = Field(..., description="Source currency code")
    destination_amount: Decimal = Field(..., gt=0, description="Amount in destination currency")
    destination_currency: str = Field(..., description="Destination currency code")
    
    # Exchange rate applied
    exchange_rate_used: Optional[Decimal] = Field(None, description="Exchange rate applied")
    
    # Fee information
    transfer_fee: Decimal = Field(default=Decimal("0"), description="Transfer fee")
    exchange_fee: Decimal = Field(default=Decimal("0"), description="Exchange fee")
    total_fees: Decimal = Field(..., description="Total fees charged")
    
    # Cost breakdown
    total_cost: Decimal = Field(..., description="Total amount debited")
    
    # Transfer details
    purpose: str = Field(..., description="Transfer purpose/reason")
    reference: Optional[str] = Field(None, description="User reference")
    recipient_message: Optional[str] = Field(None, description="Message to recipient")
    
    # Processing information
    quote_id: Optional[str] = Field(None, description="Associated quote ID")
    external_reference: Optional[str] = Field(None, description="External system reference")
    
    # Tracking information
    initiated_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = Field(None, description="When transfer was processed")
    completed_at: Optional[datetime] = Field(None, description="When transfer was completed")
    estimated_arrival: Optional[datetime] = Field(None, description="Estimated arrival time")
    
    # Status history
    status_history: List[Dict[str, Any]] = Field(default_factory=list, description="Status change history")
    
    # Compliance and verification
    compliance_check_passed: bool = Field(default=False, description="AML/KYC compliance status")
    requires_documents: bool = Field(default=False, description="Whether additional documents required")
    
    @validator('total_cost')
    def validate_total_cost(cls, v, values):
        if 'source_amount' in values and 'total_fees' in values:
            expected = values['source_amount'] + values['total_fees']
            if abs(v - expected) > Decimal("0.01"):
                raise ValueError("Total cost must equal source amount plus fees")
        return v


# Request models
class BeneficiaryCreateRequest(BaseModel):
    """Request model for creating a beneficiary."""
    beneficiary_type: BeneficiaryType = Field(..., description="Type of beneficiary")
    first_name: str = Field(..., min_length=1, max_length=50, description="First name")
    last_name: str = Field(..., min_length=1, max_length=50, description="Last name")
    business_name: Optional[str] = Field(None, max_length=100, description="Business name")
    
    email: Optional[str] = Field(None, description="Email address")
    phone_number: Optional[str] = Field(None, description="Phone number")
    
    address_line1: str = Field(..., max_length=100, description="Address line 1")
    address_line2: Optional[str] = Field(None, max_length=100, description="Address line 2")
    city: str = Field(..., max_length=50, description="City")
    state_province: Optional[str] = Field(None, max_length=50, description="State/province")
    postal_code: str = Field(..., max_length=20, description="Postal code")
    country: CountryCode = Field(..., description="Country")
    
    bank_name: str = Field(..., max_length=100, description="Bank name")
    bank_code: Optional[str] = Field(None, max_length=20, description="Bank code")
    swift_bic: Optional[str] = Field(None, max_length=11, description="SWIFT/BIC code")
    account_number: str = Field(..., max_length=50, description="Account number")
    iban: Optional[str] = Field(None, max_length=34, description="IBAN")
    
    mobile_money_provider: Optional[str] = Field(None, description="Mobile money provider")
    mobile_money_number: Optional[str] = Field(None, description="Mobile money number")
    
    nickname: Optional[str] = Field(None, max_length=50, description="Nickname")
    relationship: Optional[str] = Field(None, max_length=50, description="Relationship")
    notes: Optional[str] = Field(None, max_length=500, description="Notes")


class BeneficiaryUpdateRequest(BaseModel):
    """Request model for updating beneficiary information."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    business_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = None
    phone_number: Optional[str] = None
    nickname: Optional[str] = Field(None, max_length=50)
    relationship: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=500)
    is_favorite: Optional[bool] = None


class TransferQuoteRequest(BaseModel):
    """Request model for getting transfer quotes."""
    source_account_id: str = Field(..., description="Source account ID")
    beneficiary_id: str = Field(..., description="Beneficiary ID")
    source_amount: Decimal = Field(..., gt=0, description="Amount to send")
    source_currency: str = Field(..., description="Source currency")
    destination_currency: str = Field(..., description="Destination currency")
    transfer_type: TransferType = Field(..., description="Type of transfer")
    priority: TransferPriority = Field(default=TransferPriority.STANDARD, description="Transfer priority")


class TransferCreateRequest(BaseModel):
    """Request model for creating a money transfer."""
    source_account_id: str = Field(..., description="Source account ID")
    destination_account_id: str = Field(..., description="Destination account ID")
    amount: float = Field(..., gt=0, description="Transfer amount")
    currency: str = Field(default="USD", description="Currency code")
    description: Optional[str] = Field(None, max_length=200, description="Transfer description")
    reference: Optional[str] = Field(None, max_length=50, description="User reference")
    transfer_type: TransferType = Field(default=TransferType.INSTANT_TRANSFER, description="Type of transfer")


class TransferInitiateRequest(BaseModel):
    """Request model for initiating a money transfer."""
    quote_id: str = Field(..., description="Quote ID from previous quote request")
    purpose: str = Field(..., min_length=1, max_length=200, description="Transfer purpose")
    reference: Optional[str] = Field(None, max_length=50, description="User reference")
    recipient_message: Optional[str] = Field(None, max_length=200, description="Message to recipient")
    notification_preferences: Dict[str, bool] = Field(
        default_factory=lambda: {"email": True, "sms": False, "push": True},
        description="Notification preferences"
    )


class TransferCancelRequest(BaseModel):
    """Request model for cancelling a transfer."""
    reason: str = Field(..., description="Cancellation reason")
    refund_fees: bool = Field(default=False, description="Whether to refund fees")


# Response models
class BeneficiaryListResponse(BaseResponse):
    """Response model for beneficiary listing."""
    beneficiaries: List[Beneficiary] = Field(..., description="List of beneficiaries")
    total_count: int = Field(..., description="Total number of beneficiaries")
    favorites: List[Beneficiary] = Field(..., description="Favorite beneficiaries")


class BeneficiaryResponse(BaseResponse):
    """Response model for single beneficiary operations."""
    beneficiary: Beneficiary = Field(..., description="Beneficiary details")


class TransferQuoteResponse(BaseResponse):
    """Response model for transfer quotes."""
    quote: TransferQuote = Field(..., description="Transfer quote details")
    alternative_quotes: List[TransferQuote] = Field(default_factory=list, description="Alternative quote options")


class TransferResponse(BaseResponse):
    """Response model for transfer operations."""
    transfer: MoneyTransfer = Field(..., description="Transfer details")


class TransferListResponse(BaseResponse):
    """Response model for transfer listing."""
    transfers: List[MoneyTransfer] = Field(..., description="List of transfers")
    total_count: int = Field(..., description="Total number of transfers")
    pending_count: int = Field(..., description="Number of pending transfers")


class TransferTrackingResponse(BaseResponse):
    """Response model for transfer tracking."""
    transfer: MoneyTransfer = Field(..., description="Transfer details")
    tracking_events: List[Dict[str, Any]] = Field(..., description="Transfer tracking events")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    next_update: Optional[datetime] = Field(None, description="Next status update time")


class ExchangeRateResponse(BaseResponse):
    """Response model for exchange rates."""
    rates: List[ExchangeRate] = Field(..., description="Available exchange rates")
    base_currency: str = Field(..., description="Base currency for rates")
    last_updated: datetime = Field(..., description="Last rate update time")


class TransferLimitsResponse(BaseResponse):
    """Response model for transfer limits."""
    daily_limit: Decimal = Field(..., description="Daily transfer limit")
    monthly_limit: Decimal = Field(..., description="Monthly transfer limit")
    annual_limit: Decimal = Field(..., description="Annual transfer limit")
    daily_used: Decimal = Field(..., description="Daily limit used")
    monthly_used: Decimal = Field(..., description="Monthly limit used")
    annual_used: Decimal = Field(..., description="Annual limit used")
    remaining_daily: Decimal = Field(..., description="Remaining daily limit")
    remaining_monthly: Decimal = Field(..., description="Remaining monthly limit")
    remaining_annual: Decimal = Field(..., description="Remaining annual limit")
    single_transfer_limit: Decimal = Field(..., description="Maximum single transfer amount")


class TransferFeesResponse(BaseResponse):
    """Response model for transfer fee schedules."""
    transfer_type: TransferType = Field(..., description="Transfer type")
    fee_structure: Dict[str, Any] = Field(..., description="Fee structure details")
    currency_pairs: List[Dict[str, Any]] = Field(..., description="Supported currency pairs and fees")
    priority_fees: Dict[str, Decimal] = Field(..., description="Priority upgrade fees")


class CountryCorridor(BaseModel):
    """Transfer corridor information between countries."""
    from_country: CountryCode = Field(..., description="Source country")
    to_country: CountryCode = Field(..., description="Destination country")
    supported_transfer_types: List[TransferType] = Field(..., description="Supported transfer types")
    average_delivery_time: str = Field(..., description="Average delivery time")
    is_active: bool = Field(default=True, description="Whether corridor is active")
    compliance_level: str = Field(..., description="Required compliance level")


class TransferCorridorsResponse(BaseResponse):
    """Response model for transfer corridors."""
    corridors: List[CountryCorridor] = Field(..., description="Available transfer corridors")
    total_countries: int = Field(..., description="Total number of supported countries")
    popular_corridors: List[CountryCorridor] = Field(..., description="Most popular corridors")
