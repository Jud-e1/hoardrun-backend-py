"""
SQLAlchemy database models for the fintech backend.
"""
from sqlalchemy import (
    Column, String, DateTime, Boolean, Integer, Text, ForeignKey,
    Enum as SQLEnum, JSON, CheckConstraint, UniqueConstraint, Index
)
from sqlalchemy.types import DECIMAL
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
from datetime import datetime
import enum
import uuid
import re

from .config import Base


def generate_uuid():
    """Generate a UUID string."""
    return str(uuid.uuid4())


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


# Enums
class AccountTypeEnum(enum.Enum):
    CHECKING = "checking"
    SAVINGS = "savings"
    INVESTMENT = "investment"
    CREDIT = "credit"
    BUSINESS = "business"


class AccountStatusEnum(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    PENDING = "pending"


class TransactionTypeEnum(enum.Enum):
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


class TransactionStatusEnum(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REVERSED = "reversed"


class TransactionDirectionEnum(enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MerchantCategoryEnum(enum.Enum):
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


class PaymentMethodEnum(enum.Enum):
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    MOBILE_MONEY = "mobile_money"
    CASH = "cash"
    CHECK = "check"
    WIRE = "wire"
    ACH = "ach"
    CRYPTO = "crypto"
    OTHER = "other"


class CardTypeEnum(enum.Enum):
    DEBIT = "debit"
    CREDIT = "credit"
    PREPAID = "prepaid"


class CardStatusEnum(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# Database Models
class User(Base, TimestampMixin):
    """User model with enhanced validation and constraints."""
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    phone_number = Column(String, index=True)
    is_active = Column(Boolean, default=True, index=True)
    is_verified = Column(Boolean, default=False)

    # Authentication fields
    password_hash = Column(String, nullable=False)
    email_verification_code = Column(String, unique=True)
    email_verified = Column(Boolean, default=False)
    password_reset_token = Column(String, unique=True)
    password_reset_expires = Column(DateTime(timezone=True))
    last_login_at = Column(DateTime(timezone=True))

    # Profile fields
    date_of_birth = Column(String)
    country = Column(String(2))  # ISO 3166-1 alpha-2 country code
    id_number = Column(String)
    bio = Column(Text)
    profile_picture_url = Column(String)

    # Status and role with constraints
    status = Column(String, default="pending", nullable=False, index=True)
    role = Column(String, default="user", nullable=False, index=True)

    # Relationships
    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    cards = relationship("Card", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'suspended', 'deactivated')",
            name='check_user_status'
        ),
        CheckConstraint(
            "role IN ('user', 'premium', 'admin')",
            name='check_user_role'
        ),
        CheckConstraint(
            "length(first_name) >= 1 AND length(last_name) >= 1",
            name='check_name_length'
        ),
        CheckConstraint(
            "email LIKE '%@%'",
            name='check_email_format'
        ),
    )

    @validates('email')
    def validate_email(self, key, email):
        """Validate email format."""
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise ValueError("Invalid email format")
        return email.lower()

    @validates('phone_number')
    def validate_phone_number(self, key, phone_number):
        """Validate phone number format."""
        if phone_number:
            # Remove all non-digit characters except + for international prefix
            cleaned = re.sub(r'[^\d+]', '', phone_number)
            # Allow international format with + or local format
            # Supports formats like: +1234567890, 1234567890, 0123456789, etc.
            if not re.match(r'^\+?\d{7,15}$', cleaned):
                raise ValueError("Invalid phone number format. Must be 7-15 digits, optionally starting with +")
            return cleaned
        return phone_number

    @validates('country')
    def validate_country(self, key, country):
        """Validate country code format."""
        if country and len(country) != 2:
            raise ValueError("Country code must be 2 characters (ISO 3166-1 alpha-2)")
        return country.upper() if country else country

    @property
    def full_name(self):
        """Get user's full name."""
        return f"{self.first_name} {self.last_name}"


class Account(Base, TimestampMixin):
    """Account model with enhanced validation and constraints."""
    __tablename__ = "accounts"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    account_number = Column(String, unique=True, nullable=False, index=True)
    account_name = Column(String, nullable=False)
    account_type = Column(SQLEnum(AccountTypeEnum), nullable=False, index=True)
    status = Column(SQLEnum(AccountStatusEnum), default=AccountStatusEnum.ACTIVE, index=True)

    # Balance information with constraints
    current_balance = Column(DECIMAL(precision=15, scale=2), default=0.00, nullable=False)
    available_balance = Column(DECIMAL(precision=15, scale=2), default=0.00, nullable=False)
    pending_balance = Column(DECIMAL(precision=15, scale=2), default=0.00, nullable=False)
    reserved_balance = Column(DECIMAL(precision=15, scale=2), default=0.00, nullable=False)
    overdraft_limit = Column(DECIMAL(precision=15, scale=2), default=0.00)

    # Account settings
    currency = Column(String(3), default="USD", nullable=False, index=True)
    is_primary = Column(Boolean, default=False, index=True)
    is_overdraft_enabled = Column(Boolean, default=False)
    minimum_balance = Column(DECIMAL(precision=15, scale=2), default=0.00)

    # Interest and fees
    interest_rate = Column(DECIMAL(precision=5, scale=4), default=0.0000)
    monthly_fee = Column(DECIMAL(precision=10, scale=2), default=0.00)

    # Metadata
    opening_date = Column(DateTime(timezone=True), default=func.now())
    last_statement_date = Column(DateTime(timezone=True))
    routing_number = Column(String)
    swift_code = Column(String)

    # Relationships
    user = relationship("User", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")
    cards = relationship("Card", back_populates="account", cascade="all, delete-orphan")

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "current_balance >= -overdraft_limit",
            name='check_balance_overdraft'
        ),
        CheckConstraint(
            "available_balance >= 0",
            name='check_available_balance'
        ),
        CheckConstraint(
            "pending_balance >= 0",
            name='check_pending_balance'
        ),
        CheckConstraint(
            "reserved_balance >= 0",
            name='check_reserved_balance'
        ),
        CheckConstraint(
            "overdraft_limit >= 0",
            name='check_overdraft_limit'
        ),
        CheckConstraint(
            "minimum_balance >= 0",
            name='check_minimum_balance'
        ),
        CheckConstraint(
            "interest_rate >= 0 AND interest_rate <= 1",
            name='check_interest_rate'
        ),
        CheckConstraint(
            "monthly_fee >= 0",
            name='check_monthly_fee'
        ),
        CheckConstraint(
            "length(currency) = 3",
            name='check_currency_length'
        ),
        UniqueConstraint('user_id', 'is_primary', name='unique_primary_account_per_user'),
        Index('idx_account_user_type', 'user_id', 'account_type'),
        Index('idx_account_status_type', 'status', 'account_type'),
    )

    @validates('account_number')
    def validate_account_number(self, key, account_number):
        """Validate account number format."""
        if not re.match(r'^[A-Z0-9]{10,20}$', account_number):
            raise ValueError("Account number must be 10-20 alphanumeric characters")
        return account_number

    @validates('currency')
    def validate_currency(self, key, currency):
        """Validate currency code format."""
        if not re.match(r'^[A-Z]{3}$', currency):
            raise ValueError("Currency must be a 3-letter ISO code")
        return currency.upper()

    @property
    def effective_balance(self):
        """Calculate effective balance considering overdraft."""
        return self.available_balance + (self.overdraft_limit if self.is_overdraft_enabled else 0)


class Transaction(Base, TimestampMixin):
    """Transaction model with enhanced validation and constraints."""
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(String, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Transaction details
    transaction_type = Column(SQLEnum(TransactionTypeEnum), nullable=False, index=True)
    status = Column(SQLEnum(TransactionStatusEnum), nullable=False, index=True)
    direction = Column(SQLEnum(TransactionDirectionEnum), nullable=False, index=True)

    # Amount and currency
    amount = Column(DECIMAL(precision=15, scale=2), nullable=False)
    currency = Column(String(3), nullable=False)
    exchange_rate = Column(DECIMAL(precision=10, scale=6))
    original_amount = Column(DECIMAL(precision=15, scale=2))
    original_currency = Column(String(3))

    # Description and categorization
    description = Column(String, nullable=False)
    merchant_name = Column(String)
    merchant_category = Column(SQLEnum(MerchantCategoryEnum), default=MerchantCategoryEnum.OTHER, index=True)

    # Payment details
    payment_method = Column(SQLEnum(PaymentMethodEnum), nullable=False)
    card_id = Column(String, ForeignKey("cards.id", ondelete="SET NULL"))
    reference_number = Column(String, unique=True, index=True)

    # Location and metadata
    location = Column(String)
    tags = Column(JSON)  # Store as JSON array
    notes = Column(Text)

    # Timing
    transaction_date = Column(DateTime(timezone=True), nullable=False, index=True)
    posted_date = Column(DateTime(timezone=True))

    # Fees and charges
    fee_amount = Column(DECIMAL(precision=15, scale=2), default=0.00)

    # Balance tracking
    balance_after = Column(DECIMAL(precision=15, scale=2))

    # Dispute and fraud
    is_disputed = Column(Boolean, default=False, index=True)
    is_fraudulent = Column(Boolean, default=False, index=True)

    # Relationships
    user = relationship("User", back_populates="transactions")
    account = relationship("Account", back_populates="transactions")
    card = relationship("Card", back_populates="transactions")

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name='check_transaction_amount_positive'
        ),
        CheckConstraint(
            "fee_amount >= 0",
            name='check_fee_amount_non_negative'
        ),
        CheckConstraint(
            "exchange_rate > 0",
            name='check_exchange_rate_positive'
        ),
        CheckConstraint(
            "original_amount > 0",
            name='check_original_amount_positive'
        ),
        CheckConstraint(
            "length(currency) = 3",
            name='check_transaction_currency_length'
        ),
        CheckConstraint(
            "length(original_currency) = 3",
            name='check_original_currency_length'
        ),
        CheckConstraint(
            "transaction_date <= posted_date OR posted_date IS NULL",
            name='check_transaction_posted_date_order'
        ),
        Index('idx_transaction_user_date', 'user_id', 'transaction_date'),
        Index('idx_transaction_account_date', 'account_id', 'transaction_date'),
        Index('idx_transaction_status_date', 'status', 'transaction_date'),
        Index('idx_transaction_type_date', 'transaction_type', 'transaction_date'),
        Index('idx_transaction_merchant_date', 'merchant_category', 'transaction_date'),
    )

    @validates('currency', 'original_currency')
    def validate_currency(self, key, currency):
        """Validate currency code format."""
        if currency and not re.match(r'^[A-Z]{3}$', currency):
            raise ValueError(f"{key} must be a 3-letter ISO code")
        return currency.upper() if currency else currency

    @validates('reference_number')
    def validate_reference_number(self, key, reference_number):
        """Validate reference number format."""
        if reference_number and not re.match(r'^[A-Z0-9-]{8,50}$', reference_number):
            raise ValueError("Reference number must be 8-50 alphanumeric characters with hyphens")
        return reference_number

    @property
    def total_amount(self):
        """Calculate total amount including fees."""
        return self.amount + self.fee_amount


