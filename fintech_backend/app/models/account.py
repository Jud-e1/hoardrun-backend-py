"""
Account management models for the fintech backend.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


class AccountType(str, Enum):
    """Enumeration of account types."""
    CHECKING = "checking"
    SAVINGS = "savings"
    INVESTMENT = "investment"
    CREDIT = "credit"
    BUSINESS = "business"


class AccountStatus(str, Enum):
    """Enumeration of account statuses."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    PENDING = "pending"


class CurrencyCode(str, Enum):
    """Supported currency codes."""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CAD = "CAD"
    AUD = "AUD"
    CHF = "CHF"
    CNY = "CNY"


class TransactionCategory(str, Enum):
    """Transaction categories for statements."""
    INCOME = "income"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    PAYMENT = "payment"
    WITHDRAWAL = "withdrawal"
    DEPOSIT = "deposit"
    FEE = "fee"
    INTEREST = "interest"
    INVESTMENT = "investment"
    OTHER = "other"


class AccountBalance(BaseModel):
    """Account balance information."""
    currency: CurrencyCode = Field(..., description="Currency code")
    available_balance: Decimal = Field(..., description="Available balance for transactions")
    current_balance: Decimal = Field(..., description="Current account balance")
    pending_balance: Decimal = Field(default=Decimal("0"), description="Pending transactions amount")
    overdraft_limit: Optional[Decimal] = Field(None, description="Overdraft protection limit")
    reserved_balance: Decimal = Field(default=Decimal("0"), description="Reserved/held funds")
    
    @validator('available_balance', 'current_balance', 'pending_balance', 'reserved_balance')
    def validate_balance_precision(cls, v):
        """Ensure balance has appropriate decimal precision."""
        return round(v, 2)
    
    @property
    def effective_balance(self) -> Decimal:
        """Calculate effective spendable balance."""
        return self.available_balance - self.reserved_balance


class Account(BaseModel):
    """Account model representing a financial account."""
    id: Optional[str] = Field(None, description="Unique identifier")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    account_id: str = Field(..., description="Unique account identifier")
    user_id: str = Field(..., description="Owner user ID")
    account_type: AccountType = Field(..., description="Type of account")
    account_name: str = Field(..., description="Human-readable account name")
    account_number: str = Field(..., description="Masked account number")
    status: AccountStatus = Field(default=AccountStatus.ACTIVE, description="Account status")
    
    # Balance information
    balance: AccountBalance = Field(..., description="Account balance details")
    
    # Account settings
    is_primary: bool = Field(default=False, description="Whether this is the primary account")
    is_overdraft_enabled: bool = Field(default=False, description="Overdraft protection enabled")
    minimum_balance: Decimal = Field(default=Decimal("0"), description="Minimum required balance")
    
    # Interest and fees
    interest_rate: Optional[Decimal] = Field(None, description="Annual interest rate (for savings)")
    monthly_fee: Decimal = Field(default=Decimal("0"), description="Monthly maintenance fee")
    
    # Metadata
    opening_date: date = Field(..., description="Account opening date")
    last_statement_date: Optional[date] = Field(None, description="Last statement generation date")
    routing_number: Optional[str] = Field(None, description="Bank routing number")
    swift_code: Optional[str] = Field(None, description="SWIFT/BIC code for international transfers")


class AccountStatement(BaseModel):
    """Account statement model."""
    id: Optional[str] = Field(None, description="Unique identifier")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    statement_id: str = Field(..., description="Unique statement identifier")
    account_id: str = Field(..., description="Account identifier")
    statement_period_start: date = Field(..., description="Statement period start date")
    statement_period_end: date = Field(..., description="Statement period end date")
    opening_balance: Decimal = Field(..., description="Balance at period start")
    closing_balance: Decimal = Field(..., description="Balance at period end")
    total_credits: Decimal = Field(default=Decimal("0"), description="Total credit amount")
    total_debits: Decimal = Field(default=Decimal("0"), description="Total debit amount")
    transaction_count: int = Field(default=0, description="Number of transactions")
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class StatementTransaction(BaseModel):
    """Transaction entry in account statement."""
    transaction_id: str = Field(..., description="Transaction identifier")
    date: date = Field(..., description="Transaction date")
    description: str = Field(..., description="Transaction description")
    category: str = Field(..., description="Transaction category")
    amount: Decimal = Field(..., description="Transaction amount (positive for credits, negative for debits)")
    balance_after: Decimal = Field(..., description="Account balance after transaction")
    reference_number: Optional[str] = Field(None, description="External reference number")


# Request models
class AccountCreateRequest(BaseModel):
    """Request model for creating a new account."""
    account_type: AccountType = Field(..., description="Type of account to create")
    account_name: str = Field(..., min_length=1, max_length=100, description="Account name")
    currency: CurrencyCode = Field(default=CurrencyCode.USD, description="Account currency")
    initial_deposit: Optional[Decimal] = Field(None, ge=0, description="Initial deposit amount")
    is_overdraft_enabled: bool = Field(default=False, description="Enable overdraft protection")
    minimum_balance: Decimal = Field(default=Decimal("0"), ge=0, description="Minimum balance requirement")


