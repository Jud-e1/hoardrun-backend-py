"""
Card deposits through Stripe Checkout. Stripe's API is faked; webhook signatures use Stripe's real check.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_stripe_payments.py --noconftest --import-mode=importlib
"""

import hashlib
import hmac
import json
import os
import time
from decimal import Decimal
from types import SimpleNamespace

# Must be set before the app is imported, so these tests can never reach a real database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
import stripe
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import stripe_payments
from app.auth.dependencies import get_current_user_id
from app.database.config import Base, get_db
from app.database.models import Account, Transaction, User
from app.services.card_vault import SavedCard

WEBHOOK_SECRET = "whsec_test_secret_for_unit_tests"
# Kept before any test swaps it for the fake
REAL_GET_CLIENT = stripe_payments.get_client
CARD = {"brand": "visa", "last4": "4242", "exp_month": 12, "exp_year": 2031, "fingerprint": "fp_abc123", "funding": "debit"}


def paid_session(session_id="cs_test_0001", user_id="ada", cents=2500, status="paid"):
    return {"id": session_id, "mode": "payment", "payment_status": status, "amount_total": cents, "currency": "usd",
            "metadata": {"user_id": user_id}, "created": int(time.time()),
            "payment_intent": {"id": "pi_1", "payment_method": {"id": "pm_1", "card": CARD}}}


class FakeSessions:
    def __init__(self):
        self.created = []
        self.store = {}

    def create(self, params=None, options=None):
        self.created.append(params)
        return SimpleNamespace(id="cs_test_new", url="https://checkout.stripe.com/c/pay/cs_test_new")

    def retrieve(self, session_id, params=None, options=None):
        if session_id not in self.store:
            raise stripe.InvalidRequestError("No such checkout session", param="session")
        return self.store[session_id]


class FakeClient:
    def __init__(self):
        self.sessions = FakeSessions()
        self.v1 = SimpleNamespace(checkout=SimpleNamespace(sessions=self.sessions))
        self._real = stripe.StripeClient("sk_test_dummy")

    def construct_event(self, payload, sig_header, secret, tolerance=300):
        return self._real.construct_event(payload, sig_header, secret, tolerance)


@pytest.fixture
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add(User(id="ada", email="ada@example.com", password_hash="x", first_name="Ada", last_name="Mensah"))
        db.add(User(id="kofi", email="kofi@example.com", password_hash="x", first_name="Kofi", last_name="Boateng"))
        db.commit()

    settings = stripe_payments.get_settings()
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_dummy")
    monkeypatch.setattr(settings, "stripe_webhook_secret", WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "cors_origins", ["http://localhost:3000"])
    fake = FakeClient()
    monkeypatch.setattr(stripe_payments, "get_client", lambda: fake)

    app = FastAPI()
    app.include_router(stripe_payments.router, prefix="/api/v1")

    def db_override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    who = {"id": "ada"}
    app.dependency_overrides[get_current_user_id] = lambda: who["id"]
    return TestClient(app), Session, fake, who


def cash(Session, user="ada"):
    with Session() as db:
        accounts = db.query(Account).filter(Account.user_id == user).all()
        return sum((Decimal(a.available_balance) for a in accounts), Decimal(0))


def signed(event: dict):
    payload = json.dumps(event)
    stamp = int(time.time())
    signature = hmac.new(WEBHOOK_SECRET.encode(), f"{stamp}.{payload}".encode(), hashlib.sha256).hexdigest()
    return payload, f"t={stamp},v1={signature}"


def test_provider_prefers_stripe(env):
    client, _, _, _ = env
    assert client.get("/api/v1/payments/provider").json() == {"provider": "stripe"}


def test_checkout_opens_stripe_with_the_right_amount_and_user(env):
    client, _, fake, _ = env
    response = client.post("/api/v1/payments/stripe/checkout", json={"amount": 25, "return_url": "http://localhost:3000/home"})
    assert response.json()["url"].startswith("https://checkout.stripe.com/")
    params = fake.sessions.created[0]
    assert params["line_items"][0]["price_data"]["unit_amount"] == 2500
    assert params["metadata"] == {"user_id": "ada"} and params["customer_email"] == "ada@example.com"
    assert params["success_url"] == "http://localhost:3000/home?stripe_session={CHECKOUT_SESSION_ID}"


