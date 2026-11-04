"""
Saved cards: what a user pays Hoardrun with.

Only display details are kept: the last four digits, brand, expiry and holder name, plus
Paystack's card signature (a non-secret fingerprint) to recognise the same card again.
Full card numbers, CVVs and Paystack authorization codes are never stored here.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, DECIMAL, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Session

from ..database.config import Base

BRANDS = {"visa", "mastercard", "american_express", "discover", "verve"}


class SavedCard(Base):
    __tablename__ = "saved_cards"
    __table_args__ = (UniqueConstraint("user_id", "signature", name="uq_saved_card_signature"),)

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(12), nullable=False, default="debit_card")
    holder_name = Column(String(80), nullable=False, default="Card holder")
    last4 = Column(String(4), nullable=False)
    brand = Column(String(20), nullable=False, default="visa")
    exp_month = Column(Integer)
    exp_year = Column(Integer)
    bank = Column(String(80))
    # manual (typed in) or paystack (seen on a real payment)
    source = Column(String(10), nullable=False, default="manual")
    signature = Column(String(64))
    status = Column(String(10), nullable=False, default="active")
    is_default = Column(Boolean, nullable=False, default=False)
    contactless = Column(Boolean, nullable=False, default=True)
    online_payments = Column(Boolean, nullable=False, default=True)
    per_transaction_limit = Column(DECIMAL(18, 2))
    monthly_limit = Column(DECIMAL(18, 2))
    last_used_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


def card_tag(card_id: str) -> str:
    """How a transaction records which saved card paid for it."""
    return f"card:{card_id}"


def normalise_brand(value: Optional[str]) -> str:
    brand = (value or "").strip().lower().replace(" ", "_")
    if brand in {"amex", "americanexpress"}:
        brand = "american_express"
    return brand if brand in BRANDS else "visa"


def remember_card(
    db: Session,
    user_id: str,
    *,
    last4: str,
    brand: Optional[str],
    source: str,
    signature: Optional[str] = None,
    exp_month=None,
    exp_year=None,
    holder: Optional[str] = None,
    bank: Optional[str] = None,
    credit: bool = False,
) -> Optional[SavedCard]:
    """Save, or find again by its signature, a card seen on a real payment. Display details only."""
    last4 = str(last4 or "")
    if len(last4) != 4 or not last4.isdigit():
        return None
    signature = (str(signature)[:64] or None) if signature else None
    card = None
    if signature:
        card = db.query(SavedCard).filter(SavedCard.user_id == user_id, SavedCard.signature == signature).first()
    if card is None:
        has_cards = db.query(SavedCard.id).filter(SavedCard.user_id == user_id).first() is not None
        try:
            exp_month, exp_year = int(exp_month), int(exp_year)
        except (TypeError, ValueError):
            exp_month = exp_year = None
        card = SavedCard(
            id=str(uuid.uuid4()), user_id=user_id, last4=last4, brand=normalise_brand(brand),
            kind="credit_card" if credit else "debit_card", holder_name=(holder or "Card holder")[:80],
            exp_month=exp_month, exp_year=exp_year, bank=bank or None, source=source, signature=signature,
            is_default=not has_cards,
        )
        db.add(card)
    card.last_used_at = datetime.utcnow()
    return card


def remember_paystack_card(db: Session, user_id: str, authorization: Optional[dict]) -> Optional[SavedCard]:
    """The card a Paystack payment was made with. Returns None for non-card payments."""
    if not isinstance(authorization, dict) or authorization.get("channel", "card") != "card":
        return None
    return remember_card(
        db, user_id, last4=authorization.get("last4"), brand=authorization.get("card_type") or authorization.get("brand"),
        source="paystack", signature=authorization.get("signature"), exp_month=authorization.get("exp_month"),
        exp_year=authorization.get("exp_year"), holder=authorization.get("account_name"), bank=authorization.get("bank"),
        credit="credit" in str(authorization.get("card_type", "")).lower(),
    )


def remember_stripe_card(db: Session, user_id: str, card: Optional[dict]) -> Optional[SavedCard]:
    """The card a Stripe payment was made with (payment_method.card). Its fingerprint identifies it again."""
    if not isinstance(card, dict):
        return None
    return remember_card(
        db, user_id, last4=card.get("last4"), brand=card.get("brand"), source="stripe", signature=card.get("fingerprint"),
        exp_month=card.get("exp_month"), exp_year=card.get("exp_year"), credit=card.get("funding") == "credit",
    )