class Card(Base, TimestampMixin):
    """Card model with enhanced validation and constraints."""
    __tablename__ = "cards"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(String, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Card details
    card_number_masked = Column(String, nullable=False, unique=True)  # Only store masked version
    card_type = Column(SQLEnum(CardTypeEnum), nullable=False, index=True)
    status = Column(SQLEnum(CardStatusEnum), default=CardStatusEnum.ACTIVE, index=True)

    # Card information
    cardholder_name = Column(String, nullable=False)
    expiry_month = Column(Integer, nullable=False)
    expiry_year = Column(Integer, nullable=False)

    # Limits and settings
    daily_limit = Column(DECIMAL(precision=15, scale=2), default=1000.00)
    monthly_limit = Column(DECIMAL(precision=15, scale=2), default=10000.00)
    is_contactless_enabled = Column(Boolean, default=True)
    is_online_enabled = Column(Boolean, default=True)
    is_international_enabled = Column(Boolean, default=False)

    # PIN and security
    pin_set = Column(Boolean, default=False)
    failed_pin_attempts = Column(Integer, default=0)
    last_used_date = Column(DateTime(timezone=True))

    # Metadata
    issued_date = Column(DateTime(timezone=True), default=func.now())
    activation_date = Column(DateTime(timezone=True))

    # Relationships
    user = relationship("User", back_populates="cards")
    account = relationship("Account", back_populates="cards")
    transactions = relationship("Transaction", back_populates="card")

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "expiry_month >= 1 AND expiry_month <= 12",
            name='check_expiry_month'
        ),
        CheckConstraint(
            "expiry_year >= 2020 AND expiry_year <= 2050",
            name='check_expiry_year'
        ),
        CheckConstraint(
            "daily_limit > 0",
            name='check_daily_limit_positive'
        ),
        CheckConstraint(
            "monthly_limit > 0",
            name='check_monthly_limit_positive'
        ),
        CheckConstraint(
            "monthly_limit >= daily_limit",
            name='check_monthly_limit_greater_than_daily'
        ),
        CheckConstraint(
            "failed_pin_attempts >= 0 AND failed_pin_attempts <= 10",
            name='check_failed_pin_attempts'
        ),
        CheckConstraint(
            "activation_date >= issued_date OR activation_date IS NULL",
            name='check_activation_after_issued'
        ),
        Index('idx_card_expiry', 'expiry_year', 'expiry_month'),
        Index('idx_card_user_status', 'user_id', 'status'),
        Index('idx_card_account_type', 'account_id', 'card_type'),
    )

    @validates('card_number_masked')
    def validate_card_number_masked(self, key, card_number_masked):
        """Validate masked card number format."""
        if not re.match(r'^\*{4,12}\d{4}$', card_number_masked):
            raise ValueError("Card number must be masked (e.g., ****1234)")
        return card_number_masked

    @validates('cardholder_name')
    def validate_cardholder_name(self, key, cardholder_name):
        """Validate cardholder name format."""
        if not re.match(r'^[A-Z\s]{2,50}$', cardholder_name.upper()):
            raise ValueError("Cardholder name must be 2-50 alphabetic characters")
        return cardholder_name.upper()

    @property
    def is_expired(self):
        """Check if card is expired."""
        from datetime import datetime
        now = datetime.now()
        return (self.expiry_year < now.year or
                (self.expiry_year == now.year and self.expiry_month < now.month))

    @property
    def is_blocked(self):
        """Check if card is blocked due to failed PIN attempts."""
        return self.failed_pin_attempts >= 3