class AccountUpdateRequest(BaseModel):
    """Request model for updating account settings."""
    account_name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_overdraft_enabled: Optional[bool] = None
    minimum_balance: Optional[Decimal] = Field(None, ge=0)
    is_primary: Optional[bool] = None


class AccountTransferRequest(BaseModel):
    """Request model for account-to-account transfers."""
    from_account_id: str = Field(..., description="Source account ID")
    to_account_id: str = Field(..., description="Destination account ID")
    amount: Decimal = Field(..., gt=0, description="Transfer amount")
    currency: CurrencyCode = Field(..., description="Transfer currency")
    description: Optional[str] = Field(None, max_length=200, description="Transfer description")
    reference: Optional[str] = Field(None, max_length=50, description="Reference number")


class StatementRequest(BaseModel):
    """Request model for generating account statements."""
    start_date: date = Field(..., description="Statement period start date")
    end_date: date = Field(..., description="Statement period end date")
    format: str = Field(default="json", description="Statement format (json, pdf)")
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError("End date must be after start date")
        return v


class BalanceHistoryRequest(BaseModel):
    """Request model for balance history."""
    days: int = Field(default=30, ge=1, le=365, description="Number of days of history")
    granularity: str = Field(default="daily", description="Data granularity (daily, weekly, monthly)")


# Response models
class AccountListResponse(BaseModel):
    """Response model for account listing."""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(default="Success", description="Response message")
    accounts: List[Account] = Field(..., description="List of user accounts")
    total_count: int = Field(..., description="Total number of accounts")
    primary_account_id: Optional[str] = Field(None, description="Primary account identifier")


class AccountResponse(BaseModel):
    """Response model for single account operations."""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(default="Success", description="Response message")
    account: Account = Field(..., description="Account details")


class AccountCreatedResponse(BaseModel):
    """Response model for account creation."""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(default="Account created successfully", description="Response message")
    account: Account = Field(..., description="Created account details")
    welcome_bonus: Optional[Decimal] = Field(None, description="Welcome bonus amount")
    next_steps: List[str] = Field(..., description="Recommended next steps")


class AccountBalanceResponse(BaseModel):
    """Response model for account balance."""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(default="Success", description="Response message")
    account_id: str = Field(..., description="Account identifier")
    balance: AccountBalance = Field(..., description="Current balance information")
    last_updated: datetime = Field(..., description="Last balance update timestamp")


class AccountStatementResponse(BaseModel):
    """Response model for account statements."""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(default="Success", description="Response message")
    statement: AccountStatement = Field(..., description="Statement details")
    transactions: List[StatementTransaction] = Field(..., description="Statement transactions")
    summary: Dict[str, Decimal] = Field(..., description="Statement summary by category")


class BalanceHistoryPoint(BaseModel):
    """Single point in balance history."""
    date: date = Field(..., description="Date of balance point")
    balance: Decimal = Field(..., description="Account balance")
    change: Decimal = Field(default=Decimal("0"), description="Change from previous point")


class BalanceHistoryResponse(BaseModel):
    """Response model for balance history."""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(default="Success", description="Response message")
    account_id: str = Field(..., description="Account identifier")
    period_start: date = Field(..., description="History period start")
    period_end: date = Field(..., description="History period end")
    history: List[BalanceHistoryPoint] = Field(..., description="Balance history points")
    trend: str = Field(..., description="Overall trend (increasing, decreasing, stable)")
    average_balance: Decimal = Field(..., description="Average balance over period")


class AccountOverviewResponse(BaseModel):
    """Response model for comprehensive account overview."""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(default="Success", description="Response message")
    accounts: List[Account] = Field(..., description="All user accounts")
    total_assets: Decimal = Field(..., description="Total assets across accounts")
    total_liabilities: Decimal = Field(..., description="Total liabilities (credit balances)")
    net_worth: Decimal = Field(..., description="Net worth (assets - liabilities)")
    monthly_income: Decimal = Field(..., description="Average monthly income")
    monthly_expenses: Decimal = Field(..., description="Average monthly expenses")
    cash_flow_trend: str = Field(..., description="Cash flow trend analysis")


class AccountTransferResponse(BaseModel):
    """Response model for account transfers."""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(default="Transfer completed successfully", description="Response message")
    transfer_id: str = Field(..., description="Transfer transaction identifier")
    from_account: str = Field(..., description="Source account ID")
    to_account: str = Field(..., description="Destination account ID")
    amount: Decimal = Field(..., description="Transfer amount")
    currency: CurrencyCode = Field(..., description="Transfer currency")
    status: str = Field(..., description="Transfer status")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    fee: Decimal = Field(default=Decimal("0"), description="Transfer fee charged")
