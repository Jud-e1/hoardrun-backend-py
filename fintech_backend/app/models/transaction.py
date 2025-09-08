"""
Transaction management models for the fintech backend.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from enum import Enum

from app.models.base import BaseResponse, BaseModel as BaseModelWithTimestamps


class TransactionType(str, Enum):
    """Enumeration of transaction types."""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    PAYMENT = "payment"
    REFUND = "refund"
    FEE = "fee"
    INTEREST = "interest"
    DIVIDEND = "dividend"
    PURCHASE = "purchase"
    SALE = "sale"
    ATM_WITHDRAWAL = "atm_withdrawal"
    CARD_PAYMENT = "card_payment"
    MOBILE_PAYMENT = "mobile_payment"
    BILL_PAYMENT = "bill_payment"
    SALARY = "salary"
    LOAN_PAYMENT = "loan_payment"
    INVESTMENT = "investment"
    OTHER = "other"


class TransactionStatus(str, Enum):
    """Enumeration of transaction statuses."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REVERSED = "reversed"


class TransactionDirection(str, Enum):
    """Transaction direction from account perspective."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MerchantCategory(str, Enum):
    """Merchant category codes for spending categorization."""
    GROCERIES = "groceries"
    RESTAURANTS = "restaurants"
    GAS_STATIONS = "gas_stations"
    RETAIL = "retail"
    ENTERTAINMENT = "entertainment"
    TRAVEL = "travel"
    HEALTHCARE = "healthcare"
    UTILITIES = "utilities"
    EDUCATION = "education"
    AUTOMOTIVE = "automotive"
    HOME_IMPROVEMENT = "home_improvement"
    INSURANCE = "insurance"
    PROFESSIONAL_SERVICES = "professional_services"
    GOVERNMENT = "government"
    CHARITY = "charity"
    ONLINE_SERVICES = "online_services"
    SUBSCRIPTION = "subscription"
    ATM_FEE = "atm_fee"
    BANK_FEE = "bank_fee"
    TRANSFER = "transfer"
    INVESTMENT_TRADE = "investment_trade"
    CASH_ADVANCE = "cash_advance"
    OTHER = "other"


class PaymentMethod(str, Enum):
    """Payment method used for transaction."""
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    MOBILE_MONEY = "mobile_money"
    CASH = "cash"
    CHECK = "check"
    WIRE = "wire"
    ACH = "ach"
    CRYPTO = "crypto"
    OTHER = "other"


class Transaction(BaseModelWithTimestamps):
    """Transaction model representing a financial transaction."""
    transaction_id: str = Field(..., description="Unique transaction identifier")
    account_id: str = Field(..., description="Associated account ID")
    user_id: str = Field(..., description="User ID (owner of account)")
    
    # Transaction details
    transaction_type: TransactionType = Field(..., description="Type of transaction")
    status: TransactionStatus = Field(..., description="Current transaction status")
    direction: TransactionDirection = Field(..., description="Transaction direction")
    
    # Amount and currency
    amount: Decimal = Field(..., description="Transaction amount (positive for credits, negative for debits)")
    currency: str = Field(..., description="Transaction currency code")
    exchange_rate: Optional[Decimal] = Field(None, description="Exchange rate if currency conversion applied")
    original_amount: Optional[Decimal] = Field(None, description="Original amount before conversion")
    original_currency: Optional[str] = Field(None, description="Original currency before conversion")
    
    # Description and categorization
    description: str = Field(..., description="Transaction description")
    merchant_name: Optional[str] = Field(None, description="Merchant or counterparty name")
    merchant_category: MerchantCategory = Field(default=MerchantCategory.OTHER, description="Merchant category")
    
    # Payment details
    payment_method: PaymentMethod = Field(..., description="Payment method used")
    card_id: Optional[str] = Field(None, description="Card ID if card transaction")
    reference_number: Optional[str] = Field(None, description="External reference number")
    
    # Location and metadata
    location: Optional[str] = Field(None, description="Transaction location")
    tags: List[str] = Field(default_factory=list, description="User-defined tags")
    notes: Optional[str] = Field(None, description="User notes")
    
    # Timing
    transaction_date: datetime = Field(..., description="When transaction occurred")
    posted_date: Optional[datetime] = Field(None, description="When transaction was posted")
    
    # Fees and charges
    fee_amount: Decimal = Field(default=Decimal("0"), description="Transaction fee")
    
    # Balance tracking
    balance_after: Optional[Decimal] = Field(None, description="Account balance after transaction")
    
    # Dispute and fraud
    is_disputed: bool = Field(default=False, description="Whether transaction is disputed")
    is_fraudulent: bool = Field(default=False, description="Whether transaction is flagged as fraudulent")
    
    @validator('amount')
    def validate_amount_precision(cls, v):
        """Ensure amount has appropriate decimal precision."""
        return round(v, 2)


class TransactionDetails(Transaction):
    """Extended transaction details with additional metadata."""
    merchant_details: Optional[Dict[str, Any]] = Field(None, description="Extended merchant information")
    authorization_code: Optional[str] = Field(None, description="Payment authorization code")
    processor_response: Optional[str] = Field(None, description="Payment processor response")
    risk_score: Optional[float] = Field(None, description="Fraud risk score")


class TransactionSummary(BaseModel):
    """Transaction summary for reporting."""
    period_start: date = Field(..., description="Summary period start")
    period_end: date = Field(..., description="Summary period end")
    total_transactions: int = Field(..., ge=0, description="Total number of transactions")
    total_amount: Decimal = Field(..., description="Total transaction amount")
    total_credits: Decimal = Field(default=Decimal("0"), description="Total credit amount")
    total_debits: Decimal = Field(default=Decimal("0"), description="Total debit amount")
    average_transaction: Decimal = Field(default=Decimal("0"), description="Average transaction amount")
    largest_transaction: Decimal = Field(default=Decimal("0"), description="Largest transaction amount")
    by_category: Dict[str, Decimal] = Field(default_factory=dict, description="Spending by category")
    by_merchant: Dict[str, Decimal] = Field(default_factory=dict, description="Spending by merchant")


# Request models
class TransactionCreateRequest(BaseModel):
    """Request model for creating a new transaction."""
    account_id: str = Field(..., description="Associated account ID")
    transaction_type: TransactionType = Field(..., description="Type of transaction")
    amount: Decimal = Field(..., description="Transaction amount")
    currency: str = Field(default="USD", description="Transaction currency code")
    description: str = Field(..., description="Transaction description")
    merchant_name: Optional[str] = Field(None, description="Merchant or counterparty name")
    merchant_category: MerchantCategory = Field(default=MerchantCategory.OTHER, description="Merchant category")
    payment_method: PaymentMethod = Field(..., description="Payment method used")
    card_id: Optional[str] = Field(None, description="Card ID if card transaction")
    reference_number: Optional[str] = Field(None, description="External reference number")
    location: Optional[str] = Field(None, description="Transaction location")
    tags: List[str] = Field(default_factory=list, description="User-defined tags")
    notes: Optional[str] = Field(None, description="User notes")


class TransactionFilters(BaseModel):
    """Filters for transaction queries."""
    account_id: Optional[str] = Field(None, description="Filter by account ID")
    transaction_type: Optional[str] = Field(None, description="Filter by transaction type")
    status: Optional[str] = Field(None, description="Filter by status")
    start_date: Optional[date] = Field(None, description="Filter from date")
    end_date: Optional[date] = Field(None, description="Filter to date")
    min_amount: Optional[float] = Field(None, ge=0, description="Minimum amount filter")
    max_amount: Optional[float] = Field(None, gt=0, description="Maximum amount filter")
    limit: int = Field(default=50, ge=1, le=1000, description="Number of results to return")
    offset: int = Field(default=0, ge=0, description="Number of results to skip")


class TransactionListRequest(BaseModel):
    """Request model for listing transactions."""
    account_id: Optional[str] = Field(None, description="Filter by account ID")
    transaction_type: Optional[TransactionType] = Field(None, description="Filter by transaction type")
    status: Optional[TransactionStatus] = Field(None, description="Filter by status")
    direction: Optional[TransactionDirection] = Field(None, description="Filter by direction")
    merchant_category: Optional[MerchantCategory] = Field(None, description="Filter by merchant category")
    payment_method: Optional[PaymentMethod] = Field(None, description="Filter by payment method")
    start_date: Optional[date] = Field(None, description="Filter from date")
    end_date: Optional[date] = Field(None, description="Filter to date")
    min_amount: Optional[Decimal] = Field(None, ge=0, description="Minimum amount filter")
    max_amount: Optional[Decimal] = Field(None, gt=0, description="Maximum amount filter")
    search_query: Optional[str] = Field(None, description="Search in description or merchant name")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    limit: int = Field(default=50, ge=1, le=1000, description="Number of results to return")
    offset: int = Field(default=0, ge=0, description="Number of results to skip")
    sort_by: str = Field(default="transaction_date", description="Sort field")
    sort_order: str = Field(default="desc", description="Sort order (asc, desc)")
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        if v and 'start_date' in values and values['start_date'] and v < values['start_date']:
            raise ValueError("End date must be after start date")
        return v
    
    @validator('max_amount')
    def validate_amount_range(cls, v, values):
        if v and 'min_amount' in values and values['min_amount'] and v < values['min_amount']:
            raise ValueError("Maximum amount must be greater than minimum amount")
        return v


class TransactionSearchRequest(BaseModel):
    """Request model for advanced transaction search."""
    query: str = Field(..., min_length=1, description="Search query")
    search_fields: List[str] = Field(
        default=["description", "merchant_name", "notes"],
        description="Fields to search in"
    )
    filters: Optional[TransactionListRequest] = Field(None, description="Additional filters")
    fuzzy_match: bool = Field(default=True, description="Enable fuzzy matching")


class TransactionUpdateRequest(BaseModel):
    """Request model for updating transaction details."""
    description: Optional[str] = Field(None, max_length=200)
    merchant_category: Optional[MerchantCategory] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = Field(None, max_length=500)


class TransactionDisputeRequest(BaseModel):
    """Request model for disputing a transaction."""
    reason: str = Field(..., description="Dispute reason")
    description: str = Field(..., min_length=10, max_length=1000, description="Detailed dispute description")
    evidence_urls: Optional[List[str]] = Field(None, description="URLs to supporting evidence")


class TransactionCategorizeRequest(BaseModel):
    """Request model for batch categorizing transactions."""
    transaction_ids: List[str] = Field(..., min_items=1, max_items=100, description="Transaction IDs to categorize")
    category: MerchantCategory = Field(..., description="New category")
    apply_to_similar: bool = Field(default=False, description="Apply to similar transactions")


class TransactionExportRequest(BaseModel):
    """Request model for exporting transactions."""
    format: str = Field(default="csv", description="Export format (csv, json, pdf)")
    filters: Optional[TransactionListRequest] = Field(None, description="Export filters")
    include_fields: Optional[List[str]] = Field(None, description="Specific fields to include")


# Response models
class TransactionListResponse(BaseResponse):
    """Response model for transaction listing."""
    transactions: List[Transaction] = Field(..., description="List of transactions")
    total_count: int = Field(..., description="Total number of matching transactions")
    summary: TransactionSummary = Field(..., description="Summary statistics")
    has_more: bool = Field(..., description="Whether more results are available")


class TransactionResponse(BaseResponse):
    """Response model for single transaction operations."""
    transaction: Transaction = Field(..., description="Transaction details")


class TransactionSearchResponse(BaseResponse):
    """Response model for transaction search results."""
    transactions: List[Transaction] = Field(..., description="Matching transactions")
    total_matches: int = Field(..., description="Total number of matches")
    search_time_ms: float = Field(..., description="Search execution time in milliseconds")
    suggestions: List[str] = Field(default_factory=list, description="Search suggestions")


class TransactionCategoryStats(BaseModel):
    """Statistics for a transaction category."""
    category: MerchantCategory = Field(..., description="Category name")
    transaction_count: int = Field(..., ge=0, description="Number of transactions")
    total_amount: Decimal = Field(..., description="Total amount spent")
    average_amount: Decimal = Field(..., description="Average transaction amount")
    percentage_of_total: float = Field(..., ge=0, le=100, description="Percentage of total spending")


class TransactionAnalyticsResponse(BaseResponse):
    """Response model for transaction analytics."""
    account_id: Optional[str] = Field(None, description="Account ID if filtered")
    period_start: date = Field(..., description="Analysis period start")
    period_end: date = Field(..., description="Analysis period end")
    total_transactions: int = Field(..., description="Total transactions analyzed")
    category_breakdown: List[TransactionCategoryStats] = Field(..., description="Spending by category")
    monthly_trends: Dict[str, Decimal] = Field(..., description="Monthly spending trends")
    top_merchants: Dict[str, Decimal] = Field(..., description="Top merchants by spending")
    payment_method_breakdown: Dict[str, Decimal] = Field(..., description="Spending by payment method")


class TransactionExportResponse(BaseResponse):
    """Response model for transaction export."""
    export_id: str = Field(..., description="Export job identifier")
    download_url: str = Field(..., description="URL to download exported file")
    expires_at: datetime = Field(..., description="Download link expiration")
    file_size: int = Field(..., description="File size in bytes")
    record_count: int = Field(..., description="Number of records exported")


class DisputeResponse(BaseResponse):
    """Response model for transaction disputes."""
    dispute_id: str = Field(..., description="Dispute case identifier")
    transaction_id: str = Field(..., description="Disputed transaction ID")
    status: str = Field(..., description="Dispute status")
    estimated_resolution: str = Field(..., description="Estimated resolution timeframe")
    case_number: str = Field(..., description="Dispute case number")


class BulkUpdateResponse(BaseResponse):
    """Response model for bulk transaction updates."""
    updated_count: int = Field(..., description="Number of transactions updated")
    failed_count: int = Field(..., description="Number of failed updates")
    failed_transactions: List[str] = Field(default_factory=list, description="IDs of failed updates")
    similar_updated: int = Field(default=0, description="Number of similar transactions also updated")
