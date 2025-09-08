"""
SQLAlchemy database models for the fintech backend.
"""
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.types import DECIMAL
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
import uuid

from app.database.config import Base


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
    """User model."""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    phone_number = Column(String)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Relationships
    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    cards = relationship("Card", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")


class Account(Base, TimestampMixin):
    """Account model."""
    __tablename__ = "accounts"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    account_number = Column(String, unique=True, nullable=False, index=True)
    account_name = Column(String, nullable=False)
    account_type = Column(SQLEnum(AccountTypeEnum), nullable=False)
    status = Column(SQLEnum(AccountStatusEnum), default=AccountStatusEnum.ACTIVE)
    
    # Balance information
    current_balance = Column(DECIMAL(precision=15, scale=2), default=0.00, nullable=False)
    available_balance = Column(DECIMAL(precision=15, scale=2), default=0.00, nullable=False)
    pending_balance = Column(DECIMAL(precision=15, scale=2), default=0.00, nullable=False)
    reserved_balance = Column(DECIMAL(precision=15, scale=2), default=0.00, nullable=False)
    overdraft_limit = Column(DECIMAL(precision=15, scale=2), default=0.00)
    
    # Account settings
    currency = Column(String(3), default="USD", nullable=False)
    is_primary = Column(Boolean, default=False)
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


class Transaction(Base, TimestampMixin):
    """Transaction model."""
    __tablename__ = "transactions"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False, index=True)
    
    # Transaction details
    transaction_type = Column(SQLEnum(TransactionTypeEnum), nullable=False)
    status = Column(SQLEnum(TransactionStatusEnum), nullable=False)
    direction = Column(SQLEnum(TransactionDirectionEnum), nullable=False)
    
    # Amount and currency
    amount = Column(DECIMAL(precision=15, scale=2), nullable=False)
    currency = Column(String(3), nullable=False)
    exchange_rate = Column(DECIMAL(precision=10, scale=6))
    original_amount = Column(DECIMAL(precision=15, scale=2))
    original_currency = Column(String(3))
    
    # Description and categorization
    description = Column(String, nullable=False)
    merchant_name = Column(String)
    merchant_category = Column(SQLEnum(MerchantCategoryEnum), default=MerchantCategoryEnum.OTHER)
    
    # Payment details
    payment_method = Column(SQLEnum(PaymentMethodEnum), nullable=False)
    card_id = Column(String, ForeignKey("cards.id"))
    reference_number = Column(String)
    
    # Location and metadata
    location = Column(String)
    tags = Column(JSON)  # Store as JSON array
    notes = Column(Text)
    
    # Timing
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    posted_date = Column(DateTime(timezone=True))
    
    # Fees and charges
    fee_amount = Column(DECIMAL(precision=15, scale=2), default=0.00)
    
    # Balance tracking
    balance_after = Column(DECIMAL(precision=15, scale=2))
    
    # Dispute and fraud
    is_disputed = Column(Boolean, default=False)
    is_fraudulent = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="transactions")
    account = relationship("Account", back_populates="transactions")
    card = relationship("Card", back_populates="transactions")


class Card(Base, TimestampMixin):
    """Card model."""
    __tablename__ = "cards"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False, index=True)
    
    # Card details
    card_number_masked = Column(String, nullable=False)  # Only store masked version
    card_type = Column(SQLEnum(CardTypeEnum), nullable=False)
    status = Column(SQLEnum(CardStatusEnum), default=CardStatusEnum.ACTIVE)
    
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


# Database Indexes for Performance Optimization
from sqlalchemy import Index

# User indexes
Index('idx_users_email', User.email)
Index('idx_users_phone', User.phone_number)
Index('idx_users_active', User.is_active)

# Account indexes
Index('idx_accounts_user_id', Account.user_id)
Index('idx_accounts_number', Account.account_number)
Index('idx_accounts_type', Account.account_type)
Index('idx_accounts_status', Account.status)
Index('idx_accounts_primary', Account.is_primary)
Index('idx_accounts_user_type', Account.user_id, Account.account_type)

# Transaction indexes
Index('idx_transactions_user_id', Transaction.user_id)
Index('idx_transactions_account_id', Transaction.account_id)
Index('idx_transactions_date', Transaction.transaction_date)
Index('idx_transactions_type', Transaction.transaction_type)
Index('idx_transactions_status', Transaction.status)
Index('idx_transactions_direction', Transaction.direction)
Index('idx_transactions_merchant', Transaction.merchant_category)
Index('idx_transactions_user_date', Transaction.user_id, Transaction.transaction_date)
Index('idx_transactions_account_date', Transaction.account_id, Transaction.transaction_date)
Index('idx_transactions_status_date', Transaction.status, Transaction.transaction_date)

# Card indexes
Index('idx_cards_user_id', Card.user_id)
Index('idx_cards_account_id', Card.account_id)
Index('idx_cards_status', Card.status)
Index('idx_cards_type', Card.card_type)
Index('idx_cards_expiry', Card.expiry_year, Card.expiry_month)

# Investment indexes
Index('idx_investments_user_id', Investment.user_id)
Index('idx_investments_account_id', Investment.account_id)
Index('idx_investments_symbol', Investment.symbol)
Index('idx_investments_type', Investment.investment_type)
Index('idx_investments_purchase_date', Investment.purchase_date)

# P2P Transaction indexes
Index('idx_p2p_sender', P2PTransaction.sender_id)
Index('idx_p2p_recipient', P2PTransaction.recipient_id)
Index('idx_p2p_status', P2PTransaction.status)
Index('idx_p2p_date', P2PTransaction.requested_date)

# Transfer indexes
Index('idx_transfers_user_id', Transfer.user_id)
Index('idx_transfers_from_account', Transfer.from_account_id)
Index('idx_transfers_to_account', Transfer.to_account_id)
Index('idx_transfers_status', Transfer.status)
Index('idx_transfers_date', Transfer.requested_date)
