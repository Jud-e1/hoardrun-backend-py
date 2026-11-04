"""
Hoardrun cards: virtual Visa cards issued with Stripe Issuing, spending from Hoardrun cash.

- Getting a card needs a verified identity and a US billing address (kept for the cardholder).
- Every purchase is a real-time question from Stripe (issuing_authorization.request). Hoardrun
  answers within the webhook: yes only when the card is on and the cash covers it, and then
  holds that amount (available goes down, reserved goes up).
- When the merchant actually charges (issuing_transaction.created), the hold turns into the
  charge; a refund puts money back; a purchase that's cancelled or expires releases its hold.
  Each event is applied once, however often Stripe delivers it.
- The full card number and CVC are never seen by Hoardrun's server: the app shows them in
  Stripe's own fields using a short-lived key made here (/ephemeral-key).
"""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, DECIMAL, ForeignKey, Integer, String
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user_id
from ...config.settings import get_settings
from ...database.config import Base, get_db
from ...database.models import (
    Account, AccountStatusEnum, MerchantCategoryEnum, PaymentMethodEnum, Transaction, TransactionDirectionEnum,
    TransactionStatusEnum, TransactionTypeEnum, User,
)
from ...services.deposit_ledger import cash_account
from ...services.inbox import notify
from .identity import require_verified_identity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/issuing", tags=["cards"])

MAX_ACTIVE_CARDS = 2
# Stripe.js shows card details with an ephemeral key made for this API version
ELEMENTS_API_VERSION = "2020-03-02"
STATES = {"AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA",
          "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR",
          "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"}
# Stripe merchant categories, by keyword, onto the app's spending categories (budgets use these)
CATEGORY_WORDS = [
    ("grocery", MerchantCategoryEnum.GROCERIES), ("supermarket", MerchantCategoryEnum.GROCERIES),
    ("restaurant", MerchantCategoryEnum.RESTAURANTS), ("eating", MerchantCategoryEnum.RESTAURANTS),
    ("fast_food", MerchantCategoryEnum.RESTAURANTS), ("bar", MerchantCategoryEnum.RESTAURANTS),
    ("service_station", MerchantCategoryEnum.GAS_STATIONS), ("fuel", MerchantCategoryEnum.GAS_STATIONS),
    ("airline", MerchantCategoryEnum.TRAVEL), ("hotel", MerchantCategoryEnum.TRAVEL), ("lodging", MerchantCategoryEnum.TRAVEL),
    ("travel", MerchantCategoryEnum.TRAVEL), ("taxi", MerchantCategoryEnum.TRAVEL), ("car_rental", MerchantCategoryEnum.TRAVEL),
    ("medical", MerchantCategoryEnum.HEALTHCARE), ("drug", MerchantCategoryEnum.HEALTHCARE), ("doctor", MerchantCategoryEnum.HEALTHCARE),
    ("utilit", MerchantCategoryEnum.UTILITIES), ("telecom", MerchantCategoryEnum.UTILITIES),
    ("school", MerchantCategoryEnum.EDUCATION), ("college", MerchantCategoryEnum.EDUCATION),
    ("automotive", MerchantCategoryEnum.AUTOMOTIVE), ("auto_", MerchantCategoryEnum.AUTOMOTIVE),
    ("home_supply", MerchantCategoryEnum.HOME_IMPROVEMENT), ("hardware", MerchantCategoryEnum.HOME_IMPROVEMENT),
    ("insurance", MerchantCategoryEnum.INSURANCE), ("government", MerchantCategoryEnum.GOVERNMENT),
    ("charit", MerchantCategoryEnum.CHARITY), ("digital", MerchantCategoryEnum.ONLINE_SERVICES),
    ("computer", MerchantCategoryEnum.ONLINE_SERVICES), ("streaming", MerchantCategoryEnum.SUBSCRIPTION),
    ("theater", MerchantCategoryEnum.ENTERTAINMENT), ("amusement", MerchantCategoryEnum.ENTERTAINMENT),
    ("record_stores", MerchantCategoryEnum.ENTERTAINMENT), ("store", MerchantCategoryEnum.RETAIL), ("shop", MerchantCategoryEnum.RETAIL),
]