class Investment(Base, TimestampMixin):
    """Investment model."""
    __tablename__ = "investments"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False, index=True)
    
    # Investment details
    symbol = Column(String, nullable=False)
    name = Column(String, nullable=False)
    investment_type = Column(String, nullable=False)  # stock, bond, etf, mutual_fund, etc.
    
    # Quantity and pricing
    quantity = Column(DECIMAL(precision=15, scale=6), nullable=False)
    purchase_price = Column(DECIMAL(precision=15, scale=2), nullable=False)
    current_price = Column(DECIMAL(precision=15, scale=2))
    
    # Dates
    purchase_date = Column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    user = relationship("User")
    account = relationship("Account")


class P2PTransaction(Base, TimestampMixin):
    """P2P Transaction model."""
    __tablename__ = "p2p_transactions"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    sender_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    recipient_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    
    # Transaction details
    amount = Column(DECIMAL(precision=15, scale=2), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    description = Column(String)
    status = Column(String, nullable=False)  # pending, completed, failed, cancelled
    
    # Timing
    requested_date = Column(DateTime(timezone=True), default=func.now())
    completed_date = Column(DateTime(timezone=True))
    
    # Relationships
    sender = relationship("User", foreign_keys=[sender_id])
    recipient = relationship("User", foreign_keys=[recipient_id])


class TransferQuote(Base, TimestampMixin):
    """Transfer quote model for storing transfer cost estimates."""
    __tablename__ = "transfer_quotes"

    quote_id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Quote details
    from_amount = Column(DECIMAL(precision=15, scale=2), nullable=False)
    from_currency = Column(String(3), nullable=False)
    to_amount = Column(DECIMAL(precision=15, scale=2), nullable=False)
    to_currency = Column(String(3), nullable=False)

    # Exchange rate (stored as JSON for complex rate structures)
    exchange_rate = Column(JSON)

    # Fee breakdown
    transfer_fee = Column(DECIMAL(precision=15, scale=2), default=0.00, nullable=False)
    exchange_fee = Column(DECIMAL(precision=15, scale=2), default=0.00, nullable=False)
    total_fees = Column(DECIMAL(precision=15, scale=2), nullable=False)

    # Total cost
    total_cost = Column(DECIMAL(precision=15, scale=2), nullable=False)

    # Quote validity
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    transfer_type = Column(String, nullable=False)

    # Relationships
    user = relationship("User")

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "from_amount > 0",
            name='check_quote_from_amount_positive'
        ),
        CheckConstraint(
            "to_amount > 0",
            name='check_quote_to_amount_positive'
        ),
        CheckConstraint(
            "transfer_fee >= 0",
            name='check_quote_transfer_fee_non_negative'
        ),
        CheckConstraint(
            "exchange_fee >= 0",
            name='check_quote_exchange_fee_non_negative'
        ),
        CheckConstraint(
            "total_fees >= 0",
            name='check_quote_total_fees_non_negative'
        ),
        CheckConstraint(
            "total_cost > 0",
            name='check_quote_total_cost_positive'
        ),
        CheckConstraint(
            "length(from_currency) = 3",
            name='check_quote_from_currency_length'
        ),
        CheckConstraint(
            "length(to_currency) = 3",
            name='check_quote_to_currency_length'
        ),
        CheckConstraint(
            "expires_at > created_at",
            name='check_quote_expires_after_created'
        ),
        Index('idx_transfer_quotes_user_expires', 'user_id', 'expires_at'),
        Index('idx_transfer_quotes_expires', 'expires_at'),
    )

    @validates('from_currency', 'to_currency')
    def validate_currency(self, key, currency):
        """Validate currency code format."""
        if currency and not re.match(r'^[A-Z]{3}$', currency):
            raise ValueError(f"{key} must be a 3-letter ISO code")
        return currency.upper() if currency else currency


