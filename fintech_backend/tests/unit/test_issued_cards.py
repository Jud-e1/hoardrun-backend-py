"""
Hoardrun cards with Stripe Issuing. Stripe's API is faked; webhook signatures use Stripe's real check.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_issued_cards.py --noconftest --import-mode=importlib
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

from app.api.v1 import identity, issued_cards
from app.auth.dependencies import get_current_user_id
from app.database.config import Base, get_db
from app.database.models import Account, Transaction, TransactionStatusEnum, User
from app.services import email_service
from app.services.deposit_ledger import cash_account

SECRET = "whsec_issuing_test"
ADDRESS = {"line1": "1 Market St", "city": "San Francisco", "state": "CA", "postal_code": "94105"}


class Recorder:
    def __init__(self, make):
        self.calls = []
        self.make = make

    def create(self, params=None, options=None):
        self.calls.append((params, options))
        return self.make(params, len(self.calls))

    def update(self, card_id, params=None, options=None):
        self.calls.append((card_id, params))
        return SimpleNamespace(id=card_id)


class FakeStripe:
    def __init__(self):
        self.cardholders = Recorder(lambda p, n: SimpleNamespace(id=f"ich_{n}"))
        self.cards = Recorder(lambda p, n: {"id": f"ic_{n}", "last4": f"424{n}", "brand": "Visa", "exp_month": 12, "exp_year": 2029})
        self.keys = Recorder(lambda p, n: SimpleNamespace(secret=f"ek_test_{n}"))
        self.v1 = SimpleNamespace(issuing=SimpleNamespace(cardholders=self.cardholders, cards=self.cards), ephemeral_keys=self.keys)
        self._real = stripe.StripeClient("sk_test_dummy")

    def construct_event(self, payload, sig_header, secret, tolerance=300):
        return self._real.construct_event(payload, sig_header, secret, tolerance)


@pytest.fixture
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add(User(id="ada", email="ada@example.com", password_hash="x", first_name="Ada", last_name="Mensah", status="active"))
        db.add(User(id="kofi", email="kofi@example.com", password_hash="x", first_name="Kofi", last_name="Boateng", status="active"))
        db.commit()

    settings = issued_cards.get_settings()
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_dummy")
    monkeypatch.setattr(settings, "stripe_issuing_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "persona_api_key", "")
    fake = FakeStripe()
    monkeypatch.setattr(issued_cards, "get_client", lambda: fake)
    monkeypatch.setattr(email_service, "deliver", lambda *a: True)
    monkeypatch.setattr(email_service, "_pool", type("Now", (), {"submit": staticmethod(lambda fn, *a: fn(*a))})())

    app = FastAPI()
    app.include_router(issued_cards.router, prefix="/api/v1")

    def db_override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    who = {"id": "ada"}
    app.dependency_overrides[get_current_user_id] = lambda: who["id"]
    return TestClient(app), Session, fake, who


def new_card(client, **extra):
    body = {"billing": ADDRESS, "accept_terms": True, **extra}
    response = client.post("/api/v1/issuing/cards", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def give_cash(Session, amount, user="ada"):
    with Session() as db:
        account = cash_account(db, user, "USD")
        account.available_balance = account.current_balance = Decimal(amount)
        db.commit()


def balances(Session, user="ada"):
    with Session() as db:
        a = db.query(Account).filter(Account.user_id == user).one()
        return Decimal(a.current_balance), Decimal(a.available_balance), Decimal(a.reserved_balance or 0)


def send(client, event_type, obj):
    payload = json.dumps({"id": f"evt_{time.time_ns()}", "object": "event", "type": event_type, "data": {"object": obj}})
    stamp = int(time.time())
    sig = hmac.new(SECRET.encode(), f"{stamp}.{payload}".encode(), hashlib.sha256).hexdigest()
    return client.post("/api/v1/issuing/webhook", content=payload, headers={"stripe-signature": f"t={stamp},v1={sig}"})


def auth_request(auth_id="iauth_1", card="ic_1", cents=2500, currency="usd"):
    return {"id": auth_id, "object": "issuing.authorization", "card": {"id": card}, "status": "pending",
            "pending_request": {"amount": cents, "currency": currency},
            "merchant_data": {"name": "Blue Bottle Coffee", "category": "eating_places_restaurants"}}


def capture(txn_id="ipi_1", auth_id="iauth_1", card="ic_1", cents=-2000, kind="capture"):
    return {"id": txn_id, "object": "issuing.transaction", "type": kind, "amount": cents, "card": card,
            "authorization": auth_id, "merchant_data": {"name": "Blue Bottle Coffee", "category": "eating_places_restaurants"}}


def test_getting_a_card_needs_terms_and_a_us_address_once(env):
    client, Session, fake, _ = env
    assert client.post("/api/v1/issuing/cards", json={"billing": ADDRESS}).status_code == 400
    assert client.post("/api/v1/issuing/cards", json={"accept_terms": True}).status_code == 400
    bad_state = {**ADDRESS, "state": "ZZ"}
    assert client.post("/api/v1/issuing/cards", json={"billing": bad_state, "accept_terms": True}).status_code == 400
    card = new_card(client)
    assert card["last4"] == "4241" and card["status"] == "active" and card["monthly_limit"] == 2000
    holder = fake.cardholders.calls[0][0]
    assert holder["billing"]["address"]["country"] == "US" and holder["metadata"] == {"user_id": "ada"}
    assert "user_terms_acceptance" in holder["individual"]["card_issuing"]
    made = fake.cards.calls[0][0]
    assert made["type"] == "virtual" and made["spending_controls"]["spending_limits"][0] == {"amount": 200000, "interval": "monthly"}
    # The second card reuses the cardholder
    new_card(client, billing=None)
    assert len(fake.cardholders.calls) == 1
    assert client.post("/api/v1/issuing/cards", json={"accept_terms": True}).status_code == 409


def test_a_card_needs_a_verified_identity_once_checks_are_on(env, monkeypatch):
    client, _, _, _ = env
    monkeypatch.setattr(identity, "configured", lambda: True)
    response = client.post("/api/v1/issuing/cards", json={"billing": ADDRESS, "accept_terms": True})
    assert response.status_code == 403 and "Verify your identity" in response.json()["detail"]


def test_a_purchase_is_approved_and_held_only_when_cash_covers_it(env):
    client, Session, _, _ = env
    new_card(client)
    give_cash(Session, 30)
    response = send(client, "issuing_authorization.request", auth_request(cents=2500))
    assert response.status_code == 200 and response.json() == {"approved": True}
    assert balances(Session) == (Decimal("30"), Decimal("5"), Decimal("25"))
    # Stripe may ask again: same answer, held once
    assert send(client, "issuing_authorization.request", auth_request(cents=2500)).json() == {"approved": True}
    assert balances(Session) == (Decimal("30"), Decimal("5"), Decimal("25"))
    with Session() as db:
        pending = db.query(Transaction).one()
        assert pending.status == TransactionStatusEnum.PENDING and pending.merchant_category.value == "restaurants"

    declined = send(client, "issuing_authorization.request", auth_request(auth_id="iauth_2", cents=1000))
    assert declined.json() == {"approved": False}
    assert send(client, "issuing_authorization.request", auth_request(auth_id="iauth_3", cents=100, currency="eur")).json() == {"approved": False}


def test_a_frozen_card_is_declined(env):
    client, Session, fake, _ = env
    card = new_card(client)
    give_cash(Session, 100)
    assert client.post(f"/api/v1/issuing/cards/{card['id']}/freeze").json()["status"] == "frozen"
    assert fake.cards.calls[-1] == ("ic_1", {"status": "inactive"})
    assert send(client, "issuing_authorization.request", auth_request()).json() == {"approved": False}
    client.post(f"/api/v1/issuing/cards/{card['id']}/unfreeze")
    assert send(client, "issuing_authorization.request", auth_request()).json() == {"approved": True}


def test_the_charge_replaces_the_hold_once(env):
    client, Session, _, _ = env
    new_card(client)
    give_cash(Session, 30)
    send(client, "issuing_authorization.request", auth_request(cents=2500))
    # The merchant charges less than it held (a tip-less total, say)
    assert send(client, "issuing_transaction.created", capture(cents=-2000)).status_code == 200
    send(client, "issuing_transaction.created", capture(cents=-2000))
    # Until Stripe closes the purchase it could still charge more, so the other $5 stays held
    assert balances(Session) == (Decimal("10"), Decimal("5"), Decimal("5"))
    with Session() as db:
        rows = db.query(Transaction).all()
        assert len(rows) == 1 and rows[0].status == TransactionStatusEnum.COMPLETED and rows[0].amount == Decimal("20")
    send(client, "issuing_authorization.updated", {**auth_request(), "status": "closed"})
    send(client, "issuing_authorization.updated", {**auth_request(), "status": "closed"})
    assert balances(Session) == (Decimal("10"), Decimal("10"), Decimal("0"))
    with Session() as db:
        assert db.query(Transaction).one().status == TransactionStatusEnum.COMPLETED


def test_a_cancelled_purchase_releases_its_hold(env):
    client, Session, _, _ = env
    new_card(client)
    give_cash(Session, 30)
    send(client, "issuing_authorization.request", auth_request(cents=2500))
    send(client, "issuing_authorization.updated", {**auth_request(), "status": "reversed"})
    assert balances(Session) == (Decimal("30"), Decimal("30"), Decimal("0"))
    with Session() as db:
        assert db.query(Transaction).one().status == TransactionStatusEnum.CANCELLED


def test_refunds_come_back_to_cash(env):
    client, Session, _, _ = env
    new_card(client)
    give_cash(Session, 10)
    send(client, "issuing_transaction.created", capture(txn_id="ipi_r", auth_id=None, cents=1500, kind="refund"))
    send(client, "issuing_transaction.created", capture(txn_id="ipi_r", auth_id=None, cents=1500, kind="refund"))
    assert balances(Session) == (Decimal("25"), Decimal("25"), Decimal("0"))


def test_cards_belong_to_their_owner(env):
    client, _, fake, who = env
    card = new_card(client)
    who["id"] = "kofi"
    assert client.post(f"/api/v1/issuing/cards/{card['id']}/freeze").status_code == 404
    assert client.post(f"/api/v1/issuing/cards/{card['id']}/ephemeral-key", json={"nonce": "ephemeral_nonce_x"}).status_code == 404
    assert client.get("/api/v1/issuing/cards").json()["cards"] == []


def test_card_details_go_through_a_short_lived_stripe_key(env):
    client, _, fake, _ = env
    card = new_card(client)
    body = client.post(f"/api/v1/issuing/cards/{card['id']}/ephemeral-key", json={"nonce": "ephemeral_nonce_x"}).json()
    assert body == {"secret": "ek_test_1", "stripe_card_id": "ic_1"}
    params, options = fake.keys.calls[0]
    assert params == {"issuing_card": "ic_1", "nonce": "ephemeral_nonce_x"} and options == {"stripe_version": "2020-03-02"}


def test_cancelling_is_permanent_and_limits_change_at_stripe(env):
    client, _, fake, _ = env
    card = new_card(client)
    assert client.put(f"/api/v1/issuing/cards/{card['id']}/limit", json={"monthly_limit": 500}).json()["monthly_limit"] == 500
    assert fake.cards.calls[-1][1]["spending_controls"]["spending_limits"][0]["amount"] == 50000
    assert client.delete(f"/api/v1/issuing/cards/{card['id']}").json()["status"] == "canceled"
    assert client.post(f"/api/v1/issuing/cards/{card['id']}/unfreeze").status_code == 404


def test_webhooks_must_be_signed(env):
    client, Session, _, _ = env
    new_card(client)
    give_cash(Session, 30)
    payload = json.dumps({"id": "evt_x", "object": "event", "type": "issuing_authorization.request", "data": {"object": auth_request()}})
    response = client.post("/api/v1/issuing/webhook", content=payload, headers={"stripe-signature": "t=1,v1=bad"})
    assert response.status_code == 400 and balances(Session)[2] == 0


def test_not_configured_says_so(env, monkeypatch):
    client, _, _, _ = env
    monkeypatch.setattr(issued_cards, "get_client", REAL_GET_CLIENT)
    monkeypatch.setattr(issued_cards.get_settings(), "stripe_secret_key", "")
    assert client.get("/api/v1/issuing/config").json()["configured"] is False
    response = client.post("/api/v1/issuing/cards", json={"billing": ADDRESS, "accept_terms": True})
    assert response.status_code == 503 and response.json()["detail"] == "Hoardrun cards aren't set up yet"


REAL_GET_CLIENT = issued_cards.get_client
