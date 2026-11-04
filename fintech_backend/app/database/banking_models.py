"""
Tables for beneficiaries, Plaid data and bank transfers.

Column names match the Pydantic models in models/transfer.py and models/plaid.py,
so banking_repository.py can convert between them without per-field mapping.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, DECIMAL, ForeignKey, Index, JSON, String, Text, UniqueConstraint
)

from .config import Base
from .encryption import EncryptedString


class BankBeneficiary(Base):
    """Someone a user has saved to send money to."""
    __tablename__ = "bank_beneficiaries"

    beneficiary_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    beneficiary_type = Column(String(20), nullable=False)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    business_name = Column(String(100))

    email = Column(String)
    phone_number = Column(String)

    address_line1 = Column(String(100), nullable=False)
    address_line2 = Column(String(100))
    city = Column(String(50), nullable=False)
    state_province = Column(String(50))
    postal_code = Column(String(20), nullable=False)
    country = Column(String(2), nullable=False)

    bank_name = Column(String(100), nullable=False)
    bank_code = Column(String(20))
    swift_bic = Column(String(11))
    account_number = Column(EncryptedString, nullable=False)
    iban = Column(EncryptedString)

    mobile_money_provider = Column(String)
    mobile_money_number = Column(EncryptedString)

    status = Column(String(30), nullable=False)
    is_favorite = Column(Boolean, default=False, nullable=False)
    verification_date = Column(DateTime)

    nickname = Column(String(50))
    relationship = Column(String(50))
    notes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class PlaidConnectionRecord(Base):
    """A user's link to their bank through Plaid."""
    __tablename__ = "plaid_connections"

    connection_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(String, nullable=False, unique=True)
    access_token = Column(EncryptedString, nullable=False)
    status = Column(String(20), nullable=False)
    institution_id = Column(String)
    institution_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_synced_at = Column(DateTime)
    error_message = Column(Text)


class PlaidAccountRecord(Base):
    """A bank account reached through a Plaid connection."""
    __tablename__ = "plaid_accounts"

    account_id = Column(String, primary_key=True)
    connection_id = Column(
        String, ForeignKey("plaid_connections.connection_id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String, nullable=False)
    official_name = Column(String)
    type = Column(String)
    subtype = Column(String)
    mask = Column(String)
    balances = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class PlaidTransactionRecord(Base):
    """A bank transaction synced from Plaid."""
    __tablename__ = "plaid_transactions"
    __table_args__ = (Index("ix_plaid_transactions_connection_date", "connection_id", "date"),)

    transaction_id = Column(String, primary_key=True)
    account_id = Column(String, nullable=False, index=True)
    connection_id = Column(
        String, ForeignKey("plaid_connections.connection_id", ondelete="CASCADE"), nullable=False
    )
    amount = Column(DECIMAL(precision=15, scale=2), nullable=False)
    iso_currency_code = Column(String(3))
    unofficial_currency_code = Column(String)
    date = Column(String(10), nullable=False)
    authorized_date = Column(String(10))
    name = Column(String, nullable=False)
    merchant_name = Column(String)
    payment_channel = Column(String)
    pending = Column(Boolean, default=False, nullable=False)
    pending_transaction_id = Column(String)
    account_owner = Column(String)
    transaction_type = Column(String)
    transaction_code = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class PlaidLinkTokenRecord(Base):
    """A Plaid Link session started by a user."""
    __tablename__ = "plaid_link_tokens"

    link_token_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    link_token = Column(EncryptedString, nullable=False)
    expiration = Column(String)
    request_id = Column(String)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class BankTransferQuote(Base):
    """A priced transfer a user can accept once, until it expires."""
    __tablename__ = "bank_transfer_quotes"

    quote_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_account_id = Column(String, nullable=False)
    beneficiary_id = Column(String, nullable=False)
    from_amount = Column(DECIMAL(precision=15, scale=2), nullable=False)
    from_currency = Column(String(3), nullable=False)
    to_amount = Column(DECIMAL(precision=15, scale=2), nullable=False)
    to_currency = Column(String(3), nullable=False)
    transfer_fee = Column(DECIMAL(precision=15, scale=2), nullable=False)
    exchange_fee = Column(DECIMAL(precision=15, scale=2), nullable=False)
    total_fees = Column(DECIMAL(precision=15, scale=2), nullable=False)
    total_cost = Column(DECIMAL(precision=15, scale=2), nullable=False)
    transfer_type = Column(String(30), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    used_at = Column(DateTime)


class BankTransfer(Base):
    """A money transfer and its status history."""
    __tablename__ = "bank_transfers"
    __table_args__ = (UniqueConstraint("quote_id", name="uq_bank_transfers_quote_id"),)

    transfer_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_account_id = Column(String, nullable=False)
    beneficiary_id = Column(String, nullable=False)
    transfer_type = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, index=True)
    priority = Column(String(20), nullable=False)
    source_amount = Column(DECIMAL(precision=15, scale=2), nullable=False)
    source_currency = Column(String(3), nullable=False)
    destination_amount = Column(DECIMAL(precision=15, scale=2), nullable=False)
    destination_currency = Column(String(3), nullable=False)
    exchange_rate_used = Column(DECIMAL(precision=15, scale=6))
    transfer_fee = Column(DECIMAL(precision=15, scale=2), nullable=False)
    exchange_fee = Column(DECIMAL(precision=15, scale=2), nullable=False)
    total_fees = Column(DECIMAL(precision=15, scale=2), nullable=False)
    total_cost = Column(DECIMAL(precision=15, scale=2), nullable=False)
    purpose = Column(String(200), nullable=False)
    reference = Column(String(50))
    recipient_message = Column(String(200))
    quote_id = Column(String)
    external_reference = Column(String)
    failure_reason = Column(Text)
    initiated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime)
    completed_at = Column(DateTime)
    estimated_arrival = Column(DateTime)
    status_history = Column(JSON, default=list, nullable=False)
    compliance_check_passed = Column(Boolean, default=False, nullable=False)
    requires_documents = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class TransactionMetadata(Base):
    """A user's own notes and tags on a bank transaction."""
    __tablename__ = "bank_transaction_metadata"

    transaction_id = Column(String, primary_key=True)
    data = Column(JSON, default=dict, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