class MoneyTransfer(Base, TimestampMixin):
    """Money transfer model for external transfers."""
    __tablename__ = "money_transfers"

    transfer_id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Source information
    source_account_id = Column(String, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Destination information
    beneficiary_id = Column(String, nullable=False, index=True)  # Foreign key to beneficiaries table

    # Transfer details
    transfer_type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)
    priority = Column(String, default="standard", nullable=False)

    # Amount and currency
    source_amount = Column(DECIMAL(precision=15, scale=2), nullable=False)
    source_currency = Column(String(3), nullable=False)
    destination_amount = Column(DECIMAL(precision=15, scale=2), nullable=False)
    destination_currency = Column(String(3), nullable=False)

    # Exchange rate applied
    exchange_rate_used = Column(DECIMAL(precision=10, scale=6))

    # Fee information
    transfer_fee = Column(DECIMAL(precision=15, scale=2), default=0.00, nullable=False)
    exchange_fee = Column(DECIMAL(precision=15, scale=2), default=0.00, nullable=False)
    total_fees = Column(DECIMAL(precision=15, scale=2), nullable=False)

    # Cost breakdown
    total_cost = Column(DECIMAL(precision=15, scale=2), nullable=False)

    # Transfer details
    purpose = Column(String)
    reference = Column(String)
    recipient_message = Column(Text)

    # Processing information
    quote_id = Column(String, ForeignKey("transfer_quotes.quote_id", ondelete="SET NULL"))
    external_reference = Column(String, index=True)

    # Tracking information
    initiated_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    estimated_arrival = Column(DateTime(timezone=True))

    # Status history (stored as JSON)
    status_history = Column(JSON, default=list)

    # Compliance and verification
    compliance_check_passed = Column(Boolean, default=False)
    requires_documents = Column(Boolean, default=False)

    # Relationships
    user = relationship("User")
    source_account = relationship("Account")
    quote = relationship("TransferQuote")

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "source_amount > 0",
            name='check_transfer_source_amount_positive'
        ),
        CheckConstraint(
            "destination_amount > 0",
            name='check_transfer_destination_amount_positive'
        ),
        CheckConstraint(
            "transfer_fee >= 0",
            name='check_transfer_fee_non_negative'
        ),
        CheckConstraint(
            "exchange_fee >= 0",
            name='check_transfer_exchange_fee_non_negative'
        ),
        CheckConstraint(
            "total_fees >= 0",
            name='check_transfer_total_fees_non_negative'
        ),
        CheckConstraint(
            "total_cost > 0",
            name='check_transfer_total_cost_positive'
        ),
        CheckConstraint(
            "length(source_currency) = 3",
            name='check_transfer_source_currency_length'
        ),
        CheckConstraint(
            "length(destination_currency) = 3",
            name='check_transfer_destination_currency_length'
        ),
        CheckConstraint(
            "exchange_rate_used > 0",
            name='check_transfer_exchange_rate_positive'
        ),
        CheckConstraint(
            "initiated_at <= processed_at OR processed_at IS NULL",
            name='check_transfer_processed_after_initiated'
        ),
        CheckConstraint(
            "processed_at <= completed_at OR completed_at IS NULL",
            name='check_transfer_completed_after_processed'
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'in_transit', 'completed', 'failed', 'cancelled', 'returned', 'on_hold')",
            name='check_transfer_status'
        ),
        CheckConstraint(
            "priority IN ('standard', 'express', 'urgent')",
            name='check_transfer_priority'
        ),
        Index('idx_money_transfers_user_status', 'user_id', 'status'),
        Index('idx_money_transfers_status_date', 'status', 'initiated_at'),
        Index('idx_money_transfers_type_date', 'transfer_type', 'initiated_at'),
        Index('idx_money_transfers_external_ref', 'external_reference'),
    )

    @validates('source_currency', 'destination_currency')
    def validate_currency(self, key, currency):
        """Validate currency code format."""
        if currency and not re.match(r'^[A-Z]{3}$', currency):
            raise ValueError(f"{key} must be a 3-letter ISO code")
        return currency.upper() if currency else currency

    @validates('status')
    def validate_status(self, key, status):
        """Validate transfer status."""
        valid_statuses = ['pending', 'processing', 'in_transit', 'completed', 'failed', 'cancelled', 'returned', 'on_hold']
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")
        return status

    @validates('priority')
    def validate_priority(self, key, priority):
        """Validate transfer priority."""
        valid_priorities = ['standard', 'express', 'urgent']
        if priority not in valid_priorities:
            raise ValueError(f"Invalid priority: {priority}. Must be one of {valid_priorities}")
        return priority