# ---------- Storage ----------

class IssuingCardholder(Base):
    """The Stripe cardholder for a user, and the billing address they gave."""
    __tablename__ = "issuing_cardholders"

    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    stripe_cardholder_id = Column(String(60), unique=True, nullable=False)
    line1 = Column(String(120), nullable=False)
    line2 = Column(String(120))
    city = Column(String(80), nullable=False)
    state = Column(String(2), nullable=False)
    postal_code = Column(String(10), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class IssuedCard(Base):
    """A Hoardrun card. Display details only; Stripe keeps the number and CVC."""
    __tablename__ = "issued_cards"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stripe_card_id = Column(String(60), unique=True, nullable=False)
    last4 = Column(String(4), nullable=False)
    brand = Column(String(20), nullable=False, default="visa")
    exp_month = Column(Integer)
    exp_year = Column(Integer)
    # active, frozen (Stripe "inactive") or canceled
    status = Column(String(10), nullable=False, default="active")
    monthly_limit = Column(DECIMAL(18, 2))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class IssuingHold(Base):
    """Cash held for one approved purchase until the merchant charges or it's released."""
    __tablename__ = "issuing_holds"

    authorization_id = Column(String(60), primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    card_id = Column(String, ForeignKey("issued_cards.id"), nullable=False)
    held = Column(DECIMAL(18, 2), nullable=False)  # still held
    merchant = Column(String(120))
    category = Column(String(30))
    open = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ---------- Requests ----------

class Address(BaseModel):
    line1: str = Field(min_length=3, max_length=120)
    line2: Optional[str] = Field(None, max_length=120)
    city: str = Field(min_length=2, max_length=80)
    state: str = Field(min_length=2, max_length=2)
    postal_code: str = Field(pattern=r"^\d{5}(-\d{4})?$")


class NewCardRequest(BaseModel):
    # Needed the first time only
    billing: Optional[Address] = None
    # The person ticked "I agree to the Hoardrun Card terms"
    accept_terms: bool = False


class LimitRequest(BaseModel):
    monthly_limit: Decimal = Field(gt=0, le=10000, decimal_places=2)


class NonceRequest(BaseModel):
    nonce: str = Field(min_length=10, max_length=200)


# ---------- Stripe ----------

def get_client() -> stripe.StripeClient:
    key = get_settings().stripe_secret_key
    if not key:
        raise HTTPException(status_code=503, detail="Hoardrun cards aren't set up yet")
    return stripe.StripeClient(key)


def stripe_failed(error: Exception, what: str) -> HTTPException:
    logger.warning("Stripe Issuing %s failed: %s", what, error)
    message = getattr(error, "user_message", None)
    return HTTPException(status_code=502, detail=message or "The card service didn't accept that. Try again.")


def as_dict(obj) -> dict:
    return obj.to_dict() if hasattr(obj, "to_dict") else dict(obj)


def money(cents) -> Decimal:
    return (Decimal(abs(int(cents or 0))) / 100).quantize(Decimal("0.01"))


def category_for(merchant_category: Optional[str]) -> MerchantCategoryEnum:
    name = (merchant_category or "").lower()
    return next((category for word, category in CATEGORY_WORDS if word in name), MerchantCategoryEnum.OTHER)


def show(card: IssuedCard) -> dict:
    return {
        # Stripe's card ID isn't secret; Stripe.js needs it to show the details
        "id": card.id, "stripe_card_id": card.stripe_card_id, "last4": card.last4, "brand": card.brand, "exp_month": card.exp_month, "exp_year": card.exp_year,
        "status": card.status, "monthly_limit": float(card.monthly_limit) if card.monthly_limit is not None else None,
        "created_at": card.created_at.isoformat() + "Z",
    }


def owned(db: Session, user_id: str, card_id: str) -> IssuedCard:
    card = db.query(IssuedCard).filter(IssuedCard.id == card_id, IssuedCard.user_id == user_id).first()
    if card is None or card.status == "canceled":
        raise HTTPException(status_code=404, detail="That card wasn't found")
    return card


# ---------- Ledger ----------

def record(db: Session, user_id: str, account: Account, amount: Decimal, *, reference: str, merchant: str,
           category: Optional[str], direction: TransactionDirectionEnum, kind: TransactionTypeEnum,
           status: TransactionStatusEnum, card: Optional[IssuedCard]) -> Transaction:
    now = datetime.now(timezone.utc)
    entry = Transaction(
        id=str(uuid.uuid4()), user_id=user_id, account_id=account.id, transaction_type=kind, direction=direction,
        status=status, amount=amount, currency="USD", payment_method=PaymentMethodEnum.CARD,
        description=f"{merchant} · Hoardrun card •••• {card.last4}" if card else merchant,
        merchant_name=merchant, merchant_category=MerchantCategoryEnum(category) if category else MerchantCategoryEnum.OTHER,
        reference_number=reference, transaction_date=now, posted_date=now, balance_after=account.current_balance,
    )
    db.add(entry)
    return entry


def ref(prefix: str, stripe_id: str) -> str:
    return f"{prefix}-" + "".join(ch for ch in stripe_id.upper() if ch.isalnum())[-40:]


def decide(db: Session, authorization: dict) -> tuple[bool, str]:
    """Approve a purchase only if the card is on and the cash covers it; hold the money when approved."""
    auth_id = authorization["id"]
    if db.get(IssuingHold, auth_id) is not None:
        return True, "already approved"
    card = db.query(IssuedCard).filter(IssuedCard.stripe_card_id == (authorization.get("card") or {}).get("id")).first()
    if card is None or card.status != "active":
        return False, "card not active"
    pending = authorization.get("pending_request") or {}
    if str(pending.get("currency") or authorization.get("currency") or "usd").lower() != "usd":
        return False, "not usd"
    amount = money(pending.get("amount", authorization.get("amount")))
    if amount <= 0:
        return True, "zero amount check"
    account = (
        db.query(Account).filter(Account.user_id == card.user_id, Account.currency == "USD",
                                 Account.status == AccountStatusEnum.ACTIVE, Account.available_balance >= amount)
        .order_by(Account.is_primary.desc(), Account.available_balance.desc()).with_for_update().first()
    )
    if account is None:
        merchant = ((authorization.get("merchant_data") or {}).get("name") or "a merchant")[:120]
        notify(db, card.user_id, "warning", "Card payment declined",
               f"A ${amount:,.2f} payment at {merchant} was declined: there wasn't enough in your Hoardrun cash.",
               link="/home", key=f"card-declined:{auth_id}", email=True)
        db.commit()
        return False, "insufficient funds"
    merchant_data = authorization.get("merchant_data") or {}
    merchant = (merchant_data.get("name") or "Card payment")[:120]
    category = category_for(merchant_data.get("category")).value
    account.available_balance = Decimal(account.available_balance) - amount
    account.reserved_balance = Decimal(account.reserved_balance or 0) + amount
    db.add(IssuingHold(authorization_id=auth_id, user_id=card.user_id, account_id=account.id, card_id=card.id,
                       held=amount, merchant=merchant, category=category))
    record(db, card.user_id, account, amount, reference=ref("ICA", auth_id), merchant=merchant, category=category,
           direction=TransactionDirectionEnum.OUTBOUND, kind=TransactionTypeEnum.CARD_PAYMENT,
           status=TransactionStatusEnum.PENDING, card=card)
    db.commit()
    return True, "approved"


def release(db: Session, hold: IssuingHold, amount: Optional[Decimal] = None) -> Decimal:
    """Give back some or all of what's still held."""
    give = min(Decimal(hold.held), amount if amount is not None else Decimal(hold.held))
    if give <= 0:
        return Decimal(0)
    account = db.query(Account).filter(Account.id == hold.account_id).with_for_update().one()
    account.reserved_balance = max(Decimal(account.reserved_balance or 0) - give, Decimal(0))
    account.available_balance = Decimal(account.available_balance) + give
    hold.held = Decimal(hold.held) - give
    return give


def authorization_closed(db: Session, authorization: dict) -> None:
    """A purchase that ended without (more) charges: whatever is still held goes back."""
    hold = db.query(IssuingHold).filter(IssuingHold.authorization_id == authorization["id"]).with_for_update().first()
    if hold is None or not hold.open:
        return
    if authorization.get("status") in ("closed", "reversed", "expired"):
        release(db, hold)
        hold.open = False
        pending = db.query(Transaction).filter(Transaction.reference_number == ref("ICA", hold.authorization_id)).first()
        if pending is not None and pending.status == TransactionStatusEnum.PENDING:
            pending.status = TransactionStatusEnum.CANCELLED
        db.commit()


def apply_transaction(db: Session, txn: dict) -> None:
    """A merchant's charge (capture) or refund, applied once."""
    reference = ref("ICT", txn["id"])
    if db.query(Transaction.id).filter(Transaction.reference_number == reference).first():
        return
    card = db.query(IssuedCard).filter(IssuedCard.stripe_card_id == (txn.get("card") if isinstance(txn.get("card"), str) else (txn.get("card") or {}).get("id"))).first()
    if card is None:
        logger.error("Issuing transaction %s for an unknown card", txn["id"])
        return
    amount = money(txn.get("amount"))
    if amount <= 0:
        return
    auth = txn.get("authorization")
    auth_id = auth if isinstance(auth, str) else (auth or {}).get("id")
    hold = db.query(IssuingHold).filter(IssuingHold.authorization_id == auth_id).with_for_update().first() if auth_id else None
    merchant_data = txn.get("merchant_data") or {}
    merchant = (merchant_data.get("name") or (hold.merchant if hold else None) or "Card payment")[:120]
    category = hold.category if hold else category_for(merchant_data.get("category")).value

    if txn.get("type") == "refund":
        account = cash_account(db, card.user_id, "USD")
        account.current_balance = Decimal(account.current_balance) + amount
        account.available_balance = Decimal(account.available_balance) + amount
        record(db, card.user_id, account, amount, reference=reference, merchant=merchant, category=category,
               direction=TransactionDirectionEnum.INBOUND, kind=TransactionTypeEnum.REFUND,
               status=TransactionStatusEnum.COMPLETED, card=card)
        notify(db, card.user_id, "transaction", "Card refund", f"${amount:,.2f} from {merchant} is back in your cash.",
               link="/transactions", key=f"card-refund:{txn['id']}", email=True)
        db.commit()
        return

    # A charge: the held money becomes the payment; anything beyond the hold comes from available cash
    account_id = hold.account_id if hold else cash_account(db, card.user_id, "USD").id
    if hold is not None:
        release(db, hold, amount)
        if Decimal(hold.held) <= 0:
            hold.open = False
    account = db.query(Account).filter(Account.id == account_id).with_for_update().one()
    taken = min(amount, Decimal(account.available_balance))
    if taken < amount:
        logger.error("Card charge %s exceeded cash by $%s", txn["id"], amount - taken)
    account.available_balance = Decimal(account.available_balance) - taken
    account.current_balance = Decimal(account.current_balance) - taken
    pending = db.query(Transaction).filter(Transaction.reference_number == ref("ICA", auth_id)).first() if auth_id else None
    if pending is not None and pending.status == TransactionStatusEnum.PENDING:
        # The pending line becomes the charge, with the final amount
        pending.status, pending.amount, pending.reference_number = TransactionStatusEnum.COMPLETED, amount, reference
        pending.balance_after = account.current_balance
    else:
        record(db, card.user_id, account, amount, reference=reference, merchant=merchant, category=category,
               direction=TransactionDirectionEnum.OUTBOUND, kind=TransactionTypeEnum.CARD_PAYMENT,
               status=TransactionStatusEnum.COMPLETED, card=card)
    db.commit()


# ---------- Routes ----------

@router.get("/config")
async def config():
    settings = get_settings()
    return {"configured": bool(settings.stripe_secret_key), "publishable_key": settings.stripe_publishable_key or None,
            "monthly_limit": settings.issuing_monthly_limit}


@router.get("/cards")
async def list_cards(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    cards = (db.query(IssuedCard).filter(IssuedCard.user_id == user_id, IssuedCard.status != "canceled")
             .order_by(IssuedCard.created_at.asc()).all())
    holder = db.get(IssuingCardholder, user_id)
    return {"cards": [show(card) for card in cards], "has_billing_address": holder is not None}


@router.post("/cards")
async def create_card(payload: NewCardRequest, request: Request, user_id: str = Depends(get_current_user_id),
                      db: Session = Depends(get_db)):
    require_verified_identity(db, user_id, "get a Hoardrun card")
    client = get_client()
    if not payload.accept_terms:
        raise HTTPException(status_code=400, detail="Agree to the Hoardrun Card terms to get a card.")
    active = db.query(IssuedCard).filter(IssuedCard.user_id == user_id, IssuedCard.status != "canceled").count()
    if active >= MAX_ACTIVE_CARDS:
        raise HTTPException(status_code=409, detail=f"You can have up to {MAX_ACTIVE_CARDS} Hoardrun cards. Cancel one to get another.")
    user = db.get(User, user_id)
    holder = db.get(IssuingCardholder, user_id)
    try:
        if holder is None:
            billing = payload.billing
            if billing is None:
                raise HTTPException(status_code=400, detail="Add your US billing address to get a card.")
            if billing.state.upper() not in STATES:
                raise HTTPException(status_code=400, detail="Use a US state, like CA or NY.")
            address = {"line1": billing.line1.strip(), "city": billing.city.strip(), "state": billing.state.upper(),
                       "postal_code": billing.postal_code, "country": "US"}
            if billing.line2:
                address["line2"] = billing.line2.strip()
            created = client.v1.issuing.cardholders.create(params={
                "type": "individual", "name": f"{user.first_name} {user.last_name}".strip()[:24], "email": user.email,
                "billing": {"address": address}, "status": "active",
                "individual": {"first_name": user.first_name, "last_name": user.last_name,
                               "card_issuing": {"user_terms_acceptance": {
                                   "date": int(datetime.now(timezone.utc).timestamp()),
                                   "ip": request.client.host if request.client else "127.0.0.1"}}},
                "metadata": {"user_id": user_id},
            })
            holder = IssuingCardholder(user_id=user_id, stripe_cardholder_id=created.id, line1=address["line1"],
                                       line2=address.get("line2"), city=address["city"], state=address["state"],
                                       postal_code=address["postal_code"])
            db.add(holder)
            db.flush()
        limit = int(get_settings().issuing_monthly_limit)
        made = as_dict(client.v1.issuing.cards.create(params={
            "cardholder": holder.stripe_cardholder_id, "currency": "usd", "type": "virtual", "status": "active",
            "spending_controls": {"spending_limits": [{"amount": limit * 100, "interval": "monthly"}]},
            "metadata": {"user_id": user_id},
        }))
    except stripe.StripeError as error:
        db.rollback()
        raise stripe_failed(error, "card create")
    card = IssuedCard(id=str(uuid.uuid4()), user_id=user_id, stripe_card_id=made["id"], last4=made.get("last4") or "0000",
                      brand=(made.get("brand") or "visa").lower(), exp_month=made.get("exp_month"), exp_year=made.get("exp_year"),
                      status="active", monthly_limit=Decimal(limit))
    db.add(card)
    notify(db, user_id, "security", "New Hoardrun card",
           f"A virtual card ending {card.last4} was added to your account. If this wasn't you, freeze it right away.",
           link="/cards", key=f"card-issued:{card.id}")
    db.commit()
    return show(card)


def set_status(db: Session, user_id: str, card_id: str, status: str) -> dict:
    card = owned(db, user_id, card_id)
    try:
        get_client().v1.issuing.cards.update(card.stripe_card_id, params={"status": {"active": "active", "frozen": "inactive", "canceled": "canceled"}[status]})
    except stripe.StripeError as error:
        raise stripe_failed(error, "card status")
    card.status = status
    db.commit()
    return show(card)


@router.post("/cards/{card_id}/freeze")
async def freeze(card_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return set_status(db, user_id, card_id, "frozen")


@router.post("/cards/{card_id}/unfreeze")
async def unfreeze(card_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return set_status(db, user_id, card_id, "active")


@router.delete("/cards/{card_id}")
async def cancel(card_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Cancelling is permanent; purchases already approved still complete."""
    return set_status(db, user_id, card_id, "canceled")


@router.put("/cards/{card_id}/limit")
async def set_limit(card_id: str, payload: LimitRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    card = owned(db, user_id, card_id)
    limit = payload.monthly_limit.quantize(Decimal("1"))
    try:
        get_client().v1.issuing.cards.update(card.stripe_card_id, params={
            "spending_controls": {"spending_limits": [{"amount": int(limit) * 100, "interval": "monthly"}]}})
    except stripe.StripeError as error:
        raise stripe_failed(error, "card limit")
    card.monthly_limit = limit
    db.commit()
    return show(card)


@router.post("/cards/{card_id}/ephemeral-key")
async def ephemeral_key(card_id: str, payload: NonceRequest, user_id: str = Depends(get_current_user_id),
                        db: Session = Depends(get_db)):
    """A short-lived key so Stripe.js can show this card's number and CVC to its owner."""
    card = owned(db, user_id, card_id)
    try:
        key = get_client().v1.ephemeral_keys.create(params={"issuing_card": card.stripe_card_id, "nonce": payload.nonce},
                                                   options={"stripe_version": ELEMENTS_API_VERSION})
    except stripe.StripeError as error:
        raise stripe_failed(error, "ephemeral key")
    return {"secret": key.secret, "stripe_card_id": card.stripe_card_id}


def cancel_all_cards(db: Session, user_id: str) -> None:
    """Used when an account closes: every Hoardrun card is cancelled at Stripe and here."""
    for card in db.query(IssuedCard).filter(IssuedCard.user_id == user_id, IssuedCard.status != "canceled").all():
        try:
            get_client().v1.issuing.cards.update(card.stripe_card_id, params={"status": "canceled"})
        except Exception as error:  # closing the account mustn't fail because Stripe didn't answer
            logger.error("Couldn't cancel card %s at Stripe: %s", card.id, error)
        card.status = "canceled"


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    secret = get_settings().stripe_issuing_webhook_secret
    if not secret:
        raise HTTPException(status_code=503, detail="Issuing webhook isn't set up")
    client = get_client()
    payload = await request.body()
    try:
        event = client.construct_event(payload, request.headers.get("stripe-signature"), secret)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid signature")
    obj = as_dict(event.data.object)

    if event.type == "issuing_authorization.request":
        approved, why = decide(db, obj)
        logger.info("Card authorization %s %s (%s)", obj.get("id"), "approved" if approved else "declined", why)
        # Answered in the response itself, within Stripe's 2-second window
        return JSONResponse({"approved": approved}, headers={"Stripe-Version": stripe.api_version})
    if event.type in ("issuing_authorization.updated", "issuing_authorization.created"):
        authorization_closed(db, obj)
    elif event.type == "issuing_transaction.created":
        apply_transaction(db, obj)
    return {"received": True}
