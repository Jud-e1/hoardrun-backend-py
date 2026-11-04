"""
Card deposits through Stripe Checkout, for US customers.

The person pays on Stripe's hosted page, so card details never touch Hoardrun. Money is
credited when Stripe confirms the payment: by the webhook, or when the person comes back
and the app verifies the session. Either path credits a payment exactly once.
"""

import logging
from decimal import Decimal
from typing import Optional
from urllib.parse import urlparse

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user_id
from ...config.settings import get_settings
from ...database.config import get_db
from ...database.models import User
from ...services.deposit_ledger import credit_stripe_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])

MIN_DEPOSIT = Decimal("1")
MAX_DEPOSIT = Decimal("10000")


class CheckoutRequest(BaseModel):
    amount: Decimal = Field(gt=0, decimal_places=2)
    # The app page to come back to; must be one of the app's own addresses
    return_url: str = Field(max_length=500)


class VerifyRequest(BaseModel):
    session_id: str = Field(min_length=10, max_length=200)


def get_client() -> stripe.StripeClient:
    key = get_settings().stripe_secret_key
    if not key:
        raise HTTPException(status_code=503, detail="Card payments aren't set up yet")
    return stripe.StripeClient(key)


def safe_return_url(url: str) -> str:
    """Only send people back to the app itself, never to an address someone slipped in."""
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if parsed.scheme not in ("http", "https") or origin not in get_settings().cors_origins:
        raise HTTPException(status_code=400, detail="That return address isn't part of Hoardrun.")
    return f"{origin}{parsed.path or '/'}"


def as_dict(obj) -> dict:
    return obj.to_dict() if hasattr(obj, "to_dict") else dict(obj)


@router.get("/provider")
async def provider():
    """Which card provider Add money uses: Stripe when it's set up, else Paystack, else none."""
    settings = get_settings()
    name = "stripe" if settings.stripe_secret_key else "paystack" if settings.paystack_secret_key else None
    return {"provider": name}


@router.post("/stripe/checkout")
async def create_checkout(payload: CheckoutRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    amount = payload.amount.quantize(Decimal("0.01"))
    if not MIN_DEPOSIT <= amount <= MAX_DEPOSIT:
        raise HTTPException(status_code=400, detail=f"Add between ${MIN_DEPOSIT:,.0f} and ${MAX_DEPOSIT:,.0f} at a time.")
    back = safe_return_url(payload.return_url)
    client = get_client()
    user = db.get(User, user_id)
    params = {
        "mode": "payment",
        "line_items": [{
            "quantity": 1,
            "price_data": {"currency": "usd", "unit_amount": int(amount * 100), "product_data": {"name": "Add money to Hoardrun"}},
        }],
        "payment_method_types": ["card"],
        "client_reference_id": user_id,
        "metadata": {"user_id": user_id},
        "payment_intent_data": {"metadata": {"user_id": user_id}},
        "success_url": f"{back}?stripe_session={{CHECKOUT_SESSION_ID}}",
        "cancel_url": back,
    }
    if user is not None and user.email:
        params["customer_email"] = user.email
    try:
        session = client.v1.checkout.sessions.create(params=params)
    except stripe.AuthenticationError:
        logger.error("Stripe rejected the secret key")
        raise HTTPException(status_code=503, detail="Card payments aren't available right now.")
    except stripe.StripeError as error:
        logger.error("Stripe checkout failed: %s", error)
        raise HTTPException(status_code=502, detail="Couldn't open the secure checkout. Try again.")
    return {"url": session.url, "session_id": session.id}


def fetch_session(client: stripe.StripeClient, session_id: str) -> dict:
    session = client.v1.checkout.sessions.retrieve(session_id, params={"expand": ["payment_intent.payment_method"]})
    return as_dict(session)


@router.post("/stripe/verify")
async def verify(payload: VerifyRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    client = get_client()
    try:
        session = fetch_session(client, payload.session_id)
    except stripe.InvalidRequestError:
        raise HTTPException(status_code=404, detail="That payment wasn't found.")
    except stripe.StripeError as error:
        logger.error("Stripe verify failed: %s", error)
        raise HTTPException(status_code=502, detail="Couldn't check the payment. Try again.")
    try:
        credited = credit_stripe_session(db, session, expected_user_id=user_id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="This payment belongs to a different account")
    if credited is None:
        return {"status": session.get("payment_status") or "unpaid", "credited": False}
    transaction, was_new = credited
    return {"status": "paid", "credited": True, "new": was_new, "amount": float(transaction.amount)}


@router.post("/stripe/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe calls this when a payment completes; the signature proves it's really Stripe."""
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook isn't set up")
    client = get_client()
    payload = await request.body()
    try:
        event = client.construct_event(payload, request.headers.get("stripe-signature"), settings.stripe_webhook_secret)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event.type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        session_id = event.data.object["id"]
        try:
            # Fetched again with the card attached, so the deposit can be linked to it
            session = fetch_session(client, session_id)
            result: Optional[tuple] = credit_stripe_session(db, session)
            if result:
                logger.info("Stripe deposit %s %s", session_id, "credited" if result[1] else "already credited")
        except stripe.StripeError as error:
            # A 5xx makes Stripe retry later
            logger.error("Stripe webhook couldn't fetch %s: %s", session_id, error)
            raise HTTPException(status_code=502, detail="Retry later")
    return {"received": True}