class Transfer(Base, TimestampMixin):
    """Transfer model for account-to-account transfers."""
    __tablename__ = "transfers"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    from_account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    to_account_id = Column(String, ForeignKey("accounts.id"), nullable=False)

    # Transfer details
    amount = Column(DECIMAL(precision=15, scale=2), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    description = Column(String)
    reference_number = Column(String)
    status = Column(String, nullable=False)  # pending, processing, completed, failed

    # Fees
    fee_amount = Column(DECIMAL(precision=15, scale=2), default=0.00)

    # Timing
    requested_date = Column(DateTime(timezone=True), default=func.now())
    processed_date = Column(DateTime(timezone=True))
    completed_date = Column(DateTime(timezone=True))

    # Relationships
    user = relationship("User")
    from_account = relationship("Account", foreign_keys=[from_account_id])
    to_account = relationship("Account", foreign_keys=[to_account_id])


# Additional indexes for models that don't have table constraints yet
# These will be moved to __table_args__ in future updates

# Investment indexes (to be moved to Investment model)
Index('idx_investments_user_id', Investment.user_id)
Index('idx_investments_account_id', Investment.account_id)
Index('idx_investments_symbol', Investment.symbol)
Index('idx_investments_type', Investment.investment_type)
Index('idx_investments_purchase_date', Investment.purchase_date)

# P2P Transaction indexes (to be moved to P2PTransaction model)
Index('idx_p2p_sender', P2PTransaction.sender_id)
Index('idx_p2p_recipient', P2PTransaction.recipient_id)
Index('idx_p2p_status', P2PTransaction.status)
Index('idx_p2p_date', P2PTransaction.requested_date)

# Transfer indexes (to be moved to Transfer model)
Index('idx_transfers_user_id', Transfer.user_id)
Index('idx_transfers_from_account', Transfer.from_account_id)
Index('idx_transfers_to_account', Transfer.to_account_id)
Index('idx_transfers_status', Transfer.status)
Index('idx_transfers_date', Transfer.requested_date)