def test_checkout_refuses_other_sites_and_out_of_range_amounts(env):
    client, _, fake, _ = env
    assert client.post("/api/v1/payments/stripe/checkout", json={"amount": 25, "return_url": "https://evil.example/steal"}).status_code == 400
    assert client.post("/api/v1/payments/stripe/checkout", json={"amount": 0.5, "return_url": "http://localhost:3000/home"}).status_code == 400
    assert client.post("/api/v1/payments/stripe/checkout", json={"amount": 20000, "return_url": "http://localhost:3000/home"}).status_code == 400
    assert fake.sessions.created == []


def test_verify_credits_once_and_saves_the_card(env):
    client, Session, fake, _ = env
    fake.sessions.store["cs_test_0001"] = paid_session()
    first = client.post("/api/v1/payments/stripe/verify", json={"session_id": "cs_test_0001"}).json()
    again = client.post("/api/v1/payments/stripe/verify", json={"session_id": "cs_test_0001"}).json()
    assert first["credited"] and first["new"] and first["amount"] == 25
    assert again["credited"] and not again["new"]
    assert cash(Session) == Decimal("25")
    with Session() as db:
        card = db.query(SavedCard).one()
        assert card.last4 == "4242" and card.source == "stripe" and card.signature == "fp_abc123"
        tx = db.query(Transaction).one()
        assert tx.merchant_name == "Stripe" and tx.description.endswith("•••• 4242")


def test_unpaid_session_adds_nothing(env):
    client, Session, fake, _ = env
    fake.sessions.store["cs_test_0002"] = paid_session("cs_test_0002", status="unpaid")
    body = client.post("/api/v1/payments/stripe/verify", json={"session_id": "cs_test_0002"}).json()
    assert body == {"status": "unpaid", "credited": False}
    assert cash(Session) == 0


def test_someone_elses_payment_is_refused(env):
    client, Session, fake, who = env
    fake.sessions.store["cs_test_0003"] = paid_session("cs_test_0003", user_id="ada")
    who["id"] = "kofi"
    assert client.post("/api/v1/payments/stripe/verify", json={"session_id": "cs_test_0003"}).status_code == 403
    assert cash(Session, "kofi") == 0 and cash(Session, "ada") == 0


def test_webhook_credits_with_a_valid_signature_only(env):
    client, Session, fake, _ = env
    fake.sessions.store["cs_test_0004"] = paid_session("cs_test_0004", cents=4000)
    event = {"id": "evt_1", "object": "event", "type": "checkout.session.completed",
             "data": {"object": {"id": "cs_test_0004", "object": "checkout.session"}}}
    payload, header = signed(event)

    forged = client.post("/api/v1/payments/stripe/webhook", content=payload, headers={"stripe-signature": "t=1,v1=bad"})
    assert forged.status_code == 400 and cash(Session) == 0

    assert client.post("/api/v1/payments/stripe/webhook", content=payload, headers={"stripe-signature": header}).status_code == 200
    # Stripe may deliver the same event again; it still counts once
    client.post("/api/v1/payments/stripe/webhook", content=payload, headers={"stripe-signature": header})
    assert cash(Session) == Decimal("40")


def test_not_configured_says_so(env, monkeypatch):
    client, _, _, _ = env
    monkeypatch.setattr(stripe_payments, "get_client", REAL_GET_CLIENT)
    monkeypatch.setattr(stripe_payments.get_settings(), "stripe_secret_key", "")
    response = client.post("/api/v1/payments/stripe/checkout", json={"amount": 25, "return_url": "http://localhost:3000/home"})
    assert response.status_code == 503
    assert client.get("/api/v1/payments/provider").json()["provider"] != "stripe"
