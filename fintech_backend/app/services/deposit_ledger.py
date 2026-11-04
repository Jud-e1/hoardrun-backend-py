"""
Credits confirmed card deposits to a user's Hoardrun cash account.

A payment is credited at most once: a fingerprint of its Paystack reference
becomes the transaction's unique reference number, so a repeat (the browser returning
twice, or the webhook arriving after verification) finds the first credit
instead of adding the money again.
"""

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database.models import (
    Account, AccountStatusEnum, AccountTypeEnum, PaymentMethodEnum, Transaction,
    TransactionDirectionEnum, TransactionStatusEnum, TransactionTypeEnum,
)
from .card_vault import card_tag, remember_paystack_card, remember_stripe_card
from .inbox import notify


def _new_account_number(db: Session) -> str:
    while True:
        number = f"HR{secrets.randbelow(10**12):012d}"
        if not db.query(Account.id).filter(Account.account_number == number).first():
            return number


def cash_account(db: Session, user_id: str, currency: str) -> Account:
    """The account deposits land in: the primary active one in this currency, created on first deposit."""
    account = (
        db.query(Account)
        .filter(Account.user_id == user_id, Account.currency == currency, Account.status == AccountStatusEnum.ACTIVE)
        .order_by(Account.is_primary.desc(), Account.created_at.asc())
        .with_for_update()
        .first()
    )
    if account is None:
        account = Account(
            id=str(uuid.uuid4()),
            user_id=user_id,
            account_number=_new_account_number(db),
            account_name=f"Cash ({currency})",
            account_type=AccountTypeEnum.CHECKING,
            currency=currency,
            is_primary=not db.query(Account.id).filter(Account.user_id == user_id).first(),
            current_balance=Decimal("0"),
            available_balance=Decimal("0"),
        )
        db.add(account)
        db.flush()
    return account


def ledger_reference(paystack_reference: str) -> str:
    """Transaction references allow only A-Z, 0-9 and hyphens, so store a stable fingerprint."""
    return "PS-" + hashlib.sha256(paystack_reference.encode("utf-8")).hexdigest()[:40].upper()


def credit_deposit(
    db: Session,
    *,
    user_id: str,
    reference: str,
    amount_minor: int,
    currency: str,
    paid_at: Optional[datetime] = None,
    card_authorization: Optional[dict] = None,
    provider: str = "Paystack",
    stripe_card: Optional[dict] = None,
) -> tuple[Transaction, bool]:
    """Add a confirmed payment to the user's cash. Returns the transaction and whether it was new."""
    key = ledger_reference(reference)
    existing = db.query(Transaction).filter(Transaction.reference_number == key).first()
    if existing is not None:
        return existing, False

    amount = (Decimal(amount_minor) / 100).quantize(Decimal("0.01"))
    if amount <= 0:
        raise ValueError("A deposit has to be more than zero")
    currency = currency.upper()

    account = cash_account(db, user_id, currency)
    # The card paid with is saved (display details only) so it shows on the Cards page with this deposit
    card = remember_stripe_card(db, user_id, stripe_card) if stripe_card else remember_paystack_card(db, user_id, card_authorization)
    if card is not None:
        db.flush()
    account.current_balance = Decimal(account.current_balance) + amount
    account.available_balance = Decimal(account.available_balance) + amount
    when = paid_at or datetime.now(timezone.utc)
    transaction = Transaction(
        id=str(uuid.uuid4()),
        user_id=user_id,
        account_id=account.id,
        transaction_type=TransactionTypeEnum.DEPOSIT,
        status=TransactionStatusEnum.COMPLETED,
        direction=TransactionDirectionEnum.INBOUND,
        amount=amount,
        currency=currency,
        description=f"Card deposit · {card.brand.replace('_', ' ').title()} •••• {card.last4}" if card is not None else "Card deposit",
        merchant_name=provider,
        payment_method=PaymentMethodEnum.CARD,
        reference_number=key,
        notes=f"{provider} reference {reference}",
        tags=[card_tag(card.id)] if card is not None else None,
        transaction_date=when,
        posted_date=datetime.now(timezone.utc),
        balance_after=account.current_balance,
    )
    db.add(transaction)
    notify(db, user_id, "transaction", "Money added", f"${amount:,.2f} from your card is in your account.",
           link="/home", key=f"deposit:{key}", email=True)
    try:
        db.commit()
    except IntegrityError:
        # The same payment was credited at the same moment by another request
        db.rollback()
        return db.query(Transaction).filter(Transaction.reference_number == key).one(), False
    return transaction, True


def credit_paystack_charge(db: Session, charge: dict, expected_user_id: Optional[str] = None):
    """Credit a successful Paystack charge to the user named in its metadata.

    Returns (transaction, was_new), or None when the charge isn't a successful payment
    started by Hoardrun. Raises PermissionError when the charge belongs to someone else.
    """
    if charge.get("status") != "success":
        return None
    metadata = charge.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except ValueError:
            metadata = {}
    user_id = str(metadata.get("user_id") or "")
    if not user_id:
        return None
    if expected_user_id is not None and user_id != str(expected_user_id):
        raise PermissionError("This payment belongs to a different user")
    paid_at = charge.get("paid_at")
    if isinstance(paid_at, str):
        try:
            paid_at = datetime.fromisoformat(paid_at.replace("Z", "+00:00"))
        except ValueError:
            paid_at = None
    return credit_deposit(
        db,
        user_id=user_id,
        reference=str(charge["reference"]),
        amount_minor=int(charge["amount"]),
        currency=str(charge.get("currency") or "USD"),
        paid_at=paid_at,
        card_authorization=charge.get("authorization"),
    )


def credit_stripe_session(db: Session, session: dict, expected_user_id: Optional[str] = None):
    """Credit a paid Stripe Checkout session to the user named in its metadata.

    Returns (transaction, was_new), or None when the session isn't a paid Hoardrun deposit.
    Raises PermissionError when the session belongs to someone else.
    """
    if session.get("payment_status") != "paid" or session.get("mode", "payment") != "payment":
        return None
    user_id = str((session.get("metadata") or {}).get("user_id") or "")
    if not user_id:
        return None
    if expected_user_id is not None and user_id != str(expected_user_id):
        raise PermissionError("This payment belongs to a different user")
    intent = session.get("payment_intent")
    method = intent.get("payment_method") if isinstance(intent, dict) else None
    card = method.get("card") if isinstance(method, dict) else None
    created = session.get("created")
    paid_at = datetime.fromtimestamp(created, tz=timezone.utc) if isinstance(created, (int, float)) else None
    return credit_deposit(
        db,
        user_id=user_id,
        reference=str(session["id"]),
        amount_minor=int(session["amount_total"]),
        currency=str(session.get("currency") or "usd"),
        paid_at=paid_at,
        provider="Stripe",
        stripe_card=card,
    )
